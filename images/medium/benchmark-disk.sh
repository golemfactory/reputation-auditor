#!/bin/bash -e

# First parameter is the provider ID
provider_id=$1

# Function to get the disk size in GB
function get_disk_size() {
    local disk_size=$(df --output=size -BG / | tail -n 1 | grep -oP '\d+')
    echo $disk_size
}

# Define function to run sysbench fileio test and store results in JSON
function run_and_parse_fileio() {
    local test_mode=$1
    local output_file=$2
    local benchmark_name="FileIO_${test_mode}"

    # Prepare the test environment
    sysbench fileio --file-total-size=2G --file-test-mode=$test_mode --file-extra-flags=direct --file-fsync-freq=0 --file-num=5 prepare

    # Run the sysbench command
    echo "Running fileio test in $test_mode mode..."
    local output=$(sysbench fileio --file-total-size=2G --file-test-mode=$test_mode --file-extra-flags=direct --file-fsync-freq=0 --file-num=5 run)

    # Parse and extract the necessary details
    local reads_per_sec=$(echo "$output" | grep -oP "reads/s:\s+\K[0-9]+(\.[0-9]+)?")
    local writes_per_sec=$(echo "$output" | grep -oP "writes/s:\s+\K[0-9]+(\.[0-9]+)?")
    local fsyncs_per_sec=$(echo "$output" | grep -oP "fsyncs/s:\s+\K[0-9]+(\.[0-9]+)?")
    local read_throughput=$(echo "$output" | grep -oP "read, MiB/s:\s+\K[0-9]+(\.[0-9]+)?")
    local write_throughput=$(echo "$output" | grep -oP "written, MiB/s:\s+\K[0-9]+(\.[0-9]+)?")
    local total_time=$(echo "$output" | grep -oP "total time:\s+\K[0-9]+\.[0-9]+")
    local total_events=$(echo "$output" | grep -oP "total number of events:\s+\K[0-9]+")
    local min_latency=$(echo "$output" | grep -oP "min:\s+\K[0-9]+\.[0-9]+")
    local avg_latency=$(echo "$output" | grep -oP "avg:\s+\K[0-9]+\.[0-9]+")
    local max_latency=$(echo "$output" | grep -oP "max:\s+\K[0-9]+\.[0-9]+")
    local percentile_95th=$(echo "$output" | grep -oP "95th percentile:\s+\K[0-9]+\.[0-9]+")
    local disk_size=$(get_disk_size)

    # Create JSON object and write to file
    jq -n \
        --arg providerId "$provider_id" \
        --arg benchmarkName "$benchmark_name" \
        --arg readsPerSecond "$reads_per_sec" \
        --arg writesPerSecond "$writes_per_sec" \
        --arg fsyncsPerSecond "$fsyncs_per_sec" \
        --arg readThroughputMBPS "$read_throughput" \
        --arg writeThroughputMBPS "$write_throughput" \
        --arg totalTimeSec "$total_time" \
        --arg totalIOEvents "$total_events" \
        --arg minLatencyMs "$min_latency" \
        --arg avgLatencyMs "$avg_latency" \
        --arg maxLatencyMs "$max_latency" \
        --arg latency95thPercentileMs "$percentile_95th" \
        --arg diskSizeGB "$disk_size" \
        '{
        node_id: $providerId,
        benchmark_name: $benchmarkName,
        reads_per_second: $readsPerSecond,
        writes_per_second: $writesPerSecond,
        fsyncs_per_second: $fsyncsPerSecond,
        read_throughput_mb_ps: $readThroughputMBPS,
        write_throughput_mb_ps: $writeThroughputMBPS,
        total_time_sec: $totalTimeSec,
        total_io_events: $totalIOEvents,
        min_latency_ms: $minLatencyMs,
        avg_latency_ms: $avgLatencyMs,
        max_latency_ms: $maxLatencyMs,
        latency_95th_percentile_ms: $latency95thPercentileMs,
        disk_size_gb: $diskSizeGB
    }' >$output_file

    # Cleanup after test
    sysbench fileio --file-total-size=2G --file-test-mode=$test_mode cleanup

    echo "$test_mode results saved to $output_file"
}

# Ensure the working directory is correct
mkdir -p /golem/work/sysbench
cd /golem/work/sysbench

# Define test modes and respective output files
declare -A tests=(
    ["seqwr"]="sequential_write.json"
    ["seqrd"]="sequential_read.json"
    ["rndwr"]="random_write.json"
    ["rndrd"]="random_read.json"
    ["rndrw"]="random_read_write.json"
)

# Check for provider_id argument
if [ -z "$provider_id" ]; then
    echo "Error: Provider ID not supplied. Please provide it as the first argument."
    exit 1
fi

# Run and parse tests
for test_mode in "${!tests[@]}"; do
    run_and_parse_fileio $test_mode ${tests[$test_mode]}
done
