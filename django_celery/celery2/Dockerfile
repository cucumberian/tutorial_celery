FROM python:3.11.8-slim-bullseye
RUN mkdir -p /usr/src/app/
WORKDIR /usr/src/app/
COPY . .
RUN pip install -U pip && pip install --no-cache-dir -r requirements.txt
