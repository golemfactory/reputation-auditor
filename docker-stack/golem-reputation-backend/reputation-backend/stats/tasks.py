import requests
from core.celery import app
from .models import DailyProviderStats
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

    success_rate_80_100 = sum(1 for p in tested_providers if 0.8 <= p['scores']['successRate'] <= 1) / len(tested_providers) if tested_providers else 0
    success_rate_50_80 = sum(1 for p in tested_providers if 0.5 <= p['scores']['successRate'] < 0.8) / len(tested_providers) if tested_providers else 0
    success_rate_30_50 = sum(1 for p in tested_providers if 0.3 <= p['scores']['successRate'] < 0.5) / len(tested_providers) if tested_providers else 0
    success_rate_0_30 = sum(1 for p in tested_providers if 0 <= p['scores']['successRate'] < 0.3) / len(tested_providers) if tested_providers else 0

    uptime_80_100 = sum(1 for p in tested_providers if 0.8 <= p['scores']['uptime'] <= 1) / len(tested_providers) if tested_providers else 0
    uptime_50_80 = sum(1 for p in tested_providers if 0.5 <= p['scores']['uptime'] < 0.8) / len(tested_providers) if tested_providers else 0
    uptime_30_50 = sum(1 for p in tested_providers if 0.3 <= p['scores']['uptime'] < 0.5) / len(tested_providers) if tested_providers else 0
    uptime_0_30 = sum(1 for p in tested_providers if 0 <= p['scores']['uptime'] < 0.3) / len(tested_providers) if tested_providers else 0

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