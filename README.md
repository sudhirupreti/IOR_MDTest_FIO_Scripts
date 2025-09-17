IOR MDTest FIO Scripts to troubleshoot storage/filesystem issues.

This script assumes that openmpi and ior have already been installed on the system or all the hosts.
```
#If openmpi is not installed, then:
sudo apt-get update
sudo apt-get install openmpi-bin libopenmpi-dev

#Verify using:
mpirun -V
mpirun (Open MPI) 4.1.6

IOR can be downloaded from:
https://github.com/hpc/ior.git

#To compile (if mpirun is installed on a specific directory):
export PATH=$PATH:{path_to_mpi_bin_dir}
export LD_LIBRARY_PATH:{path_to_mpi_lib_dir}

git clone https://github.com/hpc/ior.git

cd ior
#Install dependencies
sudo apt-get update
sudo apt-get install autoconf automake libtool m4 make gcc g++ pkg-config

#Compile
 ./bootstrap ; ./configure ; sudo make ; sudo make install

#IOR will now be installed under
ls /usr/local/bin/
ior  md-workbench  mdtest

#Running IOR
#IOR takes network interface, machinefile, number of hosts, process per node(ppn), work directory, and memory on the client (make sure blocksize is > 1.5 x client memory) as arguments)

python3 run_ior_mdtest.py --interface ens300np0 --transfer_size 1m,2m --benchmark ior --machinefile 1node --num-hosts 1 --memory 1G --ppn 2,4,6,8,10 --workdir /mnt/localdisk/ior --output ior_results.csv

#Running MDTest
#MDtest takes network interface, machinefile,number of hosts, ppn, number of files (Make sure that total combined files > 1M) as arguments.

python3 run_ior_mdtest-v2.py --interface ens300np0  --benchmark mdtest --machinefile 1node --num-hosts 1 --ppn 2,4 --num-files 100 --workdir /mnt/localdisk/mdtest/ --memory 1G --output mdtest_results.csv

#For more info:
python3 run_ior_mdtest.py -h
usage: run_ior_mdtest.py [-h] --benchmark {ior,mdtest} --machinefile MACHINEFILE --num-hosts NUM_HOSTS --ppn PPN --workdir WORKDIR [--output OUTPUT] [--interface INTERFACE] --memory MEMORY
                            [--num-files NUM_FILES] --transfer_size TRANSFER_SIZE

IOR/MDTest with node, process, and file scaling, and per-run logs.

options:
  -h, --help            show this help message and exit
  --benchmark {ior,mdtest}, -bm {ior,mdtest}
                        Which benchmark to run: ior or mdtest
  --machinefile MACHINEFILE
                        MPI machinefile (list of available nodes)
  --num-hosts NUM_HOSTS
                        Comma-separated #nodes for sweep, e.g. 1,2,4,8
  --ppn PPN             Comma-separated list, e.g. 2,4,8 for processes-per-node sweep
  --workdir WORKDIR, -d WORKDIR
                        Working/output directory
  --output OUTPUT       CSV file to save aggregate results (optional)
  --interface INTERFACE
                        Network interface for MPI traffic (default: eth0)
  --memory MEMORY       Total memory per node (e.g. 128G or 131072M, REQUIRED for IOR)
  --num-files NUM_FILES
                        Total number of files (for MDTest)
  --transfer_size TRANSFER_SIZE
                        Comma separated, Transfer or I/O size (e.g. 4k,128k,1M. REQUIRED for IOR)


Running FIO benchmark
# Install FIO benchmark first
sudo apt install fio

#Make sure passwordless login is active among the hosts/client nodes. Run fio with the following command line. Add --output argument if you want results in csv format as well. The fio job
file consists of 4k and 32k bs random writes, random reads , and mixed random writes/reads sections.
./run_fio-v2.sh 1node 4k-and-32k-random.fio --output csv
