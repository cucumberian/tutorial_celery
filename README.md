# Celery

## Часть 1

[статья](https://habr.com/ru/articles/770020/)

### Добавление задачи в очередь

```python
import time
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
```

`.apply_async` - добавление задачи в очередь для выполнения. В данном случае, задача `generate_report_task` будет выполнена асинхронно с переданными аргументами.

### Выполнение задачи через час

- самый простой способ - аргумент `countdown` в `apply_async`.

```python
@app.task
def publish_article(arg1, arg2):
    print(f"Publish time: {datetime.datetime.now()}")

publish_article_after = 60 * 60  # 60 минут
result = publish_article.apply_async(
    kwargs={"arg1": "article title", "arg2": "article body"},
    countdown=publish_article_after,
)
```

> __Важно для Redis Backend__
Данный способ не подойдет, если вы используете Redis в качестве брокера. Дело в том, что Redis помещает отложенные задачи в очередь `unacked`, из которой по истечение времени, указанного в аргументе `VISIBILITY_TIMEOUT`, задача будет назначена еще одному обработчику. Например, `countdown` у нас равен 120 минутам, а `VISIBILITY_TIMEOUT` по умолчанию 60. В таком случае есть риск, что задача будет назначена сразу трём обработчикам (первому сразу, второму через 60 минут, третьему - если задача через 120 минут будет еще в очереди). В результате, мы получим выполнение одной и той же задачи несколько раз. Подробнее в документации [тут](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html#redis-caveats) и [тут](https://docs.celeryq.dev/en/latest/userguide/calling.html#eta-and-countdown).

> __Важно для RabbitMQ Backend__
Параметр `consumer_timeout` по умолчанию равен 30 минутам. Не желательно устанавливать `countdown` больше этого времени, иначе будет возбуждено исключение `PRECONDITION_FAILED`. Если есть такая необходимость, необходимо увеличить время в `rabbitmq.conf`. Подробнее - [тут](https://docs.celeryq.dev/en/latest/userguide/calling.html#eta-and-countdown).

### Выполнение задачи в определённое время

- при использовании Redis отложенные задачи с помощью `eta` столкнутся с той же проблемой, что и `countdown` из-за `VISIBILITY_TIMEOUT`.

- `eta` - это не точное время, в которое будет выполнена задача. Задача будет выполнена не раньше этого времени в порядке очереди.

### Статусы задач

#### Результат и статус задачи

Для получения статуса задачи можно использовать её `id`.

```python

task = publish_article.apply_async(kwargs={"arg1": 1, "arg2": 2})
task_id = task.id


def get_task_status_with_result(task_id: str):
    task = AsyncResult(id=task_id)
    return {
        "id": task_id,
        "status": task.status,
        "result": TaskResponse.model_validate_json(task.result),
    }
```

#### Статусы всех задач

```python
PENDING, STARTED, RETRY, FAILURE, SUCCESS, REVOKED
```

Чтобы получить статусы всех лучше знать и id. Далее можно опрашивать напрямую редис или через python-библиотеку celery.

Также можно использовать `celery_app.control.inspect`.

- `python celery` клиент - самый лучший способ, но надо знать ид задачи
- `redis` - redis не гарантирует стабильный формат ключей и данных
- `flower api` - можно получить статусы задач через рест апи.
- `celery.inspect` - общается с активными воркерами и показывает только те задачи, которые известны воркерам. Т.е. не показывает завершенные задачи (`SUCCESS` `FAILURE`).

Пример получения задач через inpect:

```python
i = app.control.inspect()
active = i.active()       # Выполняющиеся задачи
reserved = i.reserved()   # взяты воркером из брокера и ожидающие выполнения
scheduled = i.scheduled() # отложенные задачи
revoked = i.revoked()     # отмененные задачи
```

Данные запрос через inspect довольно длительный и работает только с активными воркерами.

## Celery beat

[link](https://habr.com/ru/articles/820073/)

Основные компоненты:

- __планировщик (Scheduler)__ - управляет периодическими задачами. Проверяет расписание и отправляет задачи в очередь в нужное время.

- __рабочие узлы (worker nodes)__ - забирают задачи и выполняют их. Каждый узел может выполнять множество задач параллельно.

- __посредник (broker)__ - используется для передачи сообщений между планировщиком и рабочими узлами. Управляет очередями и доставляет сообщения.

> Мы можем использовать стандартный планировщик или подключить другой. Вот два сторонних планировщика для примера:

- [DatabaseScheduler](https://github.com/celery/django-celery-beat/blob/main/django_celery_beat/schedulers.py) из django-celery-beat. Хранит расписание в базе данных.

- [RedBeatScheduler](https://github.com/sibson/redbeat/tree/main) из RedBeat. Хранит расписание в Redis.

### Настройка

```python
import logging
import time
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
```

В `beat_schedule` мы передаем словарь с настройками расписания для задач.

Полный список возможных параметров

- `task`: Имя задачи в формате строки. Например, `'celery_app.test'`

- `schedule`: Объект, определяющий расписание выполнения задачи.
Например, `timedelta(seconds=10), crontab(minute='*/5')`.

- `args`: Список или кортеж с позиционными аргументами для задачи. Например, `(1, 2, 3)`.

- `kwargs`: Словарь с именованными аргументами для задачи. Например, `{"foo": "bar"}`.

- `options`: Словарь с дополнительными параметрами выполнения задачи. Принимает всё, что поддерживает `apply_async()`. Например, `{"queue": "default", "priority": 10}`.

- `relative`: Флаг, указывающий на использование относительного расписания. Например, `True`.

В `schedule` мы передаем объект `timedelta`. Это основной способ, с помощью которого мы будем указывать временной интервал для задач. Его альтернатива - `crontab`. С ним бы было вот так:

```python
app.conf.beat_schedule = {
    "test": {
        "task": 'celery_app.test',  # путь к задаче
        'schedule': crontab(hour=8, minute=0),  # Ежедневно в 8 утра
    }
}
```

Можно вместо `beat_schedule` использовать `add_periodic_task`. Это позволяет добавлять задачи динамически. [документация](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)

```python
@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    sender.add_periodic_task(
        timedelta(seconds=5),
        run.s(),
        name="run scheduler service every 5 seconds",
    )
```

### Запуск периодических задач

Теперь пора перейти непосредственно к запуску. У нас есть возможность использовать две разных команды:

```sh
celery -A celery_app worker -B --loglevel=INFO
```

```sh
celery -A celery_app beat --loglevel=INFO
```

__Первая команда__ запускает рабочий узел, который одновременно будет являться и планировщиком. Эта команда лучше всего подходит для отладки и не рекомендуется для запуска в production среде. Дело в том, что в этом случае на работу планировщика могут повлиять выполняемые задачи, что может привести к сбоям.

__Вторая команда__ запускает только планировщик. В таком случае он занимается только назначением задач в нужную очередь и не занимается выполнением задач. Такая схема работы более надёжна. Для того, чтобы задачи начали выполняться, нам понадобится запустить worker отдельно.

Сам рабочий узел мы будем запускать с помощью команды:

```sh
celery -A celery_app worker
```

Запускаем beat в первом терминале, worker во втором.

## Django + Celery

[статья](https://habr.com/ru/companies/otus/articles/503380/)

1. https://habr.com/ru/companies/otus/articles/503380/  (https://github.com/testdrivenio/django-celery)
2. https://realpython.com/asynchronous-tasks-with-django-and-celery/

Celery это отдельная очередь задач, которая может собирать, получать, планировать и выполнять задачи вне основной программы.
Чтобы получить и отдавать готовые задачи celery нужен брокер сообщений для коммуникации.
Обычно вместе с Celery используется Redis и RabbitMQ.

- Celery workers - это рабочие процессы, которые выполняют задачи независимо вне основной программы.

- Celery beat - планировщик, который определяет когда запускать задачи.

### Установка

```shell
pip3 install django
...
pip3 install celery
pip3 install redis
```

Теперь можно запустить worker командой `celery worker`. Но получим сообщение об ошибке, что celery не может работать с брокером сообщений.
Celery будет безуспешно пытаться подключиться к локальному хосту по протоколу amqp - advanced message queuing protocol (https://en.wikipedia.org/wiki/Advanced_Message_Queuing_Protocol).

#### Redis

Установим redis-server

```shell
sudo apt update
sudo apt install redis
```

Конечно можно ставить отдельно в виде докер-контейнера.

Можно запустить redis-server

```shell
redis-server
```

Проверить работает ли redis

```shell
ps aux | grep redis
```

Остановить

```shell
sudo service redis-server stop
```

Пингануть

```shell
redis-cli ping
```

Запустить клиент

```shell
redis-cli
```

Установим питоновский клиент

```shell
pip install redis
pip install celery
pip install flower
```

Т.е. нам нужен редис сервер, как отдельное приложение и пакет для питоновских программ для работы с ним.

### Добавление celery у джанго проекту

Создадим файл `celery.py` в папке корневого приложенияЮ рядом c `settings.py`.

```python
# django_celery/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_celery.settings")

app = Celery("django_celery")
# app = Celery("hello", backend="redis://localhost:6379", broker="pyamqp://quest@127.0.0.1:6379/")
app.config_from_object("django.conf.settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task
def add(x, y):
    return x + y
```

Здесь мы устанавливаем переменную окружения, чтобы получить модуль джанго `project_name.settings.py` через переменную окружения `DJANGO_SETTINGS_MODULE`.

Затем создаём экземпляр приложения Celery и передаём внутрь имя нашего приложения (главного модуля).

Далее мы задаем путь до файла настроек и имя неймспейса с настройками celery. В файле конфигурации `settings.py` все настройки начинающиеся с `CELERY_` будут прочтены этим приложением. При желании можно определить и другой файл конфигурации.

Через автодисковер мы говорим приложению celery искать задачи в каждом приложении джанго.

Далее добавляем настройки для celery в `settings.py`:

```python
# settings.py

# Celery settings
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```

Данные строки дают инстансу celery достаточно информации, чтобы понять куда отправлять сообщения и куда записывать результат.
Заметим, что начинаются эти строки на имя `CELERY_`, где название `CELERY` задается как namespace в файле `celery.py` в строке `app.config_from_object("django.conf:settings", namespace="CELERY")`.

Добавим celery.app в загрузку модуля через файл `main_app/__init__.py`:

```python
# __init__.py

from .celery import app as celery_app

__all__ = ("celery_app", )
```

запуск приложения `celery_app` при запуске джанго будет гарантировать нам, что декоратор `@shared_task` будет использовать его корректно.

Теперь можно протестировать приложение. Напомним что наша связка с celery-django будет состоять из трёх модулей:

- producer - приложение джанго
- message-broker - сервер редис
- consumer - приложение celery_app в джанго

#### Запуск

- Запускаем сервер redis  `redis-server` если еще не запущен как сервис или в докере
- запускаем джанго `python manage.py runserver`
- запускаем воркер `python -m celery -A django_celery worker --loglevel=INFO`
  При запуске воркера передаём celery имя нашего джанго модуля в котором есть инстанс Celery.

  - `-A` = `--app=`
  - `-l` = `--loglevel=`
  - `-b` = `--broker=`

  Можно явно указать инстанс Celery:
  
  ```shell
  python -m celery --app=django_celery:celery_app worker --loglevel=INFO
  ```

- запускаем flower на порту 5555

```shell
python -m celery --broker=redis://127.0.0.1:6379/0 flower -A django_celery --port=5555
```

или если подтягиваем настройки для фловера из аппы

```shell
python -m celery -A django_celery flower --port=5555
```

#### Использование

Для использование надо в тексте программы добавить задачу для воркера

```python
task = add.delay(1, 2)
```

, где `add` - функция задекорированная `@celery_app.task` - специальным декоратором от инстанса Celery, который сы создали в `celery.py`.

Получить статус задачи и результат выполнения:

```python
print(task.result)
print(task.status)
```

В случае если работа ведётся с базой данных, например создаваться объект, сохраняется и потом добавляется задача, то может случиться, что воркер получит задачу и начнёт её выполнять, а значения в базе данных ещё не будет.
Тогда лучше запускать воркер после [транзакции](https://docs.djangoproject.com/en/5.0/topics/db/transactions/) в базу данных, например так:

```python
from django.db import transaction

transaction.on_commit(lambda: some_celery_task.delay(obj.id))
```

По самому celery. Уже много раз обсуждалось и везде предупреждают, но повторю — не используйте в качестве аргументов для тасков сложные объекты, например модели django. Передавайте лучше id и уже в таске получайте объект из БД. Ещё один важный момент, который может смутить начинающего разработчика на django — вьюхи, как правило, выполняются в транзакции. Это может привести к тому, сохранив новый объект и сразу отправь его id в таск вы можете получить object not found. Чтобы такого избежать, нужно использовать конструкцию типа `transaction.on_commit(lambda: some_celery_task.delay(obj.id))`

Так же можно смотреть текущие задачи и их статусы с помощью

```shell
python -m celery -A worker events
```

##### Django

Вот пример использования в django:

```python
# для запуска после транзакции
from django.db import transaction
# для декорирования задачи
from django_cel.celery import app as celery_app

class SimpleView(View):
    def post(self, request):
        value = request.POST.get("value")
        if value:
            simple = Simple(value=value)
            simple.save()
            # отдаём задачу воркеру после выполнения транзакции,
            # когда объект уже будет создан
            transaction.on_commit(lambda: simple_task.delay(simple.id))
            return JsonResponse({"id": simple.id})
        return JsonResponse({"error": "Value is required"})

# регистрируем задачу для воркера
@celery_app.task
def simple_task(simple_id):
    print(f"Simple task started with id {simple_id}")
    simple = Simple.objects.get(id=simple_id)
    simple.result = len(Simple.objects.all())
    simple.is_completed = True
    simple.save()
    print(f"Simple task finished with id {simple_id}")
    return simple_id
```

Если celery не может найти задачу (ошибка Not registered), то просто перезапустите celery.

### Конструкции celery

```python
from celery import Celery
from celery import shared_task
...
celery_app = Celery(
    "project-name",
    broker="redis://localhost:6379/0",  # можно задать потом
    backend="redis://localhost:6379/0", # можно задать потом    
)
celery_app.autodiscover_tasks(force=True)
...

# регистрация таски
@celery_app.task
def add(x, y):
    return x + y

# регистрация shared_task
@shared_task
def sub(x, y):
    return x - y

task_sub = sub.delay(2, 1)

task = add.delay(1, 2)
while not task.ready():
    pass
print(task.get())
```

#### `@shared_task` vs `@app.task`

https://docs.celeryq.dev/en/stable/userguide/tasks.html

При использовании shared_task нет необходимости икспортировать экземпляр `Celery`.
Также можно использовать `@app.task(shared=True)`.
В случае если есть несколько экземпляров Celery

```python
app1 = Celery()

app2 = Celery()

@app1.task
def test():
    pass
```

, то __таска__ `test` будет зарегистрирована в обоих иснтансах Celery, но __имя__ `test` будет относиться только к app1.
Однако `@shared_task` позволяет использовать таск в обоих инстансах.

#### bind=True

Такие задачи первым аргументом принимают себя и позволяют повторять себя при необходимости повторов.

```python
logger = get_task_logger(__name__)

@app.task(bind=True)
def add(self, x, y):
    logger.info(self.request.id)
```

Bound tasks are needed for retries (using app.Task.retry()), for accessing information about the current task request, and for any additional functionality you add to custom task base classes.

#### delay

`task.delay()` - это метод который является псевдонимом более мощного метода `.apply_async()`, у которого есть опции выполнения.

```python
@shared_task
def add_task(x, y):
    return x + y

add_task.apply_async(
    args=[1, 2]
)
```

Хотя для многих простых случаев использование `delay` является предпочтительнее, использование метода `apply_async` иногда оправдано, например со счётчиками или повторами.

#### tasks.py

Можно задать выполняемые задачи в файле tasks.py.

```python
#tasks.py
from celery import shared_task


@shared_task
def hello():
    print("Hello Celery")

@shared_task
def add(x, y):
    return x + y
```

### docker-compose

```shell
services:
  redis:
    image: redis:7.2.4-alpine3.19
    # ports:
    #   - 6379:6379
  
  postgres:
    image: postgres:13.14-alpine3.19
    restart: always
    # ports:
    #   - "5444:5432"
    env_file: .env
    environment:
      - POSTGRES_USER=$POSTGRES_USER
      - POSTGRES_PASSWORD=$POSTGRES_PASSWORD
      - POSTGRES_DB=$POSTGRES_DB
    volumes:
      - postgresql_volume:/var/lib/postgresql/data

  django:
    build:
      context: celery2
      dockerfile: Dockerfile
    command: sh -c "python manage.py makemigrations && python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"
    ports:
      - 8080:8000
    env_file: .env
    environment:
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
    depends_on:
      - redis
      - postgres

    
  worker:
    build:
      context: celery2
      dockerfile: Dockerfile
    command: python -m celery -A celery2:celery_app worker
    env_file: .env
    environment:
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
    depends_on:
      - redis
      - postgres
  
  flower:
    build:
      context: celery2
      dockerfile: Dockerfile
    command: python -m celery -A celery2 flower --port=5555
    ports:
      - "5555:5555"
    env_file: .env
    environment:
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
    depends_on:
      - redis
      - postgres



volumes:
  postgresql_volume:
    name: postgresql_volume
```

Чтобы изменить количество запущенных контейнеров с воркерами можно воспользоваться командой

```shell
docker-compose up -d --build --scale worker=3
```

### Celery для произвольного проекта

Задача - запустить асинхронный расчет хэша от строки.
Т.к. задача асинхронная, то выполнять её можно в отдельном процессе.
А в главной программе мы будем асинхронно ожидать выполнения этого процесса через `asyncio.sleep`.

1. Создаем экземпляр celery приложения в файле `celery_app.py`

    ```python
    import time
    import hashlib
    from celery import Celery

    celery_app = Celery(
        "tasks", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0"
    )

    celery_app.conf.broker_url = Config.CELERY_BROKER_URL
    celery_app.conf.result_backend = Config.CELERY_RESULT_BACKEND
    celery_app.conf.update(result_expires=3600)

    @celery_app.task
    def calc_hash(string: str) -> str:
        time.sleep(10)
        hash_str = hashlib.sha256(string.encode()).hexdigest()
        return hash_str
    ```

2. Используем эту задачу в коде:

    ```python
    import asyncio
    from celery_app import celery_hash

    async def calc_hash(string: str) -> str:
    """
    Асинхронный расчёт хэша в отдельном процессе Celery воркера
    """
    task = celery_hash.delay(string=string)
    while not task.ready():
        asyncio.sleep(0.1)
    return task.result
    ```

3. Запускаем воркера

    ```shell
    celery -A celery_app worker --loglevel=INFO
    ```

4. Запускаем наше приложение
