from ninja import NinjaAPI, Path
from api.models import Provider, TaskCompletion, MemoryBenchmark, DiskBenchmark, CpuBenchmark
from .schemas import ResponseSchema
from django.db.models import Avg, Max, Min, F, Q, StdDev
from datetime import timedelta
from django.utils import timezone
from collections import defaultdict
from typing import Optional



api = NinjaAPI(
    title="Golem Reputation Stats API",
    version="1.0.0",
    description="Stats API",
    urls_namespace="stats",
)


@api.get("/tasks/{provider_id}", response=ResponseSchema)
def get_tasks_for_provider(request, provider_id: str = Path(...)):
    try:
        provider = Provider.objects.get(node_id=provider_id)
    except Provider.DoesNotExist:
        return api.create_response(request, {"message": "Provider not found"}, status=404)

    tasks = TaskCompletion.objects.filter(provider=provider).order_by('-timestamp')

    total_tasks = tasks.count()
    successful_tasks = tasks.filter(is_successful=True).count()
    success_ratio = (successful_tasks / total_tasks * 100) if total_tasks > 0 else 0

    response_data = {
        "successRatio": success_ratio,
        "tasks": [{
            "date": task.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "successful": task.is_successful,
            "taskName": task.task_name,
            "errorMessage": task.error_message or ""
        } for task in tasks]
    }

    return response_data


def calculate_deviation_for_benchmarks(benchmark_queryset, benchmark_name_field, score_field):
    results = defaultdict(dict)
    for benchmark in benchmark_queryset:
        benchmark_name = getattr(benchmark, benchmark_name_field)
        max_score = benchmark_queryset.filter(**{benchmark_name_field: benchmark_name}).aggregate(Max(score_field))[f'{score_field}__max']
        min_score = benchmark_queryset.filter(**{benchmark_name_field: benchmark_name}).aggregate(Min(score_field))[f'{score_field}__min']
        
        if max_score and min_score and max_score != 0:
            deviation = ((max_score - min_score) / max_score) * 100
        else:
            deviation = None
        
        results[benchmark_name]["deviation"] = deviation
        results[benchmark_name]["latest_score"] = getattr(benchmark, score_field)
    
    return results

@api.get("/provider/{node_id}/detailed_performance_deviation")
def provider_detailed_performance_deviation(request, node_id: str = Path(...)):
    three_days_ago = timezone.now() - timedelta(days=3)
    provider = Provider.objects.get(node_id=node_id)
    results = {}

    # Memory Benchmark Deviation and Latest Score
    memory_benchmarks = MemoryBenchmark.objects.filter(provider=provider, created_at__gte=three_days_ago)
    memory_results = {}
    for benchmark in memory_benchmarks:
        benchmark_scores = MemoryBenchmark.objects.filter(provider=provider, benchmark_name=benchmark.benchmark_name, created_at__gte=three_days_ago).values_list('throughput_mi_b_sec', flat=True)
        max_score = max(benchmark_scores, default=0)
        min_score = min(benchmark_scores, default=0)
        deviation = ((max_score - min_score) / max_score) * 100 if max_score != 0 else 0
        memory_results[benchmark.benchmark_name] = {"deviation": deviation, "latest_score": benchmark.throughput_mi_b_sec}
    results['memory_deviation'] = memory_results

    # Disk Benchmark Deviation and Latest Score
    disk_benchmarks = DiskBenchmark.objects.filter(provider=provider, created_at__gte=three_days_ago)
    disk_results = {}
    for benchmark in disk_benchmarks:
        benchmark_scores = DiskBenchmark.objects.filter(provider=provider, benchmark_name=benchmark.benchmark_name, created_at__gte=three_days_ago).values_list('reads_per_second', 'writes_per_second')
        max_score = max(max(scores) for scores in benchmark_scores) if benchmark_scores else 0
        min_score = min(min(scores) for scores in benchmark_scores) if benchmark_scores else 0
        deviation = ((max_score - min_score) / max_score) * 100 if max_score != 0 else 0
        disk_results[benchmark.benchmark_name] = {"reads_deviation": deviation, "latest_reads": benchmark.reads_per_second, "writes_deviation": deviation, "latest_writes": benchmark.writes_per_second}
    results['disk_deviation'] = disk_results

    # CPU Benchmark Deviation and Latest Score
    cpu_benchmarks = CpuBenchmark.objects.filter(provider=provider, created_at__gte=three_days_ago)
    print(cpu_benchmarks)
    cpu_results = {}
    for benchmark in cpu_benchmarks:
        benchmark_scores = CpuBenchmark.objects.filter(provider=provider, benchmark_name=benchmark.benchmark_name, created_at__gte=three_days_ago).values_list('events_per_second', flat=True)
        max_score = max(benchmark_scores, default=0)
        min_score = min(benchmark_scores, default=0)
        deviation = ((max_score - min_score) / max_score) * 100 if max_score != 0 else 0
        cpu_results[benchmark.benchmark_name] = {"deviation": deviation, "latest_score": benchmark.events_per_second}
    results['cpu_deviation'] = cpu_results

    return results




