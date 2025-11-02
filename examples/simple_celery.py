import time
import datetime
from celery import Celery

app = Celery("myapp", broker="pyamqp://quest@192.168.0.122//")


@app.task
def generate_report_task(arg1, arg2):
    print("Start generating report")
    time.sleep(10)
    print("Report generated")


arg_value_1 = "value1"
arg_value_2 = "value2"

generate_report_task.apply_async(
    args=[
        arg_value_1,
    ],
    kwargs={"arg2": arg_value_2},
)


@app.task
def publish_article(arg1, arg2):
    print(f"Publish time: {datetime.datetime.now()}")


publish_article_after = 60 * 60  # 60 минут
result = publish_article.apply_async(
    kwargs={"arg1": "article title", "arg2": "article body"},
    countdown=publish_article_after,
)
