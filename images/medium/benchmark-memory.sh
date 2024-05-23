#!/bin/bash -e

# First parameter is the provider_id
provider_id=$1

# Function to derive benchmark name from description
function derive_benchmark_name() {
    local description=$1
    # Replace spaces and special characters in description with underscores or other conventions
    echo $description | sed 's/[^a-zA-Z0-9]/_/g'
}

# Function to get the memory size in GB
function get_memory_size() {
    local memory_size=$(free -g | awk '/^Mem:/{print $2}')
    echo $memory_size
}

# Function to run sysbench and parse results
function run_and_parse_sysbench() {
    local description=$1
    local command=$2
    local output_file=$3

    # Derive benchmark name from description
    benchmark_name=$(derive_benchmark_name "$description")

    # Run sysbench command
    echo "Running $description..."
    local output=$($command)

    # Parse results
    local total_ops=$(echo "$output" | grep -oP "Total operations: \K[0-9]+")
    local ops_per_sec=$(echo "$output" | grep -oP "\(.* per second\)" | grep -oP "[0-9]+(\.[0-9]+)?")
    local total_data_transferred=$(echo "$output" | grep -oP "[0-9]+(\.[0-9]+)? MiB transferred" | grep -oP "[0-9]+(\.[0-9]+)?")
    local throughput=$(echo "$output" | grep -oP "\(.*MiB/sec\)" | grep -oP "[0-9]+(\.[0-9]+)?")
    local total_time=$(echo "$output" | grep -oP "total time: +\K[0-9]+\.[0-9]+")
    local total_events=$(echo "$output" | grep -oP "total number of events: +\K[0-9]+")
    local min_latency=$(echo "$output" | grep -oP "min: +\K[0-9]+(\.[0-9]+)?")
    local avg_latency=$(echo "$output" | grep -oP "avg: +\K[0-9]+(\.[0-9]+)?")
    local max_latency=$(echo "$output" | grep -oP "max: +\K[0-9]+(\.[0-9]+)?")
    local percentile_95th=$(echo "$output" | grep -oP "95th percentile: +\K[0-9]+(\.[0-9]+)?")
    local sum_latency=$(echo "$output" | grep -oP "sum: +\K[0-9]+(\.[0-9]+)?")
    local events=$(echo "$output" | grep -oP "events \(avg/stddev\): +\K[0-9]+(\.[0-9]+)?")
    local exec_time=$(echo "$output" | grep -oP "execution time \(avg/stddev\): +\K[0-9]+\.[0-9]+")
    local memory_size=$(get_memory_size)

    # Create JSON object
    local json_result=$(jq -n \
        --arg providerId "$provider_id" \
        --arg benchmarkName "$benchmark_name" \
        --arg totalOperations "$total_ops" \
        --arg operationsPerSecond "$ops_per_sec" \
        --arg totalDataTransferredMiB "$total_data_transferred" \
        --arg throughputMiBSec "$throughput" \
        --arg totalTimeSec "$total_time" \
        --arg totalEvents "$total_events" \
        --arg minLatencyMs "$min_latency" \
        --arg avgLatencyMs "$avg_latency" \
        --arg maxLatencyMs "$max_latency" \
        --arg latency95thPercentileMs "$percentile_95th" \
        --arg sumLatencyMs "$sum_latency" \
        --arg events "$events" \
        --arg executionTimeSec "$exec_time" \
        --arg memoryGB "$memory_size" \
        '{
        node_id: $providerId,
        benchmark_name: $benchmarkName,
        total_operations: $totalOperations,
        operations_per_second: $operationsPerSecond,
        total_data_transferred_mi_b: $totalDataTransferredMiB,
        throughput_mi_b_sec: $throughputMiBSec,
        total_time_sec: $totalTimeSec,
        total_events: $totalEvents,
        min_latency_ms: $minLatencyMs,
        avg_latency_ms: $avgLatencyMs,
        max_latency_ms: $maxLatencyMs,
        latency_95th_percentile_ms: $latency95thPercentileMs,
        sum_latency_ms: $sumLatencyMs,
        events: $events,
        execution_time_sec: $executionTimeSec
        memory_size_gb: $memoryGB
    }')

    # Write JSON result to file
    echo $json_result >$output_file

    echo "$description results saved to $output_file"
}

# Define sysbench commands and output files
commands=(
    "sysbench memory --memory-block-size=1M --memory-total-size=100G --memory-oper=write --threads=1 run"
    "sysbench memory --memory-block-size=1M --memory-total-size=100G --memory-oper=read --threads=1 run"
    "sysbench memory --memory-block-size=4K --memory-total-size=100G --memory-access-mode=rnd --memory-oper=write --threads=8 run"
    "sysbench memory --memory-block-size=4K --memory-total-size=100G --memory-access-mode=rnd --memory-oper=read --threads=8 run"
    "sysbench memory --memory-block-size=4K --memory-total-size=5G --memory-access-mode=rnd --memory-oper=read --time=60 --threads=1 run"
)
descriptions=(
    "Sequential Write Performance (Single Thread)"
    "Sequential Read Performance (Single Thread)"
    "Random Write Performance (Multi-threaded)"
    "Random Read Performance (Multi-threaded)"
    "Latency Test (Random Read, Single Thread)"
)
output_files=(
    "/golem/work/sequential_write_single_thread.json"
    "/golem/work/sequential_read_single_thread.json"
    "/golem/work/random_write_multi_threaded.json"
    "/golem/work/random_read_multi_threaded.json"
    "/golem/work/latency_test_single_thread.json"
)

# Run and parse sysbench for each command
for i in ${!commands[@]}; do
    run_and_parse_sysbench "${descriptions[$i]}" "${commands[$i]}" "${output_files[$i]}"
done

echo "All benchmarks completed."
