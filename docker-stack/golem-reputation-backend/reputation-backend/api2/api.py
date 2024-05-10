from ninja import NinjaAPI, Path
from django.http import JsonResponse
import json
api = NinjaAPI(
    title="Golem Reputation API",
    version="2.0.0",
    description="API for Golem Reputation Backend",
    urls_namespace="api2",
)
import redis



r = redis.Redis(host='redis', port=6379, db=0)


@api.get("/providers/scores")
def list_provider_scores(request, network: str = 'polygon'):
    if network == 'polygon' or network == 'mainnet':
        response = r.get('provider_scores_v2_mainnet')
    elif network == 'goerli' or network == 'mumbai' or network == 'holesky':
        response = r.get('provider_scores_v2_testnet')
    else:
        return JsonResponse({"error": "Network not found"}, status=404)

    if response:
        return json.loads(response)
    else:
        # Handle the case where data is not yet available in Redis
        return JsonResponse({"error": "Data not available"}, status=503)


from api.models import Provider, CpuBenchmark, NodeStatusHistory, TaskCompletion, BlacklistedProvider, BlacklistedOperator
from api.scoring import calculate_uptime, penalty_weight
from django.db.models import Subquery, OuterRef

from django.db.models import Count, Case, When, FloatField
from django.db.models.functions import Cast
from django.db.models import Q
from datetime import timedelta
from django.utils import timezone
@api.get(
    "/filter",
    summary="Retrieve a list of provider IDs",
    description="""
    This endpoint retrieves a list of active provider IDs filtered according to various performance metrics and status indicators.
    The filters include uptime, CPU multi-thread and single-thread performance scores, and success rate of tasks. 
    Each filter is optional and can range between minimum and maximum values provided by the client. 
    - `minUptime` and `maxUptime` filter providers based on their uptime percentage.
    - `minCpuMultiThreadScore` and `maxCpuMultiThreadScore` filter providers based on their CPU multi-thread benchmark scores.
    - `minCpuSingleThreadScore` and `maxCpuSingleThreadScore` filter based on CPU single-thread benchmark scores.
    - `minSuccessRate` and `maxSuccessRate` filter providers by the percentage of successfully completed tasks.
    - `minProviderAge` filters providers based on the number of days since their creation. This is useful for when you need some specific uptime but also want to ensure that the provider has been around for a certain amount of time.
    Providers are only included in the result if they are currently online and not blacklisted.
    """,
)
def filter_providers(request, 
                  minUptime: float = None, maxUptime: float = None, 
                  minCpuMultiThreadScore: float = None, maxCpuMultiThreadScore: float = None, 
                  minCpuSingleThreadScore: float = None, maxCpuSingleThreadScore: float = None, 
                  minSuccessRate: float = None, maxSuccessRate: float = None, minProviderAgeDays: int = None):
    
    blacklisted_providers = set(BlacklistedProvider.objects.values_list('provider_id', flat=True))
    blacklisted_op_wallets = set(BlacklistedOperator.objects.values_list('wallet', flat=True))

    eligible_providers = Provider.objects.exclude(
        Q(node_id__in=blacklisted_providers) | 
        Q(payment_addresses__golem_com_payment_platform_erc20_mainnet_glm_address__in=blacklisted_op_wallets)
    ).annotate(
        latest_status=Subquery(
            NodeStatusHistory.objects.filter(
                provider=OuterRef('pk')
            ).order_by('-timestamp').values('is_online')[:1]
        )
    ).filter(latest_status=True)

    if minProviderAgeDays is not None:
        minimum_age_date = timezone.now() - timedelta(days=minProviderAgeDays)
        eligible_providers = eligible_providers.filter(created_at__lte=minimum_age_date)


    if minUptime is not None:
        eligible_providers = eligible_providers.filter(node_id__in=[
            p.node_id for p in eligible_providers if calculate_uptime(p.node_id) >= minUptime])

    if maxUptime is not None:
        eligible_providers = eligible_providers.filter(node_id__in=[
            p.node_id for p in eligible_providers if calculate_uptime(p.node_id) <= maxUptime])

    if minCpuMultiThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_multi_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Multi-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_multi_thread_score__gte=minCpuMultiThreadScore)

    if maxCpuMultiThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_multi_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Multi-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_multi_thread_score__lte=maxCpuMultiThreadScore)
    
    if minCpuSingleThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_single_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Single-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_single_thread_score__gte=minCpuSingleThreadScore)

    if maxCpuSingleThreadScore is not None:
        eligible_providers = eligible_providers.annotate(latest_cpu_single_thread_score=Subquery(
            CpuBenchmark.objects.filter(
                provider=OuterRef('pk'),
                benchmark_name="CPU Single-thread Benchmark"
            ).order_by('-created_at').values('events_per_second')[:1]
        )).filter(latest_cpu_single_thread_score__lte=maxCpuSingleThreadScore)

    if minSuccessRate is not None:
        eligible_providers = eligible_providers.annotate(
            successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
            total_tasks=Count('taskcompletion'),
            calculated_success_rate=Case(
                When(total_tasks=0, then=None),
                default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
            )
        ).filter(calculated_success_rate__gte=minSuccessRate)

    if maxSuccessRate is not None:
        eligible_providers = eligible_providers.annotate(
            successful_tasks=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True)),
            total_tasks=Count('taskcompletion'),
            calculated_success_rate=Case(
                When(total_tasks=0, then=None),
                default=(Cast('successful_tasks', FloatField()) / Cast('total_tasks', FloatField()) * 100)
            )
        ).filter(calculated_success_rate__lte=maxSuccessRate)

    provider_ids = eligible_providers.values_list('node_id', flat=True)
    return {"provider_ids": list(provider_ids)}