from .schemas import BenchmarkResponse, BenchmarkSchema

@api.get("/benchmark/{node_id}", response=BenchmarkResponse)
def get_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return {"detail": "Provider not found"}

    single_benchmarks = CpuBenchmark.objects.filter(
        provider=provider, benchmark_name="CPU Single-thread Benchmark"
    ).order_by('-created_at')

    multi_benchmarks = CpuBenchmark.objects.filter(
        provider=provider, benchmark_name="CPU Multi-thread Benchmark"
    ).order_by('-created_at')

    benchmarks = [
        BenchmarkSchema(
            timestamp=int(bench.created_at.timestamp()),
            singleThread=bench.events_per_second if bench.benchmark_name == "CPU Single-thread Benchmark" else None,
            multiThread=bench.events_per_second if bench.benchmark_name == "CPU Multi-thread Benchmark" else None
        ) for bench in single_benchmarks.union(multi_benchmarks)
    ]

    def calculate_deviation(benchmark_name):
        avg_dev = CpuBenchmark.objects.filter(provider=provider, benchmark_name=benchmark_name).aggregate(
            Avg('events_per_second'), StdDev('events_per_second'))
        return (avg_dev['events_per_second__stddev'] / avg_dev['events_per_second__avg'] * 100
                if avg_dev['events_per_second__avg'] and avg_dev['events_per_second__stddev'] else None)

    single_deviation = calculate_deviation("CPU Single-thread Benchmark")
    multi_deviation = calculate_deviation("CPU Multi-thread Benchmark")

    return BenchmarkResponse(
        benchmarks=benchmarks,
        singleDeviation=single_deviation or 0,
        multiDeviation=multi_deviation or 0
    )

