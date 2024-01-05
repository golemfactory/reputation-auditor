from ninja import Schema

class ProviderSuccessRate(Schema):
    node_id: str
    success_rate: float

class DiskBenchmarkSchema(Schema):
    node_id: str
    benchmark_name: str
    reads_per_second: str
    writes_per_second: str
    fsyncs_per_second: str
    read_throughput_mb_ps: str
    write_throughput_mb_ps: str
    total_time_sec: str
    total_io_events: str
    min_latency_ms: str
    avg_latency_ms: str
    max_latency_ms: str
    latency_95th_percentile_ms: str


class CpuBenchmarkSchema(Schema):
    node_id: str
    benchmark_name: str
    threads: str
    total_time_sec: str
    total_events: str
    events_per_second: str
    min_latency_ms: str
    avg_latency_ms: str
    max_latency_ms: str
    latency_95th_percentile_ms: str
    sum_latency_ms: str



class MemoryBenchmarkSchema(Schema):
    node_id: str
    benchmark_name: str
    total_operations: str
    operations_per_second: str
    total_data_transferred_mi_b: str
    throughput_mi_b_sec: str
    total_time_sec: str
    total_events: str
    min_latency_ms: str
    avg_latency_ms: str
    max_latency_ms: str
    latency_95th_percentile_ms: str
    sum_latency_ms: str
    events: str
    execution_time_sec: str



class TaskCompletionSchema(Schema):
    node_id: str
    task_name: str
    is_successful: bool
    error_message: str = None