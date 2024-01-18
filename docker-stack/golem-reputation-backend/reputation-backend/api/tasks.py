# main.py or any other file from which you want to trigger the task

from .scanner import monitor_nodes_status  # Import the task
import asyncio
from core.celery import app
from celery import Celery
from .ping import ping_providers
import subprocess
import redis
import json
from .models import Task, Provider, Offer
redis_client = redis.Redis(host='redis', port=6379, db=0)  # Update with your Redis configuration


@app.task
def monitor_nodes_task(subnet_tag='public'):
    # Run the asyncio function using asyncio.run()
    asyncio.run(monitor_nodes_status(subnet_tag))


@app.task
def ping_providers_task():
    asyncio.run(ping_providers())
    

@app.task(queue='benchmarker', options={'queue': 'benchmarker', 'routing_key': 'benchmarker'})
def benchmark_providers_task():
    testnet_provider_count = Provider.objects.filter(network='mainnet').count()
    print(f"Found {testnet_provider_count} providers on testnet")
    command = f"cd /benchmark && yagna payment fund && npm run benchmark -- {testnet_provider_count}"
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
        offer_data = json.loads(redis_client.get(key))
        _, task_id, node_id = key.decode('utf-8').split(':')
        
        try:
            task = Task.objects.get(id=task_id)
            provider = Provider.objects.get(node_id=node_id)
            offers_to_create.append(Offer(task=task, provider=provider, offer=offer_data))

            # Optionally, delete the key from Redis after processing
            redis_client.delete(key)
        except (Task.DoesNotExist, Provider.DoesNotExist):
            continue

    # Bulk create offers
    Offer.objects.bulk_create(offers_to_create)