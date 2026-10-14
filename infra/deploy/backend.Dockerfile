# Production image for the Django backend. Build context: the repo's backend/.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Not root: the app has no reason to own its own code at runtime. It does get
# a home directory, which gunicorn uses for its control socket.
RUN useradd --system --create-home app \
    && mkdir -p /app/staticfiles \
    && chown app /app/staticfiles
USER app

EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.prod.sh"]
