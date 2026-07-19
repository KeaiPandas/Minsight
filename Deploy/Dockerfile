FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MINSIGHT_HOST=0.0.0.0
ENV MINSIGHT_PORT=8788
ENV MINSIGHT_DB_PATH=/data/minsight_deploy.sqlite

WORKDIR /app

COPY Deploy/requirements.txt /app/Deploy/requirements.txt
RUN pip install --no-cache-dir -r /app/Deploy/requirements.txt

COPY Core /app/Core
COPY Deploy /app/Deploy

VOLUME ["/data"]
EXPOSE 8788

CMD ["python", "Deploy/server.py"]
