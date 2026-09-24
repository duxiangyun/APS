FROM python:3.13-slim

WORKDIR /app/src/web
COPY src/web/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8000

EXPOSE 8000
WORKDIR /app/src/web
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
