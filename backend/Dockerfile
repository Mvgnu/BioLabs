FROM python:3.11-slim
RUN apt-get update && apt-get install -y build-essential gcc make && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY alembic.ini ./
COPY alembic ./alembic
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
