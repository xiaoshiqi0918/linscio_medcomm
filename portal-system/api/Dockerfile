FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends apache2-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://mirrors.tencent.com/pypi/simple/

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8001", \
     "--workers", "4", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
