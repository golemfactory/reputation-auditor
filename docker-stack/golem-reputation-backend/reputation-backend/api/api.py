from .scoring import get_top_80_percent_cpu_multithread_providers
from .schemas import BulkTaskCostUpdateSchema
from .models import BlacklistedOperator, BlacklistedProvider
from django.db.models import Count, Q
from django.utils import timezone
from ninja import Query
import os
from ninja.security import HttpBearer
import redis
from ninja import NinjaAPI
from .models import Provider, TaskCompletion, Task
from .schemas import TaskCompletionSchema, ProviderSuccessRate, TaskCreateSchema, BulkTaskCostUpdateSchema, BulkBenchmarkSchema
from django.http import JsonResponse
from typing import List
import json
from django.db.models import Count, Q
from .bulkutils import process_disk_benchmark, process_cpu_benchmark, process_memory_benchmark, process_network_benchmark, process_gpu_task
api = NinjaAPI(
    title="Golem Reputation API",
    version="1.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api:api",
    docs_url="/docs/"
)


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        if token == os.environ.get("BACKEND_API_TOKEN"):
            return token


r = redis.Redis(host='redis', port=6379, db=0)


@api.get("/providers/scores", tags=["Reputation"])
def list_provider_scores(request, network: str = Query('polygon', description="The network parameter specifies the blockchain network for which provider scores are retrieved. Valid options include 'polygon', 'mainnet' for the main Ethereum network, 'goerli', 'mumbai', or 'holesky' for test networks. Any other value will result in a 404 error, indicating that the network is not supported.")):
    """
    Retrieve provider scores for a specified network.

    This endpoint fetches provider scores based on the specified network. The scores are precomputed and stored, ready for retrieval.

    Args:
        request: The HTTP request object.
        network (str): The network for which to retrieve provider scores. 

    Returns:
        JsonResponse: A JSON response containing the provider scores or an error message.

    Raises:
        JsonResponse: If the network is not found or if the data is not available.

    Example:
        GET /providers/scores?network=polygon
        Response:
        {
            "providers": [
                {
                    "providerId": "provider1",
                    "scores": {
                        "successRate": 0.95,
                        "uptime": 0.99
                    }
                },
                ...
            ],
            "untestedProviders": [
                {
                    "providerId": "provider2",
                    "scores": {
                        "uptime": 0.98
                    }
                },
                ...
            ],
            "rejectedProviders": [
                {
                    "providerId": "provider3",
                    "reason": "Consecutive failures: 6. Next eligible date: 2023-10-01T00:00:00Z"
                },
                ...
            ],
            "rejectedOperators": [
                {
                    "operator": {
                        "walletAddress": "0x1234567890abcdef",
                    },
                    "reason": "CPU benchmark deviation: multi=0.25, single=0.30 over threshold 0.20. Possibly overprovisioned."
                },
                ...
            ],
            "totalRejectedProvidersMainnet": 5,
            "totalOnlineProvidersMainnet": 50,
            "totalOnlineProvidersTestnet": 20
        }
    """
    if network == 'polygon' or network == 'mainnet':
        response = r.get('provider_scores_v1_mainnet')
    elif network == 'goerli' or network == 'mumbai' or network == 'holesky':
        response = r.get('provider_scores_v1_testnet')
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available
        return JsonResponse({"error": "Data not available"}, status=503)


@api.post("/benchmark/bulk", auth=AuthBearer(), include_in_schema=False,)
def create_bulk_benchmark(request, bulk_data: BulkBenchmarkSchema):
    organized_data = {"disk": [], "cpu": [],
                      "memory": [], "network": [], "gpu": []}
    for benchmark in bulk_data.benchmarks:
        organized_data[benchmark.type].append(benchmark.data)

    disk_response = process_disk_benchmark(organized_data["disk"])
    cpu_response = process_cpu_benchmark(organized_data["cpu"])
    memory_response = process_memory_benchmark(organized_data["memory"])
    network_response = process_network_benchmark(organized_data["network"])
    gpu_response = process_gpu_task(organized_data["gpu"])

    return {
        "disk": disk_response,
        "cpu": cpu_response,
        "memory": memory_response,
        "network": network_response,
        "gpu": gpu_response
    }


