from ninja import NinjaAPI, Path
from .models import DiskBenchmark, CpuBenchmark, MemoryBenchmark, Provider, TaskCompletion, PingResult, NodeStatus, Task, Offer
from .schemas import DiskBenchmarkSchema, CpuBenchmarkSchema, MemoryBenchmarkSchema, TaskCompletionSchema, ProviderSuccessRate, TaskCreateSchema, TaskUpdateSchema, ProposalSchema, TaskCostUpdateSchema
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from typing import Any, Dict, List
import json
from collections import defaultdict
from django.db.models import Avg, Count, Q
from .tasks import benchmark_providers_task

api = NinjaAPI()
import redis




## We need to convert some of the incoming data to the correct type due to the fact that when we cat the results in the task script, they are all strings

@api.post("/benchmark/disk")
def create_disk_benchmark(request, data: DiskBenchmarkSchema):
    try:
        provider = get_object_or_404(Provider, node_id=data.node_id)
        benchmark = DiskBenchmark.objects.create(
            provider_id=provider.node_id,
            benchmark_name=data.benchmark_name,
            reads_per_second=float(data.reads_per_second),
            writes_per_second=float(data.writes_per_second),
            fsyncs_per_second=float(data.fsyncs_per_second),
            read_throughput_mb_ps=float(data.read_throughput_mb_ps),
            write_throughput_mb_ps=float(data.write_throughput_mb_ps),
            total_time_sec=float(data.total_time_sec),
            total_io_events=int(data.total_io_events),
            min_latency_ms=float(data.min_latency_ms),
            avg_latency_ms=float(data.avg_latency_ms),
            max_latency_ms=float(data.max_latency_ms),
            latency_95th_percentile_ms=float(data.latency_95th_percentile_ms)
        )
        return {"status": "success", "message": "Benchmark data saved successfully", "id": benchmark.id}
    except Exception as e:
        print(e)
        return {"status": "error", "message": "Error saving memory benchmark data",}

@api.post("/benchmark/cpu")
def create_cpu_benchmark(request, data: CpuBenchmarkSchema):
        
    try:
        provider = get_object_or_404(Provider, node_id=data.node_id)
        # Creates a new CpuBenchmark object and saves it
        benchmark = CpuBenchmark.objects.create(
            provider_id=provider.node_id,
            benchmark_name=data.benchmark_name,
            threads=int(data.threads),
            total_time_sec=data.total_time_sec.replace("s", ""),
            total_events=int(data.total_events),
            events_per_second=float(data.events_per_second),
            min_latency_ms=float(data.min_latency_ms),
            avg_latency_ms=float(data.avg_latency_ms),
            max_latency_ms=float(data.max_latency_ms),
            latency_95th_percentile_ms=float(data.latency_95th_percentile_ms),
            sum_latency_ms=float(data.sum_latency_ms)
        )
        return {"status": "success", "message": "CPU Benchmark data saved successfully", "id": benchmark.id}
    except Exception as e:
        print(e)
        return {"status": "error", "message": "Error saving memory benchmark data",}

@api.post("/benchmark/memory")
def create_memory_benchmark(request, data: MemoryBenchmarkSchema):
    try:
        provider = get_object_or_404(Provider, node_id=data.node_id)

        benchmark = MemoryBenchmark.objects.create(
            provider_id=provider.node_id,
            benchmark_name=data.benchmark_name,
            total_operations=int(data.total_operations),
            operations_per_second=float(data.operations_per_second),
            total_data_transferred_mi_b=float(data.total_data_transferred_mi_b),
            throughput_mi_b_sec=float(data.throughput_mi_b_sec),
            total_time_sec=float(data.total_time_sec),
            total_events=int(data.total_events),
            min_latency_ms=float(data.min_latency_ms),
            avg_latency_ms=float(data.avg_latency_ms),
            max_latency_ms=float(data.max_latency_ms),
            latency_95th_percentile_ms=float(data.latency_95th_percentile_ms),
            sum_latency_ms=float(data.sum_latency_ms),
            events=float(data.events),
            execution_time_sec=float(data.execution_time_sec)
        )
        return {"status": "success", "message": "Memory Benchmark data saved successfully",}
    except Exception as e:
        print(e)
        return {"status": "error", "message": "Error saving memory benchmark data",}
    

