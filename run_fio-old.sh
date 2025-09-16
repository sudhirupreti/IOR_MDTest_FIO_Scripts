#!/bin/bash
set -e

show_help() {
    echo "How to use this script:"
    echo "./run_fio.sh hostfile fio_jobfile"
    echo ""
    echo "Arguments:"
    echo "  hostfile         - File containing the list of hosts/clients taking part in the IOR test"
    echo "  fio_jobfile      - Jobfile containing fio paramters used to run FIO.Sample provided "
    echo ""
    echo "Example:"
    echo "  ./run_fio.sh hostfile 4k.fio"
}

if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

HOSTFILE=$1
FIO_JOB=$2

# Check inputs
if [[ ! -f "$HOSTFILE" || ! -f "$FIO_JOB" ]]; then
  echo "Error: Missing hostfile or fio job file."
  exit 1
fi


# Start fio servers on all remote hosts
echo "Starting fio servers"
clush -w $(paste -sd, $HOSTFILE) "sudo nohup fio --server > /tmp/fio_server.log 2>&1 &"

# Run the test
echo "Running fio client with hostfile..."
fio --client=$HOSTFILE $FIO_JOB

# Stop remote fio servers
clush -w $(paste -sd, $HOSTFILE) "sudo pkill fio"

echo "FIO test completed."
