FROM python:3.13-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN mkdir core && touch core/__init__.py
RUN pip install --user --no-cache-dir .

FROM python:3.13-slim
WORKDIR /app
RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser -s /bin/bash appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]