@api.post("/submit/task/status")
def create_task_completion(request, data: TaskCompletionSchema):
    try:
        provider = get_object_or_404(Provider, node_id=data.node_id)
        benchmark = TaskCompletion.objects.create(
            provider_id=provider.node_id,
            task_name=data.task_name,
            is_successful=data.is_successful,
            error_message=data.error_message,
            task=Task.objects.get(id=data.task_id)
            
        )
        return {"status": "success", "message": "Task completion data saved successfully",}
    except Exception as e:
        print(e)
        return {"status": "error", "message": "Error saving task completion data",}
    




@api.get("scores/task", response=List[ProviderSuccessRate])
def provider_success_rate(request):
    # Get all providers
    providers = Provider.objects.annotate(
        total_tasks=Count('taskcompletion'),
        successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True))
    )

    # Calculate success rate and prepare response
    success_rates = sorted(
        [
            {
                "node_id": provider.node_id,  # Unique Node ID
                "name": provider.name,  # Name of the provider
                "runtime_version": provider.runtime_version,  # Runtime Version
                "wallet_address": provider.payment_addresses,  # Wallet Address in JSON
                "success_rate": (provider.successful_tasks / provider.total_tasks * 100) if provider.total_tasks > 0 else 0  # Calculating success rate
            }
            for provider in providers
        ],
        key=lambda x: x["success_rate"],  # Sorting by success rate
        reverse=True  # Descending order
    )

    return success_rates

    
    



@api.get("/provider/{node_id}/scores", response=dict)
def get_provider_scores(request, node_id: str):
    try:
        provider = get_object_or_404(Provider, node_id=node_id)
        disk_benchmarks = (
            DiskBenchmark.objects.filter(provider=provider)
            .values("benchmark_name")
            .annotate(
                avg_read_throughput=Avg("read_throughput_mb_ps"),
                avg_write_throughput=Avg("write_throughput_mb_ps"),
                latency_95th_percentile=Avg("latency_95th_percentile_ms"),
            )[:5]
        )

        memory_benchmarks = (
            MemoryBenchmark.objects.filter(provider=provider)
            .values("benchmark_name")
            .annotate(
                avg_total_data_transferred=Avg("total_data_transferred_mi_b"),
                avg_throughput=Avg("throughput_mi_b_sec"),
                avg_latency_95th_percentile=Avg("latency_95th_percentile_ms"),
            )[:5]
        )

        cpu_benchmarks = (
            CpuBenchmark.objects.filter(provider=provider)
            .values("benchmark_name")
            .annotate(
                avg_events_per_second=Avg("events_per_second"),
                total_events=Avg("total_events"),
                threads=Avg("threads"),
            )[:5]
        )

        avg_ping = (
            PingResult.objects.filter(provider=provider)
            .aggregate(
                avg_ping_tcp=Avg("ping_tcp"),
                avg_ping_udp=Avg("ping_udp")
            )
        )

        uptime_percentage = (
            NodeStatus.objects.filter(provider=provider)
            .aggregate(uptime=Avg("uptime_percentage"))
            .get("uptime", 0)
        )
        task_counts = TaskCompletion.objects.filter(provider=provider).aggregate(
        total=Count('id'),
        successful=Count('id', filter=Q(is_successful=True)))

        success_rate = (task_counts['successful'] / task_counts['total'] * 100) if task_counts['total'] > 0 else 0

        disk_scores = [{"benchmark_name": db["benchmark_name"], "avg_read_throughput": db["avg_read_throughput"], 
                        "avg_write_throughput": db["avg_write_throughput"], "latency_95th_percentile": db["latency_95th_percentile"]} 
                        for db in disk_benchmarks]

        memory_scores = [{"benchmark_name": mb["benchmark_name"], "avg_total_data_transferred": mb["avg_total_data_transferred"], 
                        "avg_throughput": mb["avg_throughput"], "avg_latency_95th_percentile": mb["avg_latency_95th_percentile"]} 
                        for mb in memory_benchmarks]

        cpu_scores = [{"benchmark_name": cb["benchmark_name"], "avg_events_per_second": cb["avg_events_per_second"], 
                        "total_events": cb["total_events"], "threads": cb["threads"]} 
                    for cb in cpu_benchmarks]

        scores = {
            "disk": disk_scores,
            "memory": memory_scores,
            "cpu": cpu_scores,
            "ping": avg_ping,
            "uptime_percentage": uptime_percentage,
            "task_success_rate": success_rate
        }

        return scores
    except Exception as e:
        print(e)
        return {"status": "error", "message": "Error retrieving provider scores",}
    

