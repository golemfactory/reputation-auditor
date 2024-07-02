
from .models import PingResult
from datetime import timedelta
from django.db.models.fields.json import KeyTextTransform
from django.db.models import Subquery, OuterRef
from django.db.models.functions import Cast
from django.db.models import Count, Avg, StdDev, FloatField, Q, Subquery, OuterRef, F, Max
from .models import Provider, TaskCompletion, BlacklistedOperator, BlacklistedProvider
from .scoring import calculate_uptime, get_normalized_cpu_scores
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from .scanner import monitor_nodes_status  # Import the task
import asyncio
from core.celery import app
from .ping import ping_providers
import redis
import json
from .models import Task, Provider, Offer, NodeStatusHistory, BlacklistedOperator, BlacklistedProvider
from django.db.models import OuterRef, Subquery
# Update with your Redis configuration
redis_client = redis.Redis(host='redis', port=6379, db=0)


@app.task
def monitor_nodes_task(subnet_tag='public'):
    # Run the asyncio function using asyncio.run()
    asyncio.run(monitor_nodes_status(subnet_tag))


@app.task
def ping_providers_task(p2p):
    asyncio.run(ping_providers(p2p))


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


@app.task(queue='default', options={'queue': 'default', 'routing_key': 'default'})
def update_provider_scores(network):
    r = redis.Redis(host='redis', port=6379, db=0)
    ten_days_ago = timezone.now() - timedelta(days=10)
    recent_online_providers = NodeStatusHistory.objects.filter(
        is_online=True).order_by('provider', '-timestamp').distinct('provider')
    online_provider_ids = [
        status.provider_id for status in recent_online_providers]
    providers = Provider.objects.filter(node_id__in=online_provider_ids, network=network).annotate(
        success_count=Count('taskcompletion', filter=Q(
            taskcompletion__is_successful=True, taskcompletion__timestamp__gte=ten_days_ago)),
        total_count=Count('taskcompletion', filter=Q(
            taskcompletion__timestamp__gte=ten_days_ago)),
    ).all()
    response_v1 = {"providers": [], "untestedProviders": []}
    response_v2 = {"testedProviders": [], "untestedProviders": []}
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
                "provider": {'id': provider.node_id, 'name': provider.name, 'walletAddress': provider.payment_addresses.get('golem.com.payment.platform.erc20-mainnet-glm.address')},
                "scores": {
                    **provider_info_v1["scores"],
                    "cpuSingleThreadScore": cpu_scores[provider.node_id]["single_thread_score"],
                    "cpuMultiThreadScore": cpu_scores[provider.node_id]["multi_thread_score"]
                }
            }

            response_v1["providers"].append(provider_info_v1)
            response_v2["testedProviders"].append(provider_info_v2)

    providers_with_no_tasks = Provider.objects.filter(
        node_id__in=online_provider_ids, taskcompletion__isnull=True, network=network)
    for provider in providers_with_no_tasks:
        uptime_percentage = calculate_uptime(provider.node_id)
        untested_info = {
            "providerId": provider.node_id,
            "scores": {
                "uptime": uptime_percentage / 100,
            }
        }
        untested_info_v2 = {
            "provider": {'id': provider.node_id, 'name': provider.name, 'walletAddress': provider.payment_addresses.get('golem.com.payment.platform.erc20-mainnet-glm.address')},
            "scores": {
                "uptime": uptime_percentage / 100,
            }
        }
        response_v1["untestedProviders"].append(untested_info)
        response_v2["untestedProviders"].append(untested_info_v2)

    rejected_providers_v2 = BlacklistedProvider.objects.select_related('provider').annotate(
        providerId=F('provider_id'),
        # Adjust these field lookups based on your actual model relationships
        name=F('provider__name'),
        walletAddress=F(
            'provider__payment_addresses__golem.com.payment.platform.erc20-mainnet-glm.address')
    ).values('providerId', 'name', 'walletAddress', 'reason')

    rejected_providers_list = [
        {
            "provider": {
                "id": provider["providerId"],
                "name": provider["name"],
                "walletAddress": provider["walletAddress"],
            },
            "reason": provider["reason"]
        }
        for provider in rejected_providers_v2
    ]
    rejected_operators_v2 = BlacklistedOperator.objects.all().values('wallet', 'reason')
    rejected_operators_list = [
        {
            "operator": {
                "walletAddress": operator["wallet"],

            },
            "reason": operator["reason"]

        }
        for operator in rejected_operators_v2
    ]

    rejected_providers_v1 = BlacklistedProvider.objects.all().annotate(
        providerId=F('provider_id')).values('providerId', 'reason')
    rejected_operators_v1 = BlacklistedOperator.objects.all().values('wallet', 'reason')

    blacklisted_operators_wallets = list(
        BlacklistedOperator.objects.values_list('wallet', flat=True))
    total_blacklist_count = 0
    for wallet in blacklisted_operators_wallets:
        key = f"golem.com.payment.platform.erc20-mainnet-glm.address"
        total_blacklist_count += Provider.objects.filter(payment_addresses__has_key=key, payment_addresses__contains={
                                                         key: wallet}, node_id__in=online_provider_ids).count()

    for provider in rejected_providers_v2:
        total_blacklist_count += 1

    mainnet_online_provider_count = Provider.objects.filter(
        network="mainnet", node_id__in=online_provider_ids).count()
    testnet_online_provider_count = Provider.objects.filter(
        network="testnet", node_id__in=online_provider_ids).count()
