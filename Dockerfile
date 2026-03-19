FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5555

ENV PYTHONUNBUFFERED=1
ENV BOOKFACTORY_HOST=0.0.0.0

CMD ["python", "run.py"]