from django.utils import timezone
from django.utils import timezone
from datetime import timedelta
from django.db.models import Subquery, OuterRef

@api.get("/blacklisted-providers", response=List[str])
def blacklisted_providers(request):
    now = timezone.now()

    # Subquery to get the most recent tasks for each provider
    recent_tasks = TaskCompletion.objects.filter(
        provider=OuterRef('node_id')
    ).order_by('-timestamp')

    # Annotate each provider with its most recent tasks
    providers_with_tasks = Provider.objects.annotate(
        recent_task=Subquery(recent_tasks.values('is_successful')[:1])
    )

    # Filter providers whose most recent task was a failure
    failed_providers = providers_with_tasks.filter(recent_task=False)

    blacklisted_providers = []
    for provider in failed_providers:
        consecutive_failures = TaskCompletion.objects.filter(
            provider=provider.node_id,
            is_successful=False,
            timestamp__gte=now - timedelta(days=3)  # Assuming we look at the last 3 days
        ).count()

        # Apply a cap to the consecutive_failures
        max_consecutive_failures = 6  # Maximum failures to keep backoff within 14 days
        effective_failures = min(consecutive_failures, max_consecutive_failures)

        backoff_hours = 10 * (2 ** (effective_failures - 1))  # Exponential backoff formula
        next_eligible_date = provider.taskcompletion_set.latest('timestamp').timestamp + timedelta(hours=backoff_hours)

        if now < next_eligible_date:
            blacklisted_providers.append(provider.node_id)

    return blacklisted_providers


@api.post("/task/start")
def start_task(request, payload: TaskCreateSchema):
    task = Task.objects.create(name=payload.name, started_at=timezone.now())
    return {"id": task.id, "name": task.name, "started_at": task.started_at}

@api.post("/task/end/{task_id}")
def end_task(request, task_id: int, cost: float):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Task does not exist"}, status=404)
    task.finished_at = timezone.now()
    task.cost = cost
    task.save()
    return {"id": task.id, "finished_at": task.finished_at}

from django.shortcuts import get_object_or_404

@api.post("/task/update-cost/{task_id}")
def update_task_cost(request, task_id: int, payload: TaskCostUpdateSchema):
    try:
        # Directly fetch the TaskCompletion instance with related Task and Provider
        task_completion = get_object_or_404(
            TaskCompletion.objects.select_related('provider', 'task'),
            provider__node_id=payload.provider_id,  # Assuming node_id is the field in Provider model
            task_id=task_id
        )

        # Update the cost
        task_completion.cost = payload.cost
        task_completion.save()

        return JsonResponse({"status": "success", "message": "Task cost updated successfully"})

    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Task not found"}, status=404)
    except Provider.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Provider not found"}, status=404)
    except Exception as e:
        # Log the exception for debugging
        print(e)
        return JsonResponse({"status": "error", "message": "An error occurred"}, status=500)




redis_client = redis.Redis(host='redis', port=6379, db=0)  # Update with your Redis configuration

@api.post("/task/offer/{task_id}")
def store_offer(request, task_id: int):
    try:
        json_data = json.loads(request.body)
        node_id = json_data.get('node_id')
        offer = json_data.get('offer')

        if not node_id or offer is None:
            return JsonResponse({"status": "error", "error": "Missing node_id or offer"}, status=400)

        # Create a unique key for Redis, e.g., using task ID and node ID
        redis_key = f"offer:{task_id}:{node_id}"
        redis_client.set(redis_key, json.dumps(offer))
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)

    return JsonResponse({"status": "success", "error": "Offer stored in Redis"})


@api.get("/benchmark")
def start_benchmark(request, ):
    benchmark_providers_task.delay()
    return {"status": "ok"}