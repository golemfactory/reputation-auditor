# main.py or any other file from which you want to trigger the task

from .scanner import monitor_nodes_status  # Import the task
import asyncio
from core.celery import app
from celery import Celery
from .ping import ping_providers


@app.task
def monitor_nodes_task(subnet_tag='public'):
    # Run the asyncio function using asyncio.run()
    asyncio.run(monitor_nodes_status(subnet_tag))


@app.task
def ping_providers_task():
    asyncio.run(ping_providers())
    