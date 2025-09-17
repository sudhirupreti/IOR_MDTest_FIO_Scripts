#!/bin/bash
set -e

show_help() {
    echo "How to use this script:"
    echo "./run_fio.sh hostfile fio_jobfile [--output csv]"
    echo ""
    echo "Arguments:"
    echo "  hostfile         - File containing the list of hosts/clients taking part in the IOR test"
    echo "  fio_jobfile      - Jobfile containing fio parameters used to run FIO. Sample provided."
    echo "  --output csv     - (optional) Output summary results to a CSV file"
    echo ""
    echo "Example:"
    echo "  ./run_fio.sh hostfile 4k.fio --output csv"
}

extract_json() {
  local file="$1"
  local jq_filter="$2"
  local start
  start=$(grep -m 1 -n '{' "$file" | cut -d: -f1)
  if [[ -n "$start" ]]; then
    tail -n +$start "$file" | jq -r "$jq_filter"
  else
    # If no JSON found, echo nothing
    echo ""
  fi
}

# Check for help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
    show_help
    exit 0
fi

# Require at least two arguments
if [[ $# -lt 2 ]]; then
    echo "Error: Missing hostfile or fio job file."
    show_help
    exit 1
fi

HOSTFILE=$1
FIO_JOB=$2

# Optional CSV output flag
OUTPUT_TYPE=""
if [[ "$3" == "--output" && "$4" == "csv" ]]; then
    OUTPUT_TYPE="csv"
fi

if [[ ! -f "$HOSTFILE" || ! -f "$FIO_JOB" ]]; then
    echo "Error: Missing hostfile or fio job file."
    exit 1
fi

# Start fio servers on all remote hosts
echo "Starting fio servers"
clush -w $(paste -sd, $HOSTFILE) "sudo nohup fio --server > /tmp/fio_server.log 2>&1 &"

# Prepare output directories
RESULTS_DIR="fio_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p $RESULTS_DIR
SUMMARY_CSV="$RESULTS_DIR/fio_summary.csv"

if [[ "$OUTPUT_TYPE" == "csv" ]]; then
    # Prepare CSV header
    echo "job_name,block_size,read_iops,read_bw_KiB/s,write_iops,write_bw_KiB/s" > $SUMMARY_CSV
fi

# Parse job sections from the fio jobfile, EXCLUDING [global]
SECTION_NAMES=($(grep -E "^\[" "$FIO_JOB" | sed 's/\[\(.*\)\]/\1/' | grep -v '^global$'))

for JOB in "${SECTION_NAMES[@]}"; do
    OUTFILE="$RESULTS_DIR/${JOB}.json"
    echo "Running fio section: $JOB"
    fio --client=$HOSTFILE "$FIO_JOB" --section="$JOB" --output-format=json --output="$OUTFILE"

    if [[ "$OUTPUT_TYPE" == "csv" ]]; then
        if grep -q '{' "$OUTFILE"; then
            JOB_NAME=$JOB
            BS=$(extract_json "$OUTFILE" '(
              .client_stats[0]["job options"].bs // 
              .client_stats[0].read.bs // 
              .client_stats[0].write.bs // 
              .jobs[0]["job options"].bs // 
              .jobs[0].read.bs // 
              .jobs[0].write.bs // 
              empty
            )')
            RI=$(extract_json "$OUTFILE" '(.client_stats[0].read.iops // .jobs[0].read.iops // empty)')
            RBW=$(extract_json "$OUTFILE" '(.client_stats[0].read.bw // .jobs[0].read.bw // empty)')
            WI=$(extract_json "$OUTFILE" '(.client_stats[0].write.iops // .jobs[0].write.iops // empty)')
            WBW=$(extract_json "$OUTFILE" '(.client_stats[0].write.bw // .jobs[0].write.bw // empty)')
            echo "$JOB_NAME,$BS,$RI,$RBW,$WI,$WBW" >> $SUMMARY_CSV
        else
            echo "Warning: No JSON found in $OUTFILE for $JOB. Skipping."
        fi
    fi
done

# Stop remote fio servers
clush -w $(paste -sd, $HOSTFILE) "sudo pkill fio"

echo "FIO test completed."
if [[ "$OUTPUT_TYPE" == "csv" ]]; then
    echo "CSV summary is in: $SUMMARY_CSV"
fi
echo "All job result files are in: $RESULTS_DIR"
