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

    benchmarks = []

    single_benchmark = CpuBenchmark.objects.filter(
        provider=provider, benchmark_name="CPU Single-thread Benchmark").order_by('-created_at').first()
    multi_benchmark = CpuBenchmark.objects.filter(
        provider=provider, benchmark_name="CPU Multi-thread Benchmark").order_by('-created_at').first()

    if single_benchmark and multi_benchmark:
        benchmarks.append(BenchmarkSchema(
            timestamp=int(single_benchmark.created_at.timestamp()),
            singleThread=single_benchmark.events_per_second,
            multiThread=multi_benchmark.events_per_second
        ))

    avg_dev_single = CpuBenchmark.objects.filter(benchmark_name="CPU Single-thread Benchmark").aggregate(
        Avg('events_per_second'), StdDev('events_per_second'))
    avg_dev_multi = CpuBenchmark.objects.filter(benchmark_name="CPU Multi-thread Benchmark").aggregate(
        Avg('events_per_second'), StdDev('events_per_second'))

    single_deviation = (avg_dev_single['events_per_second__stddev'] / avg_dev_single['events_per_second__avg']) * 100 if avg_dev_single['events_per_second__avg'] else 0
    multi_deviation = (avg_dev_multi['events_per_second__stddev'] / avg_dev_multi['events_per_second__avg']) * 100 if avg_dev_multi['events_per_second__avg'] else 0

    response = BenchmarkResponse(
        benchmarks=benchmarks,
        singleDeviation=single_deviation,
        multiDeviation=multi_deviation
    )

    return response

from .schemas import MemoryBenchmarkResponse, SequentialBenchmarkSchema, RandomBenchmarkSchema
@api.get("/memory/benchmark/{node_id}", response=MemoryBenchmarkResponse)
def get_memory_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return {"detail": "Provider not found"}

    sequential_benchmarks, random_benchmarks = [], []

    benchmarks = {
        "Sequential_Write_Performance__Single_Thread_": None,
        "Sequential_Read_Performance__Single_Thread_": None,
        "Random_Write_Performance__Multi_threaded_": None,
        "Random_Read_Performance__Multi_threaded_": None
    }

    for bm_name in benchmarks.keys():
        benchmarks[bm_name] = MemoryBenchmark.objects.filter(
            provider=provider, benchmark_name=bm_name).order_by('-created_at').first()

    if benchmarks["Sequential_Write_Performance__Single_Thread_"] and benchmarks["Sequential_Read_Performance__Single_Thread_"]:
        sequential_benchmarks.append(SequentialBenchmarkSchema(
            timestamp=int(benchmarks["Sequential_Write_Performance__Single_Thread_"].created_at.timestamp()),
            writeSingleThread=benchmarks["Sequential_Write_Performance__Single_Thread_"].throughput_mi_b_sec,
            readSingleThread=benchmarks["Sequential_Read_Performance__Single_Thread_"].throughput_mi_b_sec
        ))

    if benchmarks["Random_Write_Performance__Multi_threaded_"] and benchmarks["Random_Read_Performance__Multi_threaded_"]:
        random_benchmarks.append(RandomBenchmarkSchema(
            timestamp=int(benchmarks["Random_Write_Performance__Multi_threaded_"].created_at.timestamp()),
            writeMultiThread=benchmarks["Random_Write_Performance__Multi_threaded_"].throughput_mi_b_sec,
            readMultiThread=benchmarks["Random_Read_Performance__Multi_threaded_"].throughput_mi_b_sec
        ))

    deviation_fields = {
        "sequentialWriteDeviation": "Sequential_Write_Performance__Single_Thread_",
        "sequentialReadDeviation": "Sequential_Read_Performance__Single_Thread_",
        "randomWriteDeviation": "Random_Write_Performance__Multi_threaded_",
        "randomReadDeviation": "Random_Read_Performance__Multi_threaded_"
    }
    deviations = {field: calculate_deviation(bm_name) for field, bm_name in deviation_fields.items()}

    return MemoryBenchmarkResponse(
        sequentialBenchmarks=sequential_benchmarks,
        randomBenchmarks=random_benchmarks,
        **deviations
    )

def calculate_deviation(benchmark_name):
    avg_dev = MemoryBenchmark.objects.filter(benchmark_name=benchmark_name).aggregate(
        Avg('throughput_mi_b_sec'), StdDev('throughput_mi_b_sec'))
    deviation = (avg_dev['throughput_mi_b_sec__stddev'] / avg_dev['throughput_mi_b_sec__avg']) * 100 if avg_dev['throughput_mi_b_sec__avg'] else None
    return deviation

from .schemas import DiskBenchmarkResponse, SequentialDiskBenchmarkSchema, RandomDiskBenchmarkSchema

from django.db.models import Avg, StdDev

@api.get("/disk/benchmark/{node_id}", response=DiskBenchmarkResponse)
def get_disk_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return {"detail": "Provider not found"}

    benches = {
        "FileIO_seqrd": DiskBenchmark.objects.filter(
            provider=provider, benchmark_name="FileIO_seqrd").order_by('-created_at').first(),
        "FileIO_seqwr": DiskBenchmark.objects.filter(
            provider=provider, benchmark_name="FileIO_seqwr").order_by('-created_at').first(),
        "FileIO_rndrd": DiskBenchmark.objects.filter(
            provider=provider, benchmark_name="FileIO_rndrd").order_by('-created_at').first(),
        "FileIO_rndwr": DiskBenchmark.objects.filter(
            provider=provider, benchmark_name="FileIO_rndwr").order_by('-created_at').first(),
    }

    sequentialDiskBenchmarks, randomDiskBenchmarks = [], []

    if benches["FileIO_seqrd"] and benches["FileIO_seqwr"]:
        sequentialDiskBenchmarks = [SequentialDiskBenchmarkSchema(
            timestamp=int(benches["FileIO_seqrd"].created_at.timestamp()),
            readThroughput=benches["FileIO_seqrd"].read_throughput_mb_ps,
            writeThroughput=benches["FileIO_seqwr"].write_throughput_mb_ps
        )]

    if benches["FileIO_rndrd"] and benches["FileIO_rndwr"]:
        randomDiskBenchmarks = [RandomDiskBenchmarkSchema(
            timestamp=int(benches["FileIO_rndrd"].created_at.timestamp()),
            readThroughput=benches["FileIO_rndrd"].read_throughput_mb_ps,
            writeThroughput=benches["FileIO_rndwr"].write_throughput_mb_ps
        )]

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