FROM python:3.14.7-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src

CMD ["python", "-m", "src.pipeline"]

