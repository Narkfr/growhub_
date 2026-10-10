# Image du backend GrowHub (Django 5.2 + DRF, ASGI pour le flux SSE).
#
# Le contexte de build est la racine du dépôt (voir docker-compose.yml) : les
# dépendances épinglées vivent dans `requirements/common.txt`. En exploitation,
# Compose monte le dépôt par-dessus /app — le code exécuté est celui du dépôt et
# les commandes de gestion écrivent côté hôte. La copie ci-dessous est le repli
# qui rend l'image utilisable seule.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=growhub.settings

WORKDIR /app

# psycopg[binary] embarque libpq : ni compilateur ni paquet système à installer.
COPY requirements/common.txt requirements/common.txt
RUN pip install --no-cache-dir -r requirements/common.txt

COPY gateway/backend gateway/backend

EXPOSE 8000
CMD ["uvicorn", "growhub.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "gateway/backend"]
