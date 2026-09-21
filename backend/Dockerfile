FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

RUN chmod +x scripts/generate_proto.sh && ./scripts/generate_proto.sh

EXPOSE 8000 50051

CMD ["python", "-m", "app.main"]
