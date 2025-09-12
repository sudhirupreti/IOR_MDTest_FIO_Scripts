import argparse
import subprocess
import csv
import re
import sys

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
    """
    Parses the MDTest summary rate table.
    Returns a list of dicts with operation and stats.
    """
    lines = output.splitlines()
    results = []
    start = False
    for i, line in enumerate(lines):
        if 'SUMMARY rate' in line:
            start = True
            continue
        if start and line.strip().startswith('Operation'):
            # Next line is dashes, then the data lines follow
            table_start = i + 2
            break
    else:
        return results

    # Parse table entries until a non-data line is found
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
    parser = argparse.ArgumentParser(description="Run IOR or MDTest with custom options.")
    parser.add_argument('--benchmark', '-bm', choices=['ior', 'mdtest'], required=True, help="Which benchmark to run: ior or mdtest")
    parser.add_argument('--machinefile', required=True, help='MPI machinefile')
    parser.add_argument('--ppn', type=int, required=True, help='Processes per node')
    parser.add_argument('--workdir', '-d', required=True, help='Working/output directory')
    parser.add_argument('--output', help='CSV file to save results (optional)')
    parser.add_argument('--interface', default='eth0', help='Network interface for MPI traffic (default: eth0)')
    parser.add_argument('--blocksize', '-b', help='IOR block size (e.g. 1m)')
    parser.add_argument('--files_per_proc', '-n', type=int, help='Files per proc (for MDTest)')

    args = parser.parse_args()

    mpirun_path = 'mpirun'
    mpi_common = [
        mpirun_path,
        '--oversubscribe',
        '--mca', 'pml', 'ob1',
        '--mca', 'btl', 'tcp,self',
        '--mca', 'btl_tcp_if_include', args.interface,
        '--machinefile', args.machinefile,
        '-npernode', str(args.ppn)
    ]

    if args.benchmark == "ior":
        if not args.blocksize:
            print("Error: --blocksize is required for IOR.")
            sys.exit(1)
        cmd = mpi_common + [
            'ior', '-t', '1m', '-b', args.blocksize, '-o', args.workdir, '-vv'
        ]
    elif args.benchmark == "mdtest":
        if not args.files_per_proc:
            print("Error: --files_per_proc (-n) is required for MDTest.")
            sys.exit(1)
        # Customize parameters as needed
        cmd = mpi_common + [
            'mdtest', '-n', str(args.files_per_proc), '-d', args.workdir
        ]
    else:
        print("Unknown benchmark selected.")
        sys.exit(1)

    print("Running command:")
    print(' '.join(map(str, cmd)))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(proc.stdout)

    if proc.returncode != 0:
        print("Benchmark failed:\n", proc.stderr)
        sys.exit(1)

    # Parse and save results
    if args.benchmark == "ior":
        results = parse_ior_output(proc.stdout)
        if args.output:
            if results:
                with open(args.output, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=results.keys())
                    writer.writeheader()
                    writer.writerow(results)
                print("IOR results saved to:", args.output)
            else:
                print("No IOR results to write to CSV.")
    elif args.benchmark == "mdtest":
        table = parse_mdtest_summary_table(proc.stdout)
        if args.output:
            if table:
                fieldnames = ['operation', 'max', 'min', 'mean', 'stddev']
                with open(args.output, 'w', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(table)
                print("MDTest summary saved to:", args.output)
            else:
                print("No MDTest summary table found to write to CSV.")

if __name__ == "__main__":
    main()
