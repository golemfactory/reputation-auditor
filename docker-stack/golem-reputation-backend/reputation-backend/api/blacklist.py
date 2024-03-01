from .models import Provider, TaskCompletion, BlacklistedOperator, BlacklistedProvider
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, StdDev, FloatField, Q, Subquery, OuterRef, F, Case, When
from django.db.models.functions import Cast
from datetime import timedelta
from django.db.models import Subquery, OuterRef


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
        BlacklistedOperator.objects.get_or_create(wallet=payment_address, reason=f"Task success ratio deviation: z-score={z_score_threshold}. Operator has significantly lower success ratio than the average.")

    providers_performance = Provider.objects.annotate(
        avg_eps_multi=Avg(Case(
            When(cpubenchmark__benchmark_name="CPU Multi-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField(),
        )),
        stddev_eps_multi=StdDev(Case(
            When(cpubenchmark__benchmark_name="CPU Multi-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField(),
        )),
        avg_eps_single=Avg(Case(
            When(cpubenchmark__benchmark_name="CPU Single-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField(),
        )),
        stddev_eps_single=StdDev(Case(
            When(cpubenchmark__benchmark_name="CPU Single-thread Benchmark", then=F('cpubenchmark__events_per_second')),
            output_field=FloatField(),
        ))
    ).filter(
        # Ensure we only include providers with benchmark data above zero to avoid dividing by zero
        avg_eps_multi__gt=0, 
        avg_eps_single__gt=0
    )

    # Preparing lists for blacklisting based on significant deviation for each benchmark type
    blacklisted_providers = []
    deviation_threshold = 0.20  # Define the threshold for a significant deviation

    for provider in providers_performance:
        # Calculate deviation if possible
        multi_deviation = provider.stddev_eps_multi / provider.avg_eps_multi if provider.avg_eps_multi and provider.stddev_eps_multi else None
        single_deviation = provider.stddev_eps_single / provider.avg_eps_single if provider.avg_eps_single and provider.stddev_eps_single else None
        # Check if the deviation exceeds the threshold for either benchmark type
        if multi_deviation and multi_deviation > deviation_threshold or \
           single_deviation and single_deviation > deviation_threshold:
            payment_address = provider.payment_addresses.get('golem.com.payment.platform.erc20-mainnet-glm.address', None)
            if payment_address:
                blacklisted_providers.append(payment_address)
                # Blacklist the Operator
                BlacklistedOperator.objects.get_or_create(wallet=payment_address, reason=f"CPU benchmark deviation: multi={multi_deviation}, single={single_deviation} over threshold {deviation_threshold}. Possibly overprovisioned CPU.")



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
