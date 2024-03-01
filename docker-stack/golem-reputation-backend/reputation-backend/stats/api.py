from ninja import NinjaAPI, Path
from api.models import Provider, TaskCompletion, MemoryBenchmark, DiskBenchmark, CpuBenchmark
from .schemas import ResponseSchema
from django.db.models import Avg, Max, Min, F, Q
from datetime import timedelta
from django.utils import timezone
from collections import defaultdict


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