@api.post("/submit/task/status/bulk", auth=AuthBearer(), include_in_schema=False,)
def create_bulk_task_completion(request, data: List[TaskCompletionSchema]):
    task_completion_data = []
    errors = []

    for item in data:
        try:
            provider = Provider.objects.filter(node_id=item.node_id).first()
            task = Task.objects.filter(id=item.task_id).first()

            if not provider or not task:
                errors.append(f"Provider or Task not found for item with node_id {item.node_id} and task_id {item.task_id}")
                continue

            task_completion_data.append(TaskCompletion(
                provider=provider,
                task=task,
                task_name=item.task_name,
                is_successful=item.is_successful,
                error_message=item.error_message,
                type=item.type,
            ))
        except Exception as e:
            errors.append(f"Error processing item with node_id {item.node_id}: {str(e)}")

    TaskCompletion.objects.bulk_create(task_completion_data)

    if errors:
        return {"status": "error", "message": "Errors occurred during processing", "errors": errors}
    else:
        return {"status": "success", "message": f"Bulk task completion data saved successfully, processed {len(task_completion_data)} items."}


@api.get("scores/task", response=List[ProviderSuccessRate], include_in_schema=False,)
def provider_success_rate(request):
    # Get all providers
    providers = Provider.objects.annotate(
        total_tasks=Count('taskcompletion'),
        successful_tasks=Count('taskcompletion', filter=Q(
            taskcompletion__is_successful=True))
    )

    # Calculate success rate and prepare response
    success_rates = sorted(
        [
            {
                "node_id": provider.node_id,  # Unique Node ID
                "name": provider.name,  # Name of the provider
                "runtime_version": provider.runtime_version,  # Runtime Version
                "wallet_address": provider.payment_addresses,  # Wallet Address in JSON
                # Calculating success rate
                "success_rate": (provider.successful_tasks / provider.total_tasks * 100) if provider.total_tasks > 0 else 0
            }
            for provider in providers
        ],
        key=lambda x: x["success_rate"],  # Sorting by success rate
        reverse=True  # Descending order
    )

    return success_rates


@api.get(
    "/blacklisted-operators",
    tags=["Blacklist"],
    summary="Retrieve a list of blacklisted operator wallets",
    description="""
    This endpoint retrieves a list of wallets associated with blacklisted operators.
    The response is a list of wallet addresses that have been blacklisted.
    """,
    response=List[str]
)
def blacklisted_operators(request):
    rejected_operators = BlacklistedOperator.objects.all().values('wallet')
    # Extracting just the wallet field from each object
    rejected_wallets_list = [operator['wallet']
                             for operator in rejected_operators]
    print(rejected_wallets_list, "rejected_wallets_list")
    return rejected_wallets_list


@api.get(
    "/blacklisted-providers",
    tags=["Blacklist"],
    summary="Retrieve a list of blacklisted provider node IDs",
    description="""
    This endpoint retrieves a list of node IDs associated with blacklisted providers.
    The response is a list of node IDs that have been blacklisted.
    """,
    response=List[str]
)
def blacklisted_providers(request):
    rejected_providers = BlacklistedProvider.objects.all().values('provider__node_id')
    # Extracting just the provider__node_id field from each object
    rejected_node_ids_list = [provider['provider__node_id']
                              for provider in rejected_providers]
    return rejected_node_ids_list


@api.post("/task/start",  auth=AuthBearer(), include_in_schema=False,)
def start_task(request, payload: TaskCreateSchema):
    task = Task.objects.create(name=payload.name, started_at=timezone.now())
    return {"id": task.id, "name": task.name, "started_at": task.started_at}

from stats.tasks import cache_provider_success_ratio
@api.post("/task/end/{task_id}",  auth=AuthBearer(), include_in_schema=False,)
def end_task(request, task_id: int, cost: float):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Task does not exist"}, status=404)
    task.finished_at = timezone.now()
    task.cost = cost
    task.save()
    cache_provider_success_ratio.delay()

    return {"id": task.id, "finished_at": task.finished_at}


