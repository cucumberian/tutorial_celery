# Asynchronous Tasks With Django and Celery
1. https://habr.com/ru/companies/otus/articles/503380/  (https://github.com/testdrivenio/django-celery)
2. https://realpython.com/asynchronous-tasks-with-django-and-celery/


Celery это отдельная очередь задач, которая может собирать, получать, планировать и выполнять задачи вне основной программы.
Чтобы получить и отдавать готовые задачи celery нужен брокер сообщений для коммуникации.
Обычно вместе с Celery используется Redis и RabbitMQ.
- Celery workers - это рабочие процессы, котрые выполняют задачи независимо вне основной программы.
- Celery beat - планировщик, который определяет когда запускать задачи.

## Установка
```shell
pip3 install django
...
pip3 install celery
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

### Подключение воркера
Попробуем снова запустить воркера для нашего джанго приложения
```shell
python -m celery -A django_celery worker
```
, где `django_celery` - название инстанса celery из файла `celery.py`.
Опять получим ошибку, т.к. в нашем приложении еще нет точки доступа для celery. Исправим это.

## Добавление celery у джанго проекту
Создадим файл `celery.py` в папке корневого приложенияЮ рядом c `settings.py`.
```python
# project_name/celery.py
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_celery.settings")

app = Celery("django_celery")
# app = Celery("hello", backend="redis://localhost:6379", broker="pyamqp://quest@127.0.0.1:6379/")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task
def add(x, y):
    return x + y
```
Здесь мы устанавливаем переменную окружения, чтобы получить модуль джанго `project_name.settings.py` через переменную окружения `DJANGO_SETTINGS_MODULE`.

Затем создаём экземпляр приложения Celery и передаём внутрь имя нашего приложения (главного модуля).

Далее мы задаем путь до файла настроек и имя неймспейса с настройками celery. В файле конфигурации `settings.py` все настройки начинающиеся с `CELERY_` будут прочтены этим приложение. При желании можно определить и другой файл конфигурации.

Через автодисковер мы говорим приложению celery искать задачи в каждом приложении джанго.

Далее добавляем настройки для celery в `settings.py`:
```python
# settings.py

# Celery settings
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```
Данные строки дают инстансу celery достаточно информации, чтобы понять куда отправлять сообщения и куда записывать результат.
Заметим, что начинаются эти строки на имя `CELERY_`, где название `CELERY` задается как namespace в файле celery.py в строке `app.config_from_object("django.conf:settings", namespace="CELERY")`.

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


### Запуск

- Запускаем сервер redis  `redis-server` если еще не запущен как сервис или в докере
- запускаем джанго `python manage.py runserver`
- запускаем воркер `python -m celery -A django_celery  worker --loglevel=INFO`
    При запуске воркера передаём celery имя нашего джанго модуля в котором есть инстанс Celery.
    - `-A` = `--app=`
    - `-l` = `--loglevel=`
    - `-b` = `--broker=`
    Можно явно указать инстанс Celery:
    ```shell
    python -m celery --app=django_celery:celery_app --loglevel=INFO
    ```
- запускаем flower на порту 5555
```shell
python -m celery --broker=redis://127.0.0.1:6379/0 flower -A django_celery --port=5555
```
или если подтягиваем настройки для фловера из аппы
```shell
python -m celery -A django_celery flower --port=5555
```

### Использование
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
#### Django
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

## Конструкции celery
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

### `@shared_task` vs `@app.task`
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

### bind=True
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

### tasks.py
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

## docker-compose
```shell
version: "3"

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