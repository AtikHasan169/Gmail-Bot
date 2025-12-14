FROM python:3.11-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY . .
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "app.bot"]