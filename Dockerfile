# DayTrader Autonomous Bi-Directional Intraday Trading System
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project codebase
COPY . .

# Expose web server port
EXPOSE 5000

ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Kolkata

CMD ["python", "app.py"]

