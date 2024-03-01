
from .scanner import monitor_nodes_status  # Import the task
import asyncio
from core.celery import app
from celery import Celery
from .ping import ping_providers
import subprocess
import redis
import json, os
from .models import Task, Provider, Offer, NodeStatusHistory, BlacklistedOperator, BlacklistedProvider
from django.db.models import OuterRef, Subquery
redis_client = redis.Redis(host='redis', port=6379, db=0)  # Update with your Redis configuration


@app.task
def monitor_nodes_task(subnet_tag='public'):
    # Run the asyncio function using asyncio.run()
    asyncio.run(monitor_nodes_status(subnet_tag))


@app.task
def ping_providers_task(p2p):
    asyncio.run(ping_providers(p2p))
    


@app.task(queue='benchmarker', options={'queue': 'benchmarker', 'routing_key': 'benchmarker'})
def benchmark_providers_task():
    budget_per_provider = os.environ.get('BUDGET_PER_PROVIDER', 0.1)

    # Subquery to get the latest NodeStatusHistory for each provider
    latest_status_subquery = NodeStatusHistory.objects.filter(
        provider=OuterRef('pk')
    ).order_by('-timestamp').values('is_online')[:1]

    # Query for providers that are on mainnet and their latest status is online
    mainnet_provider_count = Provider.objects.filter(
        network='mainnet',
        nodestatushistory__is_online=Subquery(latest_status_subquery)
    ).count()

    print(f"Found {mainnet_provider_count} online providers on the mainnet")

    command = f"cd /benchmark && yagna payment release-allocations && npm run benchmark -- {mainnet_provider_count} {budget_per_provider}"
    with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) as proc:
        while True:
            output = proc.stdout.readline()
            if output == '' and proc.poll() is not None:
                break
            if output:
                print(output.strip())

    rc = proc.poll()
    return rc


@app.task
def process_offers_from_redis():
    # Fetch all Redis keys that match the pattern
    offer_keys = redis_client.keys('offer:*')
    offers_to_create = []

    for key in offer_keys:
        # Load the extended offer data, which now includes reason and accepted
        offer_data = json.loads(redis_client.get(key))
        _, task_id, node_id = key.decode('utf-8').split(':')

        try:
            task = Task.objects.get(id=task_id)
            provider = Provider.objects.get(node_id=node_id)
            offer_instance = Offer(
                task=task,
                provider=provider,
                offer=offer_data.get('offer', {}),
                reason=offer_data.get('reason', ''),
                accepted=offer_data.get('accepted', False)
            )
            offers_to_create.append(offer_instance)

            # Optionally, delete the key from Redis after processing
            redis_client.delete(key)
        except (Task.DoesNotExist, Provider.DoesNotExist):
            continue

    # Bulk create offers
    Offer.objects.bulk_create(offers_to_create)


from django.db.models import Count, Q
from datetime import timedelta
from django.utils import timezone
from .scoring import calculate_uptime, get_normalized_cpu_scores
from .blacklist import get_blacklisted_providers, get_blacklisted_operators

@app.task(queue='default', options={'queue': 'default', 'routing_key': 'default'})
def update_provider_scores(network):
    r = redis.Redis(host='redis', port=6379, db=0)
    ten_days_ago = timezone.now() - timedelta(days=10)
    recent_online_providers = NodeStatusHistory.objects.filter(is_online=True).order_by('provider', '-timestamp').distinct('provider')
    online_provider_ids = [status.provider_id for status in recent_online_providers]
    providers = Provider.objects.filter(node_id__in=online_provider_ids, network=network).annotate(
        success_count=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True, taskcompletion__timestamp__gte=ten_days_ago)),
        total_count=Count('taskcompletion', filter=Q(taskcompletion__timestamp__gte=ten_days_ago)),
    ).all()
    response_v1 = {"providers": [], "untestedProviders": []}
    response_v2 = {"providers": [], "untestedProviders": []}
    cpu_scores = get_normalized_cpu_scores()
    for provider in providers:
        if provider.total_count > 0:
            success_ratio = provider.success_count / provider.total_count
            uptime_percentage = calculate_uptime(provider.node_id)

            provider_info_v1 = {
                "providerId": provider.node_id,
                "scores": {
                    "successRate": success_ratio,
                    "uptime": uptime_percentage / 100,
                }
            }

            provider_info_v2 = {
                **provider_info_v1,
                "scores": {
                    **provider_info_v1["scores"],
                    "cpuSingleThreadScore": cpu_scores[provider.node_id]["single_thread_score"],
                    "cpuMultiThreadScore": cpu_scores[provider.node_id]["multi_thread_score"]
                }
            }

            response_v1["providers"].append(provider_info_v1)
            response_v2["providers"].append(provider_info_v2)

    providers_with_no_tasks = Provider.objects.filter(node_id__in=online_provider_ids, taskcompletion__isnull=True, network=network)
    for provider in providers_with_no_tasks:
        uptime_percentage = calculate_uptime(provider.node_id)
        untested_info = {
            "providerId": provider.node_id,
            "scores": {
                "uptime": uptime_percentage / 100,
            }
        }
        response_v1["untestedProviders"].append(untested_info)
        response_v2["untestedProviders"].append(untested_info)

    rejected_providers = BlacklistedProvider.objects.all().values('provider__node_id', 'reason')
    rejected_operators = BlacklistedOperator.objects.all().values('wallet', 'reason')

# Convert QuerySets to a list of dictionaries
    rejected_providers_list = list(rejected_providers)
    rejected_operators_list = list(rejected_operators)
    response_v1["rejectedProviders"] = rejected_providers_list
    response_v1["rejectedOperators"] = rejected_operators_list
    response_v2["rejectedProviders"] = rejected_providers_list
    response_v2["rejectedOperators"] = rejected_operators_list
    r.set(f'provider_scores_v1_{network}', json.dumps(response_v1))
    r.set(f'provider_scores_v2_{network}', json.dumps(response_v2))



