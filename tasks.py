from celery import Celery

app = Celery("hello", backend="redis://localhost:6379", broker="pyamqp://quest@127.0.0.1:6379/")


@app.task
def hello():
    print("Hello Celery")


@app.task
def add(x, y):
    return x + y
