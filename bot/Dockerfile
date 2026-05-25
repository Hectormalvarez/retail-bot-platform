FROM python:3.13-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc python3-dev
COPY pyproject.toml .
RUN touch main.py && mkdir handlers && touch handlers/__init__.py
RUN pip install --user --no-cache-dir ".[dev]"

FROM python:3.13-slim
WORKDIR /app
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
CMD ["python", "main.py"]