from .models import Provider, TaskCompletion, BlacklistedOperator, BlacklistedProvider
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, StdDev, FloatField, Q, Subquery, OuterRef, F, Case, When, Max
from django.db.models.functions import Cast
from datetime import timedelta
from django.db.models import Subquery, OuterRef
from django.db.models.fields.json import KeyTextTransform

@app.task
def get_blacklisted_operators():
    # Clear the existing blacklisted providers
    BlacklistedOperator.objects.all().delete()
    now = timezone.now()
    recent_tasks = TaskCompletion.objects.filter(
        timestamp__gte=now - timedelta(days=30)
    ).annotate(
        payment_address=F('provider__payment_addresses__golem_com_payment_platform_erc20_mainnet_glm_address')
    ).values('payment_address').annotate(
        successful_tasks=Count('pk', filter=Q(is_successful=True)),
        total_tasks=Count('pk'),
        success_ratio=Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField())
    ).exclude(total_tasks=0)

    success_stats = recent_tasks.aggregate(
        average_success_ratio=Avg('success_ratio'),
        stddev_success_ratio=StdDev('success_ratio')
    )

    avg_success_ratio = success_stats.get('average_success_ratio', 0) or 0
    stddev_success_ratio = success_stats.get('stddev_success_ratio', 0) or 1

    recent_tasks_with_z_score = recent_tasks.annotate(
        z_score=(F('success_ratio') - avg_success_ratio) / stddev_success_ratio
    )

    z_score_threshold = -1
    blacklisted_addr_success = list(recent_tasks_with_z_score.filter(
        z_score__lte=z_score_threshold,
        total_tasks__gte=5
    ).values_list(
        'payment_address', flat=True
    ).distinct())

    for payment_address in blacklisted_addr_success:
        # Blacklist the Operator
        BlacklistedOperator.objects.create(wallet=payment_address, reason=f"Task success ratio deviation: z-score={z_score_threshold}. Operator has significantly lower success ratio than the average.")

    latest_online_statuses = NodeStatusHistory.objects.annotate(
        latest=Max('timestamp', filter=Q(is_online=True))
    ).filter(
        timestamp=F('latest'), is_online=True
    ).values_list('provider_id', flat=True)

    providers = Provider.objects.filter(
        node_id__in=latest_online_statuses
    )

    eligible_payment_addresses = providers.annotate(
        payment_address=KeyTextTransform('golem.com.payment.platform.erc20-mainnet-glm.address', 'payment_addresses')
    ).values('payment_address').annotate(
        online_count=Count('node_id')
    ).filter(
        online_count__gte=3
    ).values_list('payment_address', flat=True)

    # Assuming eligible_payment_addresses are now extracted accurately
    # Cast the JSON field key access to text for PostgreSQL comparison
    eligible_payment_addresses = list(eligible_payment_addresses)  # Make sure it's a list for __in lookup
    
    providers_performance = Provider.objects.filter(
        payment_addresses__has_key='golem.com.payment.platform.erc20-mainnet-glm.address'
    ).annotate(
        payment_addr=KeyTextTransform('golem.com.payment.platform.erc20-mainnet-glm.address', 'payment_addresses')
    )

    # Prepare a set or list from eligible_payment_addresses for efficient lookups
    eligible_payment_addresses_set = set(eligible_payment_addresses)

    # Manually filter providers based on the payment address
    eligible_providers = [
        provider.node_id for provider in providers_performance
        if provider.payment_addr in eligible_payment_addresses_set
    ]

    # Re-fetch providers with performance annotations
    eligible_providers_with_performance = Provider.objects.filter(
        node_id__in=eligible_providers
    ).annotate(
        avg_eps_multi=Avg(Case(
            When(cpubenchmark__benchmark_name="CPU Multi-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField()
        )),
        stddev_eps_multi=StdDev(Case(
            When(cpubenchmark__benchmark_name="CPU Multi-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField()
        )),
        avg_eps_single=Avg(Case(
            When(cpubenchmark__benchmark_name="CPU Single-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField()
        )),
        stddev_eps_single=StdDev(Case(
            When(cpubenchmark__benchmark_name="CPU Single-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField()
        ))
    )

    print(f"Found {len(eligible_providers_with_performance)} eligible providers with performance data")
    blacklisted_addr = set()
    deviation_threshold = 0.20
    for provider in eligible_providers_with_performance:
        multi_deviation = (provider.stddev_eps_multi / provider.avg_eps_multi) if provider.stddev_eps_multi else 0
        single_deviation = (provider.stddev_eps_single / provider.avg_eps_single) if provider.stddev_eps_single else 0
        payment_address = provider.payment_addresses.get('golem.com.payment.platform.erc20-mainnet-glm.address')
        print(f"Payment address: {payment_address}, multi_deviation: {multi_deviation}, single_deviation: {single_deviation}")
        if (multi_deviation > deviation_threshold or single_deviation > deviation_threshold):
            if not payment_address in blacklisted_addr:
                blacklisted_addr.add(payment_address)
                BlacklistedOperator.objects.create(
                    wallet=payment_address,
                    reason=f"CPU benchmark deviation: multi={multi_deviation:.2f}, single={single_deviation:.2f} over threshold {deviation_threshold}."
                )

@app.task
def get_blacklisted_providers():
    # Clear the existing blacklisted providers
    BlacklistedProvider.objects.all().delete()
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
            BlacklistedProvider.objects.create(provider=provider, reason=f"Consecutive failures: {consecutive_failures}. Next eligible date: {next_eligible_date}")

    return blacklisted_providers
