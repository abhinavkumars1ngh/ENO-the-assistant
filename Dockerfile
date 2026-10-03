FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENO_MODE=cloud

WORKDIR /app

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY backend ./backend

EXPOSE 8000

# --no-access-log: websocket URLs carry the session token as a query param and we do not want
# request lines (tokens, chat ids) landing in host logs. App code never logs chat bodies.
# $PORT is injected by Render/Railway/Fly; default 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log --proxy-headers --forwarded-allow-ips='*'"]
