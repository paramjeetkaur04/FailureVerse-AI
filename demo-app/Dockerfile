FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY demo-app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10002 demo \
    && useradd --uid 10002 --gid demo --no-create-home demo
COPY demo-app/app.py ./app.py
USER 10002:10002
EXPOSE 5001
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "1", "--threads", "2", "--timeout", "10", "--access-logfile", "-", "app:app"]
