FROM python:3.12-slim

WORKDIR /app/ingestion

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Unbuffered so `docker logs` / `kubectl logs` show output as it happens,
# not only after Python's internal buffer fills or the process exits.
ENV PYTHONUNBUFFERED=1

CMD ["python", "ttc_producer.py"]
