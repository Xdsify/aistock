FROM python:3.11-slim

WORKDIR /app

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# grpcio/grpcio-tools 有 manylinux wheel, 无需 gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 50051
CMD ["python", "src/main.py"]
