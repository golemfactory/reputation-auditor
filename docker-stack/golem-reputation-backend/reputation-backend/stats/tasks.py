from django.db.models import Count, Q
from django.utils import timezone
import requests
from core.celery import app
from .models import DailyProviderStats
from api.models import PingResult, NodeStatusHistory, Provider
from api.scoring import calculate_uptime
import redis
import json

redis_client = redis.Redis(host='redis', port=6379, db=0)


@app.task
def populate_daily_provider_stats():
    url = "http://django:8002/v2/providers/scores"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
        else:
            print(f"Error fetching data: HTTP {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

    tested_providers = data['testedProviders']
    untested_providers = data['untestedProviders']
    rejected_providers = data['rejectedProviders']
    rejected_operators = data['rejectedOperators']

    success_rate_80_100 = sum(1 for p in tested_providers if 0.8 <=
                              p['scores']['successRate'] <= 1) / len(tested_providers) if tested_providers else 0
    success_rate_50_80 = sum(1 for p in tested_providers if 0.5 <=
                             p['scores']['successRate'] < 0.8) / len(tested_providers) if tested_providers else 0
    success_rate_30_50 = sum(1 for p in tested_providers if 0.3 <=
                             p['scores']['successRate'] < 0.5) / len(tested_providers) if tested_providers else 0
    success_rate_0_30 = sum(1 for p in tested_providers if 0 <=
                            p['scores']['successRate'] < 0.3) / len(tested_providers) if tested_providers else 0

    uptime_80_100 = sum(1 for p in tested_providers if 0.8 <=
                        p['scores']['uptime'] <= 1) / len(tested_providers) if tested_providers else 0
    uptime_50_80 = sum(1 for p in tested_providers if 0.5 <=
                       p['scores']['uptime'] < 0.8) / len(tested_providers) if tested_providers else 0
    uptime_30_50 = sum(1 for p in tested_providers if 0.3 <=
                       p['scores']['uptime'] < 0.5) / len(tested_providers) if tested_providers else 0
    uptime_0_30 = sum(1 for p in tested_providers if 0 <=
                      p['scores']['uptime'] < 0.3) / len(tested_providers) if tested_providers else 0

    total_tested_provider = len(tested_providers)
    total_untested_provider = len(untested_providers)

    DailyProviderStats.objects.create(
        success_rate_80_100=success_rate_80_100,
        success_rate_50_80=success_rate_50_80,
        success_rate_30_50=success_rate_30_50,
        success_rate_0_30=success_rate_0_30,
        uptime_80_100=uptime_80_100,
        uptime_50_80=uptime_50_80,
        uptime_30_50=uptime_30_50,
        uptime_0_30=uptime_0_30,
        total_provider_count_mainnet=data['totalOnlineProvidersMainnet'],
        total_provider_count_testnet=data['totalOnlineProvidersTestnet'],
        total_untested_provider=total_untested_provider,
        total_tested_provider=total_tested_provider,
        total_provider_rejected_without_operator=len(rejected_providers),
        total_provider_rejected=data['totalRejectedProvidersMainnet'],
        total_operator_rejected=len(rejected_operators)
    )


@app.task
def cache_provider_uptime():

    # Get the latest online status for each provider
    latest_statuses = NodeStatusHistory.objects.filter(
        timestamp=Subquery(
            NodeStatusHistory.objects.filter(provider=OuterRef('provider'))
            .order_by('-timestamp')
            .values('timestamp')[:1]
        )
    )

    provider_ids = [status.provider_id for status in latest_statuses if status.is_online]


    # Calculate uptime percentages
    uptime_data = {
        '100-80': 0,
        '80-40': 0,
        '40-0': 0
    }

    uptime_data = {
        '100-99': 0,
        '99-98': 0,
    }
    uptime_data.update({f'{i}-{i-10}': 0 for i in range(90, 0, -10)})
    
    for provider_id in provider_ids:
        uptime_percentage = calculate_uptime(provider_id)
        if uptime_percentage >= 99:
            uptime_data['100-99'] += 1
        elif uptime_percentage >= 98:
            uptime_data['99-98'] += 1
        else:
            for i in range(90, 0, -10):
                if uptime_percentage >= i - 10:
                    uptime_data[f'{i}-{i-10}'] += 1
                    break

    redis_client.set('stats_provider_uptime', json.dumps(uptime_data))

from django.db.models import Subquery, OuterRef
@app.task
def cache_provider_success_ratio():
    # Get the latest online status for each provider
    latest_statuses = NodeStatusHistory.objects.filter(
        timestamp=Subquery(
            NodeStatusHistory.objects.filter(provider=OuterRef('provider'))
            .order_by('-timestamp')
            .values('timestamp')[:1]
        )
    )

    provider_ids = [status.provider_id for status in latest_statuses if status.is_online]


    # Calculate success ratios
    success_ratio_data = {
        '100-80': 0,
        '80-40': 0,
        '40-0': 0
    }

    for provider_id in provider_ids:
        provider = Provider.objects.filter(node_id=provider_id).annotate(
            success_count=Count('taskcompletion', filter=Q(
                taskcompletion__is_successful=True)),
            total_count=Count('taskcompletion'),
        ).first()

        if provider and provider.total_count > 0:
            success_ratio = provider.success_count / provider.total_count * 100
            if success_ratio >= 80:
                success_ratio_data['100-80'] += 1
            elif success_ratio >= 40:
                success_ratio_data['80-40'] += 1
            else:
                success_ratio_data['40-0'] += 1

    redis_client.set('stats_provider_success_ratio',
                     json.dumps(success_ratio_data))


from django.db.models import Max, F, Subquery, OuterRef, Prefetch
from api.models import CpuBenchmark, Offer, GPUTask
from datetime import timedelta


@app.task
def cache_cpu_performance_ranking():
    # Get the date 30 days ago
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Get the latest CPU Multi-thread Benchmark for each provider in the last 30 days
    latest_benchmarks = CpuBenchmark.objects.filter(
        #created_at__gte=thirty_days_ago,
        benchmark_name='CPU Multi-thread Benchmark'
    ).order_by('provider_id', '-created_at').distinct('provider_id')

    # Prefetch related providers and their latest offers
    providers = Provider.objects.filter(
        cpubenchmark__in=latest_benchmarks
    ).prefetch_related(
        Prefetch(
            'offer_set',
            queryset=Offer.objects.filter(
                accepted=True
            ).order_by('-created_at'),
            to_attr='latest_offer'
        )
    )

    cpu_performance = []

    for provider in providers:
        benchmark = next((b for b in latest_benchmarks if b.provider_id == provider.node_id), None)
        if benchmark and provider.latest_offer:
            latest_offer = provider.latest_offer[0]
            cpu_brand = latest_offer.offer.get('golem.inf.cpu.brand')
            if cpu_brand:
                cpu_performance.append({
                    'cpu_brand': cpu_brand,
                    'events_per_second': benchmark.events_per_second,
                    'provider_id': provider.node_id
                })

    # Remove duplicates, keeping the highest performance for each CPU brand
    unique_cpu_performance = {}
    for item in cpu_performance:
        cpu_brand = item['cpu_brand']
        if cpu_brand not in unique_cpu_performance or item['events_per_second'] > unique_cpu_performance[cpu_brand]['events_per_second']:
            unique_cpu_performance[cpu_brand] = item

    # Sort the list from most performant to least
    sorted_cpu_performance = sorted(
        unique_cpu_performance.values(),
        key=lambda x: x['events_per_second'],
        reverse=True
    )

    redis_client.set('stats_cpu_performance_ranking', json.dumps(sorted_cpu_performance))

@app.task
def cache_gpu_performance_ranking():
    # Get the date 30 days ago
    thirty_days_ago = timezone.now() - timedelta(days=30)

    # Get the highest GFLOPS for each GPU model in the last 30 days
    gpu_performance = GPUTask.objects.filter(
        #created_at__gte=thirty_days_ago
    ).values('name').annotate(
        max_gflops=Max('gpu_burn_gflops')
    ).filter(max_gflops__isnull=False).order_by('-max_gflops')

    # Convert queryset to list of dictionaries
    result = list(gpu_performance)

    redis_client.set('stats_gpu_performance_ranking', json.dumps(result))