FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs

RUN groupadd -r botuser && useradd -r -g botuser botuser
RUN chown -R botuser:botuser /app

USER botuser

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]