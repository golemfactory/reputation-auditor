#!/bin/bash -e
mkdir -p /golem/work/cpu
# Accept provider_id as the first script parameter
provider_id=$1

# Define output JSON files for different tests
output_json_single="/golem/work/cpu/cpu_single_thread.json"
output_json_multi="/golem/work/cpu/cpu_multi_thread.json"

# Initialize JSON files with an empty JSON object
echo "{}" >$output_json_single
echo "{}" >$output_json_multi

# Get number of CPU cores
cpu_cores=$(nproc)

# Function to parse sysbench output and write to JSON
parse_and_write_output() {
    local test_name=$1
    local threads=$2
    local result_output=$3
    local output_file=$4
    local total_time=$(echo "$result_output" | grep "total time:" | awk '{print $3}')
    local total_events=$(echo "$result_output" | grep "total number of events:" | awk '{print $5}')
    local events_per_second=$(echo "$result_output" | grep "events per second:" | awk '{print $4}')
    local min_latency=$(echo "$result_output" | grep "min:" | head -1 | awk '{print $2}')
    local avg_latency=$(echo "$result_output" | grep "avg:" | awk '{print $2}')
    local max_latency=$(echo "$result_output" | grep "max:" | awk '{print $2}')
    local percentile_latency=$(echo "$result_output" | grep "95th percentile:" | awk '{print $3}')
    local sum_latency=$(echo "$result_output" | grep "sum:" | awk '{print $2}')

    # Construct a new JSON object with the results
    local result_json=$(jq -n \
        --arg providerId "$provider_id" \
        --arg benchmarkName "$test_name" \
        --arg threads "$threads" \
        --arg totalTimeSec "$total_time" \
        --arg totalEvents "$total_events" \
        --arg eventsPerSecond "$events_per_second" \
        --arg minLatencyMs "$min_latency" \
        --arg avgLatencyMs "$avg_latency" \
        --arg maxLatencyMs "$max_latency" \
        --arg latency95thPercentileMs "$percentile_latency" \
        --arg sumLatencyMs "$sum_latency" \
        '{
        node_id: $providerId,
        benchmark_name: $benchmarkName,
        threads: $threads,
        total_time_sec: $totalTimeSec,
        total_events: $totalEvents,
        events_per_second: $eventsPerSecond,
        min_latency_ms: $minLatencyMs,
        avg_latency_ms: $avgLatencyMs,
        max_latency_ms: $maxLatencyMs,
        latency_95th_percentile_ms: $latency95thPercentileMs,
        sum_latency_ms: $sumLatencyMs
    }')

    # Replace the empty JSON object with the new JSON object in the file
    echo "$result_json" >$output_file
}

# Run CPU Performance Test - Single-thread
single_thread_result=$(sysbench cpu --cpu-max-prime=20000 --time=30 run)
parse_and_write_output "CPU Single-thread Benchmark" 1 "$single_thread_result" $output_json_single 

# Run CPU Performance Test - Multi-thread
multi_thread_result=$(sysbench cpu --cpu-max-prime=20000 --time=30 --threads=$cpu_cores run)
parse_and_write_output "CPU Multi-thread Benchmark" $cpu_cores "$multi_thread_result" $output_json_multi

echo "Benchmarking completed. Single-thread results stored in $output_json_single"
echo "Benchmarking completed. Multi-thread results stored in $output_json_multi"
