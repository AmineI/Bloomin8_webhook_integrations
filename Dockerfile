# Build from the repository root:
#   docker build -f Dockerfile.starlette .

FROM python:3.14.6-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt update && apt install -y bluetooth
COPY requirements.txt server-requirements.txt /tmp/
RUN python -m pip install --no-cache-dir -r /tmp/server-requirements.txt

COPY pybloomin8/ /app/pybloomin8/
COPY webhook_helpers/ /app/webhook_helpers/
COPY webhook_server.py /app/

EXPOSE 7072
CMD ["uvicorn", "webhook_server:app", "--host", "0.0.0.0", "--port", "7072"]