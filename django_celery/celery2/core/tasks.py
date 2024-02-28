import time
from datetime import datetime
from celery import shared_task
from .models import Task


@shared_task
def task_process(task_id):
    time.sleep(10)
    print(Task.objects.all())
    task = Task.objects.get(id=task_id)
    task.result = len(Task.objects.all())
    task.is_completed = True
    task.finished_at = datetime.now()
    task.save()
    return task.result
