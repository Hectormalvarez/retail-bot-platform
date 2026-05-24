# Retail Bot Platform

A multi-tenant, headless e-commerce engine controlled via Telegram.

## Architecture

- **Bot Engine**: Stateless Python (python-telegram-bot)
- **API**: Django REST Framework
- **Data**: PostgreSQL
- **Cache**: Redis
- **Gateway**: Nginx

## Quick Start

```bash
git clone https://github.com/hadev/retail-bot-platform.git
cd retail-bot-platform
docker compose up -d

```
