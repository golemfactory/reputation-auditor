from django.db.models import Subquery, OuterRef
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

    provider_ids = [
        status.provider_id for status in latest_statuses if status.is_online]

    # Calculate uptime percentages
    uptime_data = {
        '100-80': 0,
        '80-40': 0,
        '40-0': 0
    }

    for provider_id in provider_ids:
        uptime_percentage = calculate_uptime(provider_id)
        if uptime_percentage >= 80:
            uptime_data['100-80'] += 1
        elif uptime_percentage >= 40:
            uptime_data['80-40'] += 1
        else:
            uptime_data['40-0'] += 1

    redis_client.set('stats_provider_uptime', json.dumps(uptime_data))


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

    provider_ids = [
        status.provider_id for status in latest_statuses if status.is_online]

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
