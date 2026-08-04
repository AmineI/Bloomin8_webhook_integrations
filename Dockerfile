# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.12-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.12

# Build from the repository root: docker build .
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHONPATH=/home/site/wwwroot

# The stop debounce lives in a module global, so every webhook must reach the same worker.
ENV FUNCTIONS_WORKER_PROCESS_COUNT=1

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

COPY function_app.py host.json /home/site/wwwroot/
COPY webhook_helpers/ /home/site/wwwroot/webhook_helpers/
# Placed beside function_app.py so `python -m pybloomin8` resolves and its state
# directory lands in /home/site/wwwroot/bloomin8-state.
COPY pybloomin8/ /home/site/wwwroot/pybloomin8/