@api.post("/tasks/update-costs", auth=AuthBearer(), include_in_schema=False,)
def bulk_update_task_costs(request, payload: BulkTaskCostUpdateSchema):
    try:
        task_completions_to_update = []

        for update in payload.updates:
            task_exists = Task.objects.filter(id=update.task_id).exists()
            if not task_exists:
                print(f"Task with ID {update.task_id} not found.")
                continue  # Skip this update

            provider_exists = Provider.objects.filter(
                node_id=update.provider_id).exists()
            if not provider_exists:
                print(f"Provider with node ID {update.provider_id} not found.")
                continue  # Skip this update

            try:
                task_completion = TaskCompletion.objects.select_related('provider', 'task').get(
                    provider__node_id=update.provider_id, task__id=update.task_id)

                # Update the cost
                task_completion.cost = update.cost
                task_completions_to_update.append(task_completion)

            except TaskCompletion.DoesNotExist as e:
                print(e)
                print(f"TaskCompletion not found for task ID {update.task_id} and provider ID {update.provider_id}.")
                continue  # Skip this update

        # Bulk update
        if task_completions_to_update:
            TaskCompletion.objects.bulk_update(
                task_completions_to_update, ['cost'])

        return JsonResponse({"status": "success", "message": "Bulk task cost update completed"})

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return JsonResponse({"status": "error", "message": "An error occurred"}, status=500)


# Update with your Redis configuration
redis_client = redis.Redis(host='redis', port=6379, db=0)


@api.post("/task/offer/{task_id}", auth=AuthBearer(), include_in_schema=False,)
def store_offer(request, task_id: int):
    try:
        json_data = json.loads(request.body)
        node_id = json_data.get('node_id')
        offer = json_data.get('offer')
        # Default to an empty string if reason is not provided
        reason = json_data.get('reason', '')
        # Default to False if accepted is not provided
        accepted = json_data.get('accepted', False)

        if not node_id or offer is None:
            return JsonResponse({"status": "error", "error": "Missing node_id or offer"}, status=400)

        # Include reason and accepted in the offer dictionary
        offer_extended = {
            'offer': offer,
            'reason': reason,
            'accepted': accepted
        }

        # Create a unique key for Redis, e.g., using task ID and node ID
        redis_key = f"offer:{task_id}:{node_id}"
        redis_client.set(redis_key, json.dumps(offer_extended)
                         )  # Store the extended offer data
    except Exception as e:
        return JsonResponse({"status": "error", "error": str(e)}, status=500)

    return JsonResponse({"status": "success", "message": "Offer stored in Redis"})


@api.get("/benchmark", auth=AuthBearer(), include_in_schema=False,)
def start_benchmark(request):
    # benchmark_providers_task.delay()
    return {"status": "ok"}


@api.get(
    "/provider-whitelist",
    tags=["Reputation"],
    summary="Retrieve a whitelist of providers",
    description="""
    This endpoint retrieves a whitelist of providers based on their CPU multi-thread benchmark scores.
    The providers are filtered to include only the top percentage of performers within a specified number of days.

    The response includes a list of provider ids who are in the top specified percentage based on their CPU multi-thread benchmark scores.
    """,
)
def gnv_whitelist(
    request,
    paymentNetwork: str = Query('polygon', description="The paymentNetwork parameter specifies the blockchain network for which the whitelist of providers is retrieved. Options include: 'polygon' or 'mainnet' for the main Ethereum network, 'goerli', 'mumbai', or 'holesky' for test networks. Any other value will result in a 404 error, indicating that the network is not supported."),
    topPercent: int = Query(
        80, description="The top percentage of providers to include in the whitelist."),
    maxCheckedDaysAgo: int = Query(
        3, description="The maximum number of days ago to consider for the benchmark scores.")
):
    if paymentNetwork == 'polygon' or paymentNetwork == 'mainnet':
        response = get_top_80_percent_cpu_multithread_providers(
            maxCheckedDaysAgo=maxCheckedDaysAgo, topPercent=topPercent)
    elif paymentNetwork == 'goerli' or paymentNetwork == 'mumbai' or paymentNetwork == 'holesky':
        response = []
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response or response == []:
        return response
    else:
        # Handle the case where data is not yet available
        return JsonResponse({"error": "Data not available"}, status=503)
