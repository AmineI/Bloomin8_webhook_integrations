# Build from the repository root: docker build .

FROM python:3.14.7-alpine3.24

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apk update && apk add --no-cache \
    bluez \
    dbus \
    udev

COPY requirements.txt server-requirements.txt /tmp/
RUN python -m pip install --no-cache-dir -r /tmp/server-requirements.txt

COPY pybloomin8/ /app/pybloomin8/
COPY webhook_helpers/ /app/webhook_helpers/
COPY webhook_server.py /app/

EXPOSE 7072
CMD ["uvicorn", "webhook_server:app", "--host", "0.0.0.0", "--port", "7072"]