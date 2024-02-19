from django.db.models import Max, Min, Subquery, OuterRef
from .models import CpuBenchmark, MemoryBenchmark, DiskBenchmark, NetworkBenchmark

def get_network_benchmark_scores(provider, recent_n=3):
    benchmarks = get_recent_benchmarks(NetworkBenchmark.objects.filter(provider=provider), n=recent_n)
    if benchmarks.exists():
        network_speeds = benchmarks.order_by('-created_at').values_list('mbit_per_second', flat=True)[:recent_n]
        avg_network_speed = sum(network_speeds) / len(network_speeds)
        network_score = {"Download Speed (mbit/s)": avg_network_speed}
    else:
        network_score = {"Download Speed (mbit/s)": None}
        
    return network_score

def get_recent_benchmarks(queryset, n=3):
    return queryset.filter(
        id__in=Subquery(
            queryset.filter(provider=OuterRef('provider'))
            .order_by('-created_at')
            .values_list('id', flat=True)[:n]
        )
    )

def normalize_scores(provider, benchmark_set, benchmark_names, value_field_mapping, is_minimal_best=False, recent_n=3):
    normalized_scores = {}
    benchmark_set = get_recent_benchmarks(benchmark_set, n=recent_n)
    for readable_name, (benchmark_name, actual_value_field) in benchmark_names.items():
        benchmarks = benchmark_set.filter(provider=provider, benchmark_name=benchmark_name)
        if benchmarks.exists():
            field_max = Max(actual_value_field) if not is_minimal_best else Min(actual_value_field)
            field_min = Min(actual_value_field)
            benchmark_aggregates = benchmark_set.filter(benchmark_name=benchmark_name).aggregate(min_val=field_min, max_val=field_max)
            min_val = benchmark_aggregates['min_val']
            max_val = benchmark_aggregates['max_val']

            if max_val > min_val:
                for benchmark in benchmarks:
                    benchmark_value = getattr(benchmark, actual_value_field)
                    normalized_score = (benchmark_value - min_val) / (max_val - min_val)
                    normalized_scores[readable_name] = normalized_score
                    break  # assuming we only need one score per type for simplicity
            else:
                normalized_scores[readable_name] = None
        else:
            normalized_scores[readable_name] = None
            
    return normalized_scores

def get_provider_benchmark_scores(provider, recent_n=3):
    cpu_benchmark_names = {
        "Single-thread": ("CPU Single-thread Benchmark", 'events_per_second'),
        "Multi-thread": ("CPU Multi-thread Benchmark", 'events_per_second'),
    }

    memory_benchmark_names = {
        "Sequential Write Single-Thread": ("Sequential_Write_Performance__Single_Thread_", 'throughput_mi_b_sec'),
        "Sequential Read Single-Thread": ("Sequential_Read_Performance__Single_Thread_", 'throughput_mi_b_sec'),
        "Random Write Multi-threaded": ("Random_Write_Performance__Multi_threaded_", 'throughput_mi_b_sec'),
        "Random Read Multi-threaded": ("Random_Read_Performance__Multi_threaded_", 'throughput_mi_b_sec'),
        "Latency Random Read Single-Thread": ("Latency_Test__Random_Read__Single_Thread_", 'latency_95th_percentile_ms'),
    }

    disk_benchmark_names = {
        "Random Read": ("FileIO_rndrd", 'reads_per_second'),
        "Random Write": ("FileIO_rndwr", 'writes_per_second'),
        "Sequential Read": ("FileIO_seqrd", 'read_throughput_mb_ps'),
        "Sequential Write": ("FileIO_seqwr", 'write_throughput_mb_ps'),
    }

    network_benchmark_names = {
    "Network Throughput": ("Network Throughput Benchmark", 'mbit_per_second'),
}


    scores = {
        'cpu_scores': normalize_scores(provider, CpuBenchmark.objects.all(), cpu_benchmark_names, cpu_benchmark_names, recent_n=recent_n),
        'memory_scores': normalize_scores(provider, MemoryBenchmark.objects.all(), memory_benchmark_names, memory_benchmark_names, recent_n=recent_n),
        'disk_scores': normalize_scores(provider, DiskBenchmark.objects.all(), disk_benchmark_names, disk_benchmark_names, recent_n=recent_n),
        'network_scores': get_network_benchmark_scores(provider, recent_n=3),
    }

    

    return scores