# Convert QuerySets to a list of dictionaries
    response_v1["rejectedProviders"] = list(rejected_providers_v1)
    response_v1["rejectedOperators"] = list(rejected_operators_v1)
    response_v2["rejectedProviders"] = rejected_providers_list
    response_v2["rejectedOperators"] = rejected_operators_list
    response_v1["totalRejectedProvidersMainnet"] = total_blacklist_count
    response_v2["totalRejectedProvidersMainnet"] = total_blacklist_count
    response_v1["totalOnlineProvidersMainnet"] = mainnet_online_provider_count
    response_v1["totalOnlineProvidersTestnet"] = testnet_online_provider_count
    response_v2["totalOnlineProvidersMainnet"] = mainnet_online_provider_count
    response_v2["totalOnlineProvidersTestnet"] = testnet_online_provider_count
    r.set(f'provider_scores_v1_{network}', json.dumps(response_v1))
    r.set(f'provider_scores_v2_{network}', json.dumps(response_v2))


@app.task
def get_blacklisted_operators():
    blacklist = []

    now = timezone.now()
    recent_tasks = TaskCompletion.objects.filter(
        timestamp__gte=now - timedelta(days=3)
    ).annotate(
        payment_address=F(
            'provider__payment_addresses__golem_com_payment_platform_erc20_mainnet_glm_address')
    ).values('payment_address').annotate(
        successful_tasks=Count('pk', filter=Q(is_successful=True)),
        total_tasks=Count('pk'),
        success_ratio=Cast('successful_tasks', FloatField()) /
        Cast('total_tasks', FloatField())
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
        blacklist.append({
            "wallet": payment_address,
            "reason": f"Task success ratio deviation: z-score={z_score_threshold}. Operator has significantly lower success ratio than the average."

        })

    latest_online_statuses = NodeStatusHistory.objects.annotate(
        latest=Max('timestamp', filter=Q(is_online=True))
    ).filter(
        timestamp=F('latest'), is_online=True
    ).values_list('provider_id', flat=True)

    providers = Provider.objects.filter(
        node_id__in=latest_online_statuses
    )

    eligible_payment_addresses = providers.annotate(
        payment_address=KeyTextTransform(
            'golem.com.payment.platform.erc20-mainnet-glm.address', 'payment_addresses')
    ).values('payment_address').annotate(
        online_count=Count('node_id')
    ).filter(
        online_count__gte=3
    ).values_list('payment_address', flat=True)

    # Assuming eligible_payment_addresses are now extracted accurately
    # Cast the JSON field key access to text for PostgreSQL comparison
    # Make sure it's a list for __in lookup
    eligible_payment_addresses = list(eligible_payment_addresses)

    providers_performance = Provider.objects.filter(
        payment_addresses__has_key='golem.com.payment.platform.erc20-mainnet-glm.address'
    ).annotate(
        payment_addr=KeyTextTransform(
            'golem.com.payment.platform.erc20-mainnet-glm.address', 'payment_addresses')
    )

    # Prepare a set or list from eligible_payment_addresses for efficient lookups
    eligible_payment_addresses_set = set(eligible_payment_addresses)

    # Manually filter providers based on the payment address
    eligible_providers = [
        provider.node_id for provider in providers_performance
        if provider.payment_addr in eligible_payment_addresses_set
    ]

    # Re-fetch providers with performance annotations
    providers_with_recent_benchmarks = Provider.objects.filter(
        # Use the list of node IDs that passed initial eligibility
        node_id__in=eligible_providers
    ).annotate(
        recent_benchmark_count=Count(
            'cpubenchmark',
            filter=Q(cpubenchmark__created_at__gte=now - timedelta(days=3))
        )
    ).filter(
        recent_benchmark_count__gt=0  # Ensure there's at least one recent benchmark
    )

    # Calculate deviation for these providers
    providers_with_deviation = providers_with_recent_benchmarks.annotate(
        avg_eps_multi=Avg(
            'cpubenchmark__events_per_second',
            filter=Q(cpubenchmark__benchmark_name="CPU Multi-thread Benchmark",
                     cpubenchmark__created_at__gte=now - timedelta(days=3))
        ),
        stddev_eps_multi=StdDev(
            'cpubenchmark__events_per_second',
            filter=Q(cpubenchmark__benchmark_name="CPU Multi-thread Benchmark",
                     cpubenchmark__created_at__gte=now - timedelta(days=3))
        ),
        avg_eps_single=Avg(
            'cpubenchmark__events_per_second',
            filter=Q(cpubenchmark__benchmark_name="CPU Single-thread Benchmark",
                     cpubenchmark__created_at__gte=now - timedelta(days=3))
        ),
        stddev_eps_single=StdDev(
            'cpubenchmark__events_per_second',
            filter=Q(cpubenchmark__benchmark_name="CPU Single-thread Benchmark",
                     cpubenchmark__created_at__gte=now - timedelta(days=3))
        )
    )

    blacklisted_addr = set()
    deviation_threshold = 0.20
    for provider in providers_with_deviation:
        multi_deviation = provider.stddev_eps_multi / \
            provider.avg_eps_multi if provider.avg_eps_multi else 0
        single_deviation = provider.stddev_eps_single / \
            provider.avg_eps_single if provider.avg_eps_single else 0

        if multi_deviation > deviation_threshold or single_deviation > deviation_threshold:
            payment_address = provider.payment_addresses.get(
                'golem.com.payment.platform.erc20-mainnet-glm.address')
            if payment_address not in blacklisted_addr:
                blacklisted_addr.add(payment_address)
                blacklist.append({
                    "wallet": payment_address,
                    "reason": f"CPU benchmark deviation: multi={multi_deviation:.2f}, single={single_deviation:.2f} over threshold {deviation_threshold}. Possibly overprovisioned."
                })

    new_wallets = {operator['wallet'] for operator in blacklist}

    # Update existing entries and add new ones
    for operator in blacklist:
        obj, created = BlacklistedOperator.objects.update_or_create(
            wallet=operator['wallet'],
            defaults={'reason': operator['reason']},
        )

    # Find and delete any blacklisted operators not in the new list
    BlacklistedOperator.objects.exclude(wallet__in=new_wallets).delete()


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
            # Assuming we look at the last 3 days
            timestamp__gte=now - timedelta(days=3)
        ).count()

        # Apply a cap to the consecutive_failures
        max_consecutive_failures = 6  # Maximum failures to keep backoff within 14 days
        effective_failures = min(consecutive_failures,
                                 max_consecutive_failures)

        # Exponential backoff formula
        backoff_hours = 10 * (2 ** (effective_failures - 1))
        next_eligible_date = provider.taskcompletion_set.latest(
            'timestamp').timestamp + timedelta(hours=backoff_hours)

        if now < next_eligible_date:
            blacklisted_providers.append(provider.node_id)
            BlacklistedProvider.objects.create(
                provider=provider,
                reason=f"Consecutive failures: {consecutive_failures}. Next eligible date: {next_eligible_date}"
            )

    return blacklisted_providers


@app.task
def delete_old_ping_results():
    # Calculate the date 30 days ago from today
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Delete PingResult records older than 30 days
    old_ping_results = PingResult.objects.filter(
        created_at__lt=thirty_days_ago)
    count_ping_results = old_ping_results.count()
    old_ping_results.delete()

    # Optionally, you can log the number of deleted records or return it
    print(
        f"Deleted {count_ping_results} PingResult records older than 30 days.")