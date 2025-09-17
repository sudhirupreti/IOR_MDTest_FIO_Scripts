import argparse
import subprocess
import csv
import re
import sys
import os
import tempfile
from datetime import datetime

def parse_size_string(s):
    match = re.match(r'^(\d+)([KMGTP]?)[bB]?$', s.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse memory: {s}")
    value, unit = int(match.group(1)), match.group(2).upper()
    unit_mult = {'': 1, 'K': 1/1024, 'M': 1, 'G': 1024, 'T': 1024*1024}
    return value * unit_mult.get(unit, 1)  # Returns MB

def size_to_mb(size_str):
    # Accepts e.g. '1M', '1m', '512K', '4G'
    match = re.match(r'^(\d+)([KMG])$', size_str.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse size: {size_str}")
    value, unit = int(match.group(1)), match.group(2).upper()
    if unit == 'M':
        return value
    elif unit == 'G':
        return value * 1024
    elif unit == 'K':
        return value / 1024
    else:
        raise ValueError(f"Unknown unit: {unit}")

def mb_to_size_str(mb):
    return f"{int(mb // 1024)}g" if mb >= 1024 else f"{int(mb)}m"

def get_all_nodes(machinefile):
    with open(machinefile) as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def write_temp_machinefile(nodes):
    tf = tempfile.NamedTemporaryFile(delete=False, mode='w')
    for n in nodes:
        tf.write(f"{n}\n")
    tf.close()
    return tf.name

def parse_ior_output(output):
    results = {}
    for line in output.splitlines():
        if "Max Write" in line:
            match = re.search(r"Max Write:\s+([\d\.]+)\s+(\w+/s)", line)
            if match:
                results['max_write'] = match.group(1)
                results['write_units'] = match.group(2)
        if "Max Read" in line:
            match = re.search(r"Max Read:\s+([\d\.]+)\s+(\w+/s)", line)
            if match:
                results['max_read'] = match.group(1)
                results['read_units'] = match.group(2)
    return results

def parse_mdtest_summary_table(output):
    lines = output.splitlines()
    results = []
    start = False
    for i, line in enumerate(lines):
        if 'SUMMARY rate' in line:
            start = True
            continue
        if start and line.strip().startswith('Operation'):
            table_start = i + 2
            break
    else:
        return results
    for line in lines[table_start:]:
        if line.strip() == "" or line.strip().startswith('--'):
            break
        cols = re.split(r'\s{2,}', line.strip())
        if len(cols) == 5:
            op, maxval, minval, meanval, stddev = cols
            results.append({
                'operation': op,
                'max': maxval,
                'min': minval,
                'mean': meanval,
                'stddev': stddev
            })
    return results

def main():
    parser = argparse.ArgumentParser(description="IOR/MDTest with node, process, and file scaling, and per-run logs.")
    parser.add_argument('--benchmark', '-bm', choices=['ior', 'mdtest'], required=True, help="Which benchmark to run: ior or mdtest")
    parser.add_argument('--machinefile', required=True, help='MPI machinefile (list of available nodes)')
    parser.add_argument('--num-hosts', required=True, help='Comma-separated #nodes for sweep, e.g. 1,2,4,8')
    parser.add_argument('--ppn', required=True, help='Comma-separated list, e.g. 2,4,8 for processes-per-node sweep')
    parser.add_argument('--workdir', '-d', required=True, help='Working/output directory')
    parser.add_argument('--output', help='CSV file to save aggregate results (optional)')
    parser.add_argument('--interface', default='eth0', help='Network interface for MPI traffic (default: eth0)')
    parser.add_argument('--memory', required=True, help='Total memory per node (e.g. 128G or 131072M, REQUIRED for IOR)')
    parser.add_argument('--num-files', type=int, help='Total number of files (for MDTest)')
    parser.add_argument('--transfer_size', required=True, help='Comma separated, Transfer or I/O size (e.g. 4k,128k,1M. REQUIRED for IOR)')
    args = parser.parse_args()

    num_hosts_list = [int(x) for x in args.num_hosts.split(',') if x.strip()]
    ppn_list = [int(x) for x in args.ppn.split(',') if x.strip()]
    transfer_size_list = [x.strip() for x in args.transfer_size.split(',') if x.strip()]
    all_nodes = get_all_nodes(args.machinefile)
    nowstr_base = datetime.now().strftime("%Y%m%d-%H%M%S")
    script_pid = os.getpid()

    if args.benchmark == "ior":
        per_node_memory_mb = parse_size_string(args.memory)
        scaling_results = []
        for n_nodes in num_hosts_list:
            subnodes = all_nodes[:n_nodes]
            temp_machinefile = write_temp_machinefile(subnodes)
            for ppn in ppn_list:
                initial_blocksize_mb = (1.5 * per_node_memory_mb) / ppn
                for xfer_size in transfer_size_list:
                    try:
                        xfer_mb = size_to_mb(xfer_size)
                    except Exception as e:
                        print(f"[SKIP] Could not parse transfer size '{xfer_size}': {e}")
                        continue
                    if xfer_mb == 0:
                        print(f"[SKIP] Transfer size must be >0")
                        continue
                    # Block size as largest multiple of transfer size not exceeding initial_blocksize_mb
                    blocksize_mb = (int(initial_blocksize_mb) // int(xfer_mb)) * int(xfer_mb)
                    if blocksize_mb < xfer_mb:
                        print(f"[SKIP] Blocksize ({initial_blocksize_mb}MB rounded down to {blocksize_mb}MB) smaller than transfer size ({xfer_mb}MB); skipping")
                        continue
                    blocksize_arg = mb_to_size_str(blocksize_mb)
                    print(f"[INFO] Nodes={n_nodes}, PPN={ppn}, transfer_size={xfer_size}, blocksize={blocksize_arg} ({blocksize_mb}MB, rounded to multiple of transfer_size)")

                    mpirun_path = 'mpirun'
                    mpi_cmd = [
                        mpirun_path, '--oversubscribe',
                        '--mca', 'pml', 'ob1',
                        '--mca', 'btl', 'tcp,self',
                        '--mca', 'btl_tcp_if_include', args.interface,
                        '--machinefile', temp_machinefile,
                        '-npernode', str(ppn),
                        'ior', '-t', xfer_size, '-b', blocksize_arg, '-o', args.workdir, '-vv'
                    ]
                    print("[RUN]", ' '.join(mpi_cmd))
                    proc = subprocess.run(mpi_cmd, capture_output=True, text=True)
                    logname = f"{nowstr_base}_{args.benchmark}_ppn{ppn}_nodes{n_nodes}_t{xfer_size}_b{blocksize_arg}_pid{script_pid}.log"
                    with open(logname, "w") as flog:
                        flog.write(proc.stdout)
                        if proc.stderr:
                            flog.write("\nSTDERR:\n" + proc.stderr)
                    print(f"[INFO] Output saved to {logname}")

                    if proc.returncode != 0:
                        print(f"[ERROR] IOR failed for PPN={ppn}, node_count={n_nodes}, transfer_size={xfer_size}, blocksize={blocksize_arg}. STDERR:")
                        print(proc.stderr)
                        # Optionally, append a record of failure
                        scaling_results.append({
                            'ppn': ppn,
                            'node_count': n_nodes,
                            'blocksize': blocksize_arg,
                            'transfer_size': xfer_size,
                            'max_write': 'ERROR',
                            'write_units': '',
                            'max_read': '',
                            'read_units': ''
                        })
                        continue
                    results = parse_ior_output(proc.stdout)
                    if results:
                        results['ppn'] = ppn
                        results['node_count'] = n_nodes
                        results['blocksize'] = blocksize_arg
                        results['transfer_size'] = xfer_size
                        scaling_results.append(results)
            os.remove(temp_machinefile)
        if args.output and scaling_results:
            fieldnames = ['ppn', 'node_count', 'blocksize', 'transfer_size', 'max_write', 'write_units', 'max_read', 'read_units']
            with open(args.output, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(scaling_results)
            print("IOR scaling results saved to:", args.output)

    elif args.benchmark == "mdtest":
        if not args.num_files:
            print("Error: --num-files is required for MDTest.")
            sys.exit(1)
        scaling_results = []
        for n_nodes in num_hosts_list:
            subnodes = all_nodes[:n_nodes]
            temp_machinefile = write_temp_machinefile(subnodes)
            for ppn in ppn_list:
                total_procs = n_nodes * ppn
                files_per_proc = max(args.num_files // total_procs, 1)
                total_created = files_per_proc * total_procs
                print(f"[INFO] Nodes={n_nodes}  PPN={ppn}  files_per_proc={files_per_proc}  (total files={total_created})")
                mpirun_path = 'mpirun'
                mpi_cmd = [
                    mpirun_path, '--oversubscribe',
                    '--mca', 'pml', 'ob1',
                    '--mca', 'btl', 'tcp,self',
                    '--mca', 'btl_tcp_if_include', args.interface,
                    '--machinefile', temp_machinefile,
                    '-npernode', str(ppn),
                    'mdtest', '-n', str(files_per_proc), '-d', args.workdir
                ]
                print("[RUN]", ' '.join(mpi_cmd))
                proc = subprocess.run(mpi_cmd, capture_output=True, text=True)
                logname = f"{nowstr_base}_{args.benchmark}_ppn{ppn}_nodes{n_nodes}_pid{script_pid}.log"
                with open(logname, "w") as flog:
                    flog.write(proc.stdout)
                    if proc.stderr:
                        flog.write("\nSTDERR:\n" + proc.stderr)
                print(f"[INFO] Output saved to {logname}")
                if proc.returncode != 0:
                    print("MDTest failed:\n", proc.stderr)
                    continue
                table = parse_mdtest_summary_table(proc.stdout)
                for row in table:
                    row['ppn'] = ppn
                    row['node_count'] = n_nodes
                    row['files_per_proc'] = files_per_proc
                    row['total_files'] = total_created
                scaling_results.extend(table)
            os.remove(temp_machinefile)
        if args.output and scaling_results:
            fieldnames = ['ppn', 'node_count', 'files_per_proc', 'total_files',
                          'operation', 'max', 'min', 'mean', 'stddev']
            with open(args.output, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(scaling_results)
            print("MDTest scaling results saved to:", args.output)

if __name__ == "__main__":
    main()

