FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache gcc musl-dev libffi-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt && \
    rm -rf /root/.cache /tmp/*

COPY main.py config.py requirements.txt .
COPY cogs/ ./cogs/
COPY database/ ./database/
COPY utils/ ./utils/

RUN mkdir -p /app/data

CMD ["python", "main.py"]
