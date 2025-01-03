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
    from api.tasks import monitor_nodes_task, ping_providers_task, process_offers_from_redis, update_provider_scores, get_blacklisted_operators, get_blacklisted_providers, delete_old_ping_results
    from stats.tasks import populate_daily_provider_stats, cache_provider_success_ratio, cache_provider_uptime, cache_cpu_performance_ranking, cache_gpu_performance_ranking

    sender.add_periodic_task(
        crontab(minute=0, hour=0),  # daily at midnight
        cache_provider_success_ratio.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        crontab(minute='*/10'),  # every 10 minutes
        cache_provider_uptime.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        crontab(minute=0, hour=0),  # daily at midnight
        delete_old_ping_results.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        300.0,
        monitor_nodes_task.s(),
        queue="uptime",
        options={"queue": "uptime", "routing_key": "uptime"},
    )
    sender.add_periodic_task(
        300.0,
        update_provider_scores.s(network="mainnet"),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        3600,  # 1 hour
        populate_daily_provider_stats.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        120.0,
        get_blacklisted_providers.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        120.0,
        get_blacklisted_operators.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        60.0,
        update_provider_scores.s(network="testnet"),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
#    sender.add_periodic_task( Not needed anymore, separate docker task now.
#        30.0,
#        ping_providers_task.s(p2p=False),
#        queue="pinger",
#        options={"queue": "pinger", "routing_key": "pinger"},
#    )
    sender.add_periodic_task(
        30.0,
        process_offers_from_redis.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        600.0,  # 10 minutes
        cache_cpu_performance_ranking.s(),
        queue="default",
        options={"queue": "default", "routing_key": "default"},
    )
    sender.add_periodic_task(
        600.0,  # 10 minutes
        cache_gpu_performance_ranking.s(),
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
