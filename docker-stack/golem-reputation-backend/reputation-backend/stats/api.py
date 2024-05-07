from ninja import NinjaAPI, Path
from api.models import Provider, TaskCompletion, MemoryBenchmark, DiskBenchmark, CpuBenchmark, NetworkBenchmark, Offer
from .schemas import OfferHistorySchema, TaskParticipationSchema, ProviderDetailsResponseSchema
from typing import List
from django.utils import timezone
from api.scoring import penalty_weight


api = NinjaAPI(
    title="Golem Reputation Stats API",
    version="1.0.0",
    description="Stats API",
    urls_namespace="stats",
)

def get_summary(deviation):
    if deviation <= 5:
        return "stable"
    elif deviation <= 15:
        return "varying"
    return "unstable"



def calculate_deviation(scores):
    if not scores:
        return 0
    avg = sum(scores) / len(scores)
    deviation_percent = sum((score - avg) ** 2 for score in scores) ** 0.5 / len(scores) ** 0.5 / avg * 100
    return deviation_percent





from django.db.models import Avg, StdDev
from django.db.models import Case, When, Value, CharField
from django.db.models.functions import Cast
from django.db.models import Value as V
from django.db.models import FloatField
from django.http import JsonResponse


@api.get("/benchmark/cpu/{node_id}")
def get_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)
    
    benchmarks = CpuBenchmark.objects.filter(provider=provider).values(
        'benchmark_name', 'events_per_second', 'created_at'
    )
    result = {"data": {"single": [], "multi": []}, "singleDeviation": 0, "multiDeviation": 0, "summary": ""}
    single_scores, multi_scores = [], []

    for benchmark in benchmarks:
        score_entry = {"score": benchmark['events_per_second'], "timestamp": benchmark['created_at'].timestamp()}
        if "Single-thread" in benchmark['benchmark_name']:
            result["data"]["single"].append(score_entry)
            single_scores.append(benchmark['events_per_second'])
        else:
            result["data"]["multi"].append(score_entry)
            multi_scores.append(benchmark['events_per_second'])


    result['singleDeviation'] = calculate_deviation(single_scores)
    result['multiDeviation'] = calculate_deviation(multi_scores)



    result['summary'] = {
        "single": get_summary(result['singleDeviation']),
        "multi": get_summary(result['multiDeviation'])
    }

    return JsonResponse(result)


@api.get("/benchmark/memory/seq/single/{node_id}")
def get_seq_memory_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)
    
    benchmarks = MemoryBenchmark.objects.filter(
        provider=provider, 
        benchmark_name__in=[
            "Sequential_Write_Performance__Single_Thread_", 
            "Sequential_Read_Performance__Single_Thread_"
        ]).values('benchmark_name', 'throughput_mi_b_sec', 'created_at')

    result = {"data": {"sequential_write_single": [], "sequential_read_single": []}, "writeDeviation": 0, "readDeviation": 0, "summary": ""}
    write_scores, read_scores = [], []
    
    for benchmark in benchmarks:
        score_entry = {"score": benchmark['throughput_mi_b_sec'], "timestamp": benchmark['created_at'].timestamp()}
        if "Write" in benchmark['benchmark_name']:
            result["data"]["sequential_write_single"].append(score_entry)
            write_scores.append(benchmark['throughput_mi_b_sec'])
        else:
            result["data"]["sequential_read_single"].append(score_entry)
            read_scores.append(benchmark['throughput_mi_b_sec'])

    result['writeDeviation'] = calculate_deviation(write_scores)
    result['readDeviation'] = calculate_deviation(read_scores)

    result['summary'] = {
        "sequential_write_single": get_summary(result['writeDeviation']),
        "sequential_read_single": get_summary(result['readDeviation'])
    }
    
    return JsonResponse(result)


@api.get("/benchmark/memory/rand/multi/{node_id}")
def get_rand_memory_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = MemoryBenchmark.objects.filter(
        provider=provider, 
        benchmark_name__in=[
            "Random_Write_Performance__Multi_threaded_", 
            "Random_Read_Performance__Multi_threaded_"
        ]).values('benchmark_name', 'throughput_mi_b_sec', 'created_at')

    result = {
        "data": {
            "random_write_multi": [], 
            "random_read_multi": []
        }, 
        "writeDeviation": 0, 
        "readDeviation": 0, 
        "summary": ""
    }
    write_scores, read_scores = [], []

    for benchmark in benchmarks:
        score_entry = {"score": benchmark['throughput_mi_b_sec'], "timestamp": benchmark['created_at'].timestamp()}
        if "Write" in benchmark['benchmark_name']:
            result["data"]["random_write_multi"].append(score_entry)
            write_scores.append(benchmark['throughput_mi_b_sec'])
        else:
            result["data"]["random_read_multi"].append(score_entry)
            read_scores.append(benchmark['throughput_mi_b_sec'])

    result['writeDeviation'] = calculate_deviation(write_scores)
    result['readDeviation'] = calculate_deviation(read_scores)

    result['summary'] = {
        "random_write_multi": get_summary(result['writeDeviation']),
        "random_read_multi": get_summary(result['readDeviation'])
    }
    
    return JsonResponse(result)

