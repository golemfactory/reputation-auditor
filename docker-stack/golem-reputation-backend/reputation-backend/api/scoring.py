from django.db.models import Max, Avg
from .models import CpuBenchmark
from django.db.models.functions.window import PercentRank
from django.db.models.expressions import Window
from django.db.models.functions import Now
from django.db.models import Sum, F
from django.db.models import Max, Min, Subquery, OuterRef
from .models import CpuBenchmark, MemoryBenchmark, DiskBenchmark, NetworkBenchmark, Provider, NodeStatusHistory
from datetime import timedelta
from django.utils import timezone

# Function to determine penalty weight based on deviation


def penalty_weight(deviation):
    if deviation <= 5:
        return 1.0  # No penalty
    elif 5 < deviation <= 15:
        return 0.7  # Small penalty
    else:
        return 0.4  # Larger penalty



def calculate_uptime(node_id, node=None):
    if node is None:
        node = Provider.objects.get(node_id=node_id)
    statuses = NodeStatusHistory.objects.filter(provider=node).order_by("timestamp")

    online_duration = timedelta(0)
    last_online_time = None

    for status in statuses:
        if status.is_online:
            last_online_time = status.timestamp
        elif last_online_time:
            online_duration += status.timestamp - last_online_time
            last_online_time = None

    # Check if the node is currently online and add the duration
    if last_online_time is not None:
        online_duration += timezone.now() - last_online_time

    total_duration = timezone.now() - node.created_at
    uptime_percentage = (
        online_duration.total_seconds() / total_duration.total_seconds()
    ) * 100
    return uptime_percentage


def get_network_benchmark_scores(provider, recent_n=3):
    benchmarks = get_recent_benchmarks(
        NetworkBenchmark.objects.filter(provider=provider), n=recent_n)
    if benchmarks.exists():
        network_speeds = benchmarks.order_by(
            '-created_at').values_list('mbit_per_second', flat=True)[:recent_n]
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
        benchmarks = benchmark_set.filter(
            provider=provider, benchmark_name=benchmark_name)
        if benchmarks.exists():
            field_max = Max(actual_value_field) if not is_minimal_best else Min(
                actual_value_field)
            field_min = Min(actual_value_field)
            benchmark_aggregates = benchmark_set.filter(
                benchmark_name=benchmark_name).aggregate(min_val=field_min, max_val=field_max)
            min_val = benchmark_aggregates['min_val']
            max_val = benchmark_aggregates['max_val']

            if max_val > min_val:
                for benchmark in benchmarks:
                    benchmark_value = getattr(benchmark, actual_value_field)
                    normalized_score = (
                        benchmark_value - min_val) / (max_val - min_val)
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


def get_normalized_cpu_scores():
    # Get the maximum events_per_second for single and multi-thread benchmarks
    max_single_thread_eps = CpuBenchmark.objects.filter(
        benchmark_name="CPU Single-thread Benchmark").aggregate(Max('events_per_second'))['events_per_second__max']
    max_multi_thread_eps = CpuBenchmark.objects.filter(
        benchmark_name="CPU Multi-thread Benchmark").aggregate(Max('events_per_second'))['events_per_second__max']

    # Get all providers
    providers = Provider.objects.all()

    # Get the latest 5 benchmarks for each provider and benchmark type
    latest_benchmarks = CpuBenchmark.objects.filter(
        benchmark_name__in=["CPU Single-thread Benchmark",
                            "CPU Multi-thread Benchmark"]
    ).order_by('provider', 'benchmark_name', '-id')

    # Create a dictionary to store the latest 5 benchmarks for each provider and benchmark type
    latest_benchmarks_dict = {}
    for benchmark in latest_benchmarks:
        key = (benchmark.provider_id, benchmark.benchmark_name)
        if key not in latest_benchmarks_dict:
            latest_benchmarks_dict[key] = []
        if len(latest_benchmarks_dict[key]) < 5:
            latest_benchmarks_dict[key].append(benchmark)

    # Calculate average performance for the latest 5 benchmarks
    avg_benchmarks_dict = {}
    for key, benchmarks in latest_benchmarks_dict.items():
        avg_events_per_second = sum(
            b.events_per_second for b in benchmarks) / len(benchmarks)
        avg_benchmarks_dict[key] = avg_events_per_second

    cpu_scores = {}

    # Process each provider
    for provider in providers:
        single_thread_key = (provider.node_id, "CPU Single-thread Benchmark")
        multi_thread_key = (provider.node_id, "CPU Multi-thread Benchmark")

        single_thread_benchmarks = latest_benchmarks_dict.get(
            single_thread_key, [])
        multi_thread_benchmarks = latest_benchmarks_dict.get(
            multi_thread_key, [])

        single_thread_score_obj = single_thread_benchmarks[0] if single_thread_benchmarks else None
        multi_thread_score_obj = multi_thread_benchmarks[0] if multi_thread_benchmarks else None

        avg_latest_single_thread_eps = avg_benchmarks_dict.get(
            single_thread_key, 0)
        avg_latest_multi_thread_eps = avg_benchmarks_dict.get(
            multi_thread_key, 0)

        # Calculate deviations based on the latest 5 benchmark averages
        single_thread_deviation = abs(single_thread_score_obj.events_per_second - avg_latest_single_thread_eps) / \
            avg_latest_single_thread_eps * \
            100 if single_thread_score_obj and avg_latest_single_thread_eps else 0
        multi_thread_deviation = abs(multi_thread_score_obj.events_per_second - avg_latest_multi_thread_eps) / \
            avg_latest_multi_thread_eps * \
            100 if multi_thread_score_obj and avg_latest_multi_thread_eps else 0

        # Apply penalty weights
        single_thread_penalty_weight = penalty_weight(single_thread_deviation)
        multi_thread_penalty_weight = penalty_weight(multi_thread_deviation)

        # Normalize scores and apply penalties
        cpu_scores[provider.node_id] = {
            "single_thread_score": (single_thread_score_obj.events_per_second / max_single_thread_eps) * single_thread_penalty_weight if single_thread_score_obj else 0,
            "multi_thread_score": (multi_thread_score_obj.events_per_second / max_multi_thread_eps) * multi_thread_penalty_weight if multi_thread_score_obj else 0
        }

    return cpu_scores


# GNV replacement

def get_top_80_percent_cpu_multithread_providers(maxCheckedDaysAgo=3, topPercent=80):
    # Filter benchmarks based on the last N days and by multi-thread benchmark
    recent_benchmarks = CpuBenchmark.objects.filter(
        created_at__gte=Now() - timedelta(days=maxCheckedDaysAgo),
        benchmark_name__icontains='multi-thread'  # Adjust based on your actual naming
    ).values('provider_id').annotate(
        total_score=Sum('events_per_second')
    ).order_by('-total_score')

    # Calculate the index for the 80th percentile cutoff
    count = len(recent_benchmarks)
    cutoff_index = int(count * (topPercent / 100)) - \
        1  # Adjust the cutoff to get the top 80%

    # Get the total scores as a list and find the cutoff score
    total_scores = list(
        recent_benchmarks.values_list('total_score', flat=True))
    if total_scores:  # Ensure the list is not empty
        cutoff_score = total_scores[cutoff_index]

        # Filter providers by score, comparing against the cutoff score
        top_providers = [benchmark['provider_id']
                         for benchmark in recent_benchmarks if benchmark['total_score'] >= cutoff_score]
    else:
        top_providers = []

    return top_providers
