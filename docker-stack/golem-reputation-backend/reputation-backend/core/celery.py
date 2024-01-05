from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
import logging
from celery.schedules import crontab


logger = logging.getLogger("Celery")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    from api.tasks import monitor_nodes_task, ping_providers_task

    sender.add_periodic_task(
        40.0,
        monitor_nodes_task.s(),
        queue="uptime",
        options={"queue": "uptime", "routing_key": "uptime"},
    )
    sender.add_periodic_task(
        30.0,
        ping_providers_task.s(),
        queue="pinger",
        options={"queue": "pinger", "routing_key": "pinger"},
    )
    

app.conf.task_default_queue = "default"
app.conf.broker_url = "redis://redis:6379/0"
app.conf.result_backend = "redis://redis:6379/0"
app.conf.task_routes = {
    "app.tasks.default": {"queue": "default"},
    "app.tasks.uptime": {"queue": "uptime"},
    "app.tasks.pinger": {"queue": "pinger"},
}