@api.get("/benchmark/disk/fileio_rand/{node_id}")
def get_fileio_disk_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = DiskBenchmark.objects.filter(
        provider=provider, 
        benchmark_name__in=["FileIO_rndrd", "FileIO_rndwr"]
    ).values('benchmark_name', 'read_throughput_mb_ps', 'write_throughput_mb_ps', 'created_at')

    result = {
        "data": {
            "fileio_rndrd": [], 
            "fileio_rndwr": []
        }, 
        "readDeviation": 0, 
        "writeDeviation": 0, 
        "summary": ""
    }
    read_scores, write_scores = [], []

    for benchmark in benchmarks:
        if "rndrd" in benchmark['benchmark_name']:
            score_entry = {"score": benchmark['read_throughput_mb_ps'], "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_rndrd"].append(score_entry)
            read_scores.append(benchmark['read_throughput_mb_ps'])
        else:
            score_entry = {"score": benchmark['write_throughput_mb_ps'], "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_rndwr"].append(score_entry)
            write_scores.append(benchmark['write_throughput_mb_ps'])

    result['readDeviation'] = calculate_deviation(read_scores)
    result['writeDeviation'] = calculate_deviation(write_scores)

    result['summary'] = {
        "fileio_rndrd": get_summary(result['readDeviation']),
        "fileio_rndwr": get_summary(result['writeDeviation'])
    }
    
    return JsonResponse(result)

@api.get("/benchmark/disk/fileio_seq/{node_id}")
def get_fileio_seq_disk_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = DiskBenchmark.objects.filter(
        provider=provider, 
        benchmark_name__in=["FileIO_seqrd", "FileIO_seqwr"]
    ).values('benchmark_name', 'read_throughput_mb_ps', 'write_throughput_mb_ps', 'created_at')

    result = {
        "data": {
            "fileio_seqrd": [], 
            "fileio_seqwr": []
        }, 
        "readDeviation": 0, 
        "writeDeviation": 0, 
        "summary": ""
    }
    read_scores, write_scores = [], []

    for benchmark in benchmarks:
        if "seqrd" in benchmark['benchmark_name']:
            score_entry = {"score": benchmark['read_throughput_mb_ps'], "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_seqrd"].append(score_entry)
            read_scores.append(benchmark['read_throughput_mb_ps'])
        else:
            score_entry = {"score": benchmark['write_throughput_mb_ps'], "timestamp": benchmark['created_at'].timestamp()}
            result["data"]["fileio_seqwr"].append(score_entry)
            write_scores.append(benchmark['write_throughput_mb_ps'])

    result['readDeviation'] = calculate_deviation(read_scores)
    result['writeDeviation'] = calculate_deviation(write_scores)

    result['summary'] = {
        "fileio_seqrd": get_summary(result['readDeviation']),
        "fileio_seqwr": get_summary(result['writeDeviation'])
    }
    
    return JsonResponse(result)

@api.get("/benchmark/network/{node_id}")
def get_network_benchmark(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return JsonResponse({"detail": "Provider not found"}, status=404)

    benchmarks = NetworkBenchmark.objects.filter(provider=provider).values(
        'mbit_per_second', 'created_at'
    )

    scores = [benchmark['mbit_per_second'] for benchmark in benchmarks]

    result = {
        "data": [{"score": benchmark['mbit_per_second'], "timestamp": benchmark['created_at'].timestamp()} for benchmark in benchmarks],
        "deviation": calculate_deviation(scores),
        "summary": get_summary(calculate_deviation(scores))
    }
    
    return JsonResponse(result)

from collections import defaultdict

@api.get("/provider/{node_id}/details", response={200: ProviderDetailsResponseSchema})
def get_provider_details(request, node_id: str):
    provider = Provider.objects.filter(node_id=node_id).first()
    if not provider:
        return api.create_response(request, {"detail": "Provider not found"}, status=404)

    offers = Offer.objects.filter(provider=provider).select_related('task').order_by('-created_at')

    processed_tasks = set()
    task_participations = []

    for offer in offers:
        if offer.task_id in processed_tasks:
            continue
        processed_tasks.add(offer.task_id)

        task_entry = TaskParticipationSchema(
            task_id=offer.task_id,
            completion_status="",
            error_message=None,
            cost=None,
            task_started_at = int(offer.task.started_at.timestamp())
        )

        if offer.accepted:
            try:
                completion = TaskCompletion.objects.get(task_id=offer.task_id, provider=provider)
                try:
                    benchmark_type = completion.task_name.split('_')[1]
                except IndexError:
                    # Default or fallback value if task_name is not in the expected format
                    benchmark_type = completion.task_name
        
                if completion.is_successful:
                    task_entry.completion_status = "Completed Successfully"
                    task_entry.error_message = None
                else:
                    task_entry.completion_status = "Failed"
                    # Update the error message to include the specific benchmark type
                    task_entry.error_message = f"{benchmark_type.capitalize()} Benchmark Failed with error: {completion.error_message}"
                task_entry.cost = completion.cost
            except TaskCompletion.DoesNotExist:
                task_entry.completion_status = "Accepted offer, but the task was not started. Reason unknown."
        else:
            task_entry.completion_status = "Offer Rejected"
            task_entry.error_message = offer.reason

        task_participations.append(task_entry)

    # Sort task_participations by 'task_id'
    task_participations_sorted = sorted(task_participations, key=lambda x: x.task_id)

    return ProviderDetailsResponseSchema(
        offer_history=[],  # Populate as needed
        task_participation=task_participations_sorted
    )
