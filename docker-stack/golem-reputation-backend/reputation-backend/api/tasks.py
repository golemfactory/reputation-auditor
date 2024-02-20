# main.py or any other file from which you want to trigger the task

from .scanner import monitor_nodes_status  # Import the task
import asyncio
from core.celery import app
from celery import Celery
from .ping import ping_providers
import subprocess
import redis
import json, os
from .models import Task, Provider, Offer
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
    mainnet_provider_count = Provider.objects.filter(network='mainnet').count()
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
from .scoring import calculate_uptime

@app.task(queue='default', options={'queue': 'default', 'routing_key': 'default'})
def update_provider_scores():
    r = redis.Redis(host='redis', port=6379, db=0)
    ten_days_ago = timezone.now() - timedelta(days=10)
    providers = Provider.objects.annotate(
        success_count=Count('taskcompletion', filter=Q(taskcompletion__is_successful=True, taskcompletion__timestamp__gte=ten_days_ago)),
        total_count=Count('taskcompletion', filter=Q(taskcompletion__timestamp__gte=ten_days_ago)),
    ).all()

    response = {"providers": [], "rejected": []}
    for provider in providers:
        if provider.total_count > 0:
            success_ratio = provider.success_count / provider.total_count
            uptime_percentage = calculate_uptime(provider.node_id)
            
            response["providers"].append({
                "providerId": provider.node_id,
                "scores": {
                    "successRate": success_ratio,
                    "uptime": uptime_percentage / 100
                }
            })
    providers_with_no_tasks = Provider.objects.filter(taskcompletion__isnull=True)
    for provider in providers_with_no_tasks:
        uptime_percentage = calculate_uptime(provider.node_id)
        response["rejected"].append({
            "providerId": provider.node_id,
            "scores": {
                "successRate": 0,
                "uptime": uptime_percentage / 100
            }
        })

    # Store the response in Redis
    r.set('provider_scores', json.dumps(response))