from .schemas import MemoryBenchmarkResponse, SequentialBenchmarkSchema, RandomBenchmarkSchema
@api.get("/memory/benchmark/{node_id}", response=MemoryBenchmarkResponse)
def get_memory_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return {"detail": "Provider not found"}

    seq_write_benches = MemoryBenchmark.objects.filter(
        provider=provider, benchmark_name="Sequential_Write_Performance__Single_Thread_"
    ).order_by('-created_at')

    seq_read_benches = MemoryBenchmark.objects.filter(
        provider=provider, benchmark_name="Sequential_Read_Performance__Single_Thread_"
    ).order_by('-created_at')

    rand_write_benches = MemoryBenchmark.objects.filter(
        provider=provider, benchmark_name="Random_Write_Performance__Multi_threaded_"
    ).order_by('-created_at')

    rand_read_benches = MemoryBenchmark.objects.filter(
        provider=provider, benchmark_name="Random_Read_Performance__Multi_threaded_"
    ).order_by('-created_at')

    sequential_benchmarks = [
        SequentialBenchmarkSchema(
            timestamp=int(bench.created_at.timestamp()),
            writeSingleThread=bench.throughput_mi_b_sec if "Write" in bench.benchmark_name else None,
            readSingleThread=bench.throughput_mi_b_sec if "Read" in bench.benchmark_name else None
        ) for bench in (seq_write_benches | seq_read_benches).distinct()
    ]

    random_benchmarks = [
        RandomBenchmarkSchema(
            timestamp=int(bench.created_at.timestamp()),
            writeMultiThread=bench.throughput_mi_b_sec if "Write" in bench.benchmark_name else None,
            readMultiThread=bench.throughput_mi_b_sec if "Read" in bench.benchmark_name else None
        ) for bench in (rand_write_benches | rand_read_benches).distinct()
    ]

    def calculate_deviation(benchmark_name):
        avg_dev = MemoryBenchmark.objects.filter(provider=provider, benchmark_name=benchmark_name).aggregate(
            Avg('throughput_mi_b_sec'), StdDev('throughput_mi_b_sec'))
        return (avg_dev['throughput_mi_b_sec__stddev'] / avg_dev['throughput_mi_b_sec__avg'] * 100
                if avg_dev['throughput_mi_b_sec__avg'] and avg_dev['throughput_mi_b_sec__stddev'] else None)

    deviations = {field: calculate_deviation(bm_name) for field, bm_name in
                  {
                      "sequentialWriteDeviation": "Sequential_Write_Performance__Single_Thread_",
                      "sequentialReadDeviation": "Sequential_Read_Performance__Single_Thread_",
                      "randomWriteDeviation": "Random_Write_Performance__Multi_threaded_",
                      "randomReadDeviation": "Random_Read_Performance__Multi_threaded_"
                  }.items()}

    return MemoryBenchmarkResponse(
        sequentialBenchmarks=sequential_benchmarks,
        randomBenchmarks=random_benchmarks,
        **deviations
    )

from .schemas import DiskBenchmarkResponse, SequentialDiskBenchmarkSchema, RandomDiskBenchmarkSchema

from django.db.models import Avg, StdDev

@api.get("/disk/benchmark/{node_id}", response=DiskBenchmarkResponse)
def get_disk_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return {"detail": "Provider not found"}

    seq_benches = DiskBenchmark.objects.filter(
        provider=provider, benchmark_name__in=["FileIO_seqrd", "FileIO_seqwr"]
    ).order_by('-created_at')

    rand_benches = DiskBenchmark.objects.filter(
        provider=provider, benchmark_name__in=["FileIO_rndrd", "FileIO_rndwr"]
    ).order_by('-created_at')

    sequentialDiskBenchmarks = [
        SequentialDiskBenchmarkSchema(
            timestamp=int(bench.created_at.timestamp()),
            readThroughput=bench.read_throughput_mb_ps if "seqrd" in bench.benchmark_name else None,
            writeThroughput=bench.write_throughput_mb_ps if "seqwr" in bench.benchmark_name else None
        )
        for bench in seq_benches
    ]

    randomDiskBenchmarks = [
        RandomDiskBenchmarkSchema(
            timestamp=int(bench.created_at.timestamp()),
            readThroughput=bench.read_throughput_mb_ps if "rndrd" in bench.benchmark_name else None,
            writeThroughput=bench.write_throughput_mb_ps if "rndwr" in bench.benchmark_name else None
        )
        for bench in rand_benches
    ]

    def calculate_disk_deviation(provider, benchmark_name):
        avg_dev = DiskBenchmark.objects.filter(provider=provider, benchmark_name=benchmark_name).aggregate(
            Avg('read_throughput_mb_ps'), StdDev('read_throughput_mb_ps'))
        return (avg_dev['read_throughput_mb_ps__stddev'] / avg_dev['read_throughput_mb_ps__avg'] * 100
                if avg_dev['read_throughput_mb_ps__avg'] and avg_dev['read_throughput_mb_ps__stddev'] else None)

    deviations = {field: calculate_disk_deviation(provider, bm_name) for field, bm_name in
                  {"sequentialReadDeviation": "FileIO_seqrd",
                   "sequentialWriteDeviation": "FileIO_seqwr",
                   "randomReadDeviation": "FileIO_rndrd",
                   "randomWriteDeviation": "FileIO_rndwr"}.items()}

    return DiskBenchmarkResponse(
        sequentialDiskBenchmarks=sequentialDiskBenchmarks,
        randomDiskBenchmarks=randomDiskBenchmarks,
        **deviations
    )