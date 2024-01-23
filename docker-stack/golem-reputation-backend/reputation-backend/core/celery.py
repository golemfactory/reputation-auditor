from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
import logging
from celery.schedules import crontab
from random import randint


logger = logging.getLogger("Celery")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    from api.tasks import monitor_nodes_task, ping_providers_task, benchmark_providers_task, process_offers_from_redis

    sender.add_periodic_task(
        40.0,
        monitor_nodes_task.s(),
        queue="uptime",
        options={"queue": "uptime", "routing_key": "uptime"},
    )
    sender.add_periodic_task(
        30.0,
        ping_providers_task.s(p2p=False),
        queue="pinger",
        options={"queue": "pinger", "routing_key": "pinger"},
    )
    # sender.add_periodic_task(
    #     30.0,
    #     ping_providers_task.s(p2p=True),
    #     queue="pingerp2p",
    #     options={"queue": "pingerp2p", "routing_key": "pingerp2p"},
    # )
    sender.add_periodic_task(
        60,
        # 60 * 60 * randint(8, 12),  # This generates a random interval between 8 and 12 hours in seconds to hopefully avoid all providers benchmarking at the same time on different auditors
        benchmark_providers_task.s(),
        queue="benchmarker",
        options={"queue": "benchmarker", "routing_key": "benchmarker"},
    )
    sender.add_periodic_task(
        30.0,
        process_offers_from_redis.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    

app.conf.task_default_queue = "default"
app.conf.broker_url = "redis://redis:6379/0"
app.conf.result_backend = "redis://redis:6379/0"
app.conf.task_routes = {
    "app.tasks.default": {"queue": "default"},
    "app.tasks.uptime": {"queue": "uptime"},
    "app.tasks.pinger": {"queue": "pinger"},
    "app.tasks.pinger": {"queue": "benchmarker"},
}
