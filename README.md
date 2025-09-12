IOR MDTest FIO Scripts to troubleshoot storage/filesystem issues.

This script assumes that openmpi and ior have already been installed on the system or all the hosts.
```
IOR can be downloaded from:
https://github.com/hpc/ior.git

To compile:
export PATH=$PATH:{path_to_mpi_bin_dir}
export LD_LIBRARY_PATH:{path_to_mpi_lib_dir}

git clone https://github.com/hpc/ior.git

cd ior
 ./bootstrap ; ./configure ; sudo make ; sudo make install

#IOR will now be installed under
ls /usr/local/bin/
ior  md-workbench  mdtest

#Running IOR
#IOR takes network interface, machinefile, process per node(ppn), work directory, blocksize(make sure blocksize is > 1.5 x client memory) as arguments)

python3 run_ior_mdtest.py --benchmark ior --machinefile 1node --ppn 2 --workdir /mnt/localdisk/ior --blocksize 1m --output ior_results.csv

#Running MDTest
#MDtest takes network interface, machinefile, ppn, files per proc(Make sure that total combined files > 1M) as arguments.

python3 test.py --benchmark mdtest --interface ens300np0 --machinefile 1node --ppn 2 --workdir /mnt/localdisk/mdtest --files_per_proc 1000 --output mdtest_results.csv

#For more info:
python3 run_ior_mdtest.py -h
usage: run_ior_mdtest.py [-h] --benchmark {ior,mdtest} --machinefile MACHINEFILE --ppn PPN --workdir WORKDIR [--output OUTPUT] [--interface INTERFACE] [--blocksize BLOCKSIZE] [--files_per_proc FILES_PER_PROC]

Run IOR or MDTest with custom options.

options:
  -h, --help            show this help message and exit
  --benchmark {ior,mdtest}, -bm {ior,mdtest}
                        Which benchmark to run: ior or mdtest
  --machinefile MACHINEFILE
                        MPI machinefile
  --ppn PPN             Processes per node
  --workdir WORKDIR, -d WORKDIR
                        Working/output directory
  --output OUTPUT       CSV file to save results (optional)
  --interface INTERFACE
                        Network interface for MPI traffic (default: eth0)
  --blocksize BLOCKSIZE, -b BLOCKSIZE
                        IOR block size (e.g. 1m)
  --files_per_proc FILES_PER_PROC, -n FILES_PER_PROC
                        Files per proc (for MDTest)



Running FIO benchmark
# Install FIO benchmark first
sudo apt install fio
#Make sure passwordless login is active among the hosts/client nodes
./run_fio.sh 1node 4k-Mixed-RR-RW-Sample.fio
