import logging
import datetime
from celery import Celery
from celery.signals import after_setup_logger

logger = logging.getLogger(__name__)

app = Celery("tasks", broker="pyamqp://quest@localhost//")

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,    # переопределяем настройки логирования
)

app.autodiscover_tasks()


@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh = logging.FileHandler("logs.log")
    fh.setFormatter(formatter)
    logger.addHandler(fh)


@app.task
def test():
    logger.info("Its working")
    return True


app.conf.beat_schedule = {
    "test": {
        "task": "celery_app.test",
        "schedule": datetime.timedelta(seconds=10),
    }
}
