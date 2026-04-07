from celery import Celery
from kombu import Exchange, Queue

from core.config import settings

celery_app = Celery(
    "pinterest",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=["pins.task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
)


celery_app.conf.update(
    task_queues=(Queue("default", Exchange("default"), routing_key="default"),),
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)
