FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir gunicorn==22.0.0

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-k", "gthread", "--threads", "8", "-w", "1", "-b", "0.0.0.0:5000", "app:app"]
