# Envelhecimento Seguro: imagem única (nginx + .NET API + Python analytics).
# Contexto de build = raiz do repositório:  docker build -t envelhecimento-seguro .
#   :80 nginx (SPA estática + /api → .NET :5090) → .NET → Python :8091 (loopback)

# ---- 1. Frontend (Vite) ----
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/webapp/package.json frontend/webapp/package-lock.json ./
RUN npm ci
COPY frontend/webapp ./
RUN npm run build

# ---- 2. API .NET ----
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS api
WORKDIR /src
COPY backend/webapi ./backend/webapi
RUN dotnet publish backend/webapi/EnvelhecimentoSeguro.WebApi.csproj -c Release -o /out /p:UseAppHost=false

# ---- 3. Venv Python (fastparquet não tem wheel p/ 3.14: compila com git + gcc, fora da imagem final) ----
FROM python:3.14-slim AS pyenv
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/
RUN apt-get update \
 && apt-get install -y --no-install-recommends git build-essential \
 && rm -rf /var/lib/apt/lists/*
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/py/.venv
WORKDIR /app/py
COPY backend/webapi-python/pyproject.toml backend/webapi-python/uv.lock ./
RUN uv sync --locked --extra etl --no-install-project

# ---- 4. Runtime ----
FROM python:3.14-slim
COPY --from=mcr.microsoft.com/dotnet/aspnet:10.0 /usr/share/dotnet /usr/share/dotnet

ENV DOTNET_ROOT=/usr/share/dotnet \
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 \
    DOTNET_gcServer=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/share/dotnet:/app/py/.venv/bin:$PATH" \
    DATA_DIR=/data \
    TZ=America/Sao_Paulo

RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx libicu-dev ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

# Python: extra "etl" (PySUS + pandas) para o botão de atualização dos dados.
WORKDIR /app/py
COPY --from=pyenv /app/py/.venv ./.venv
COPY backend/webapi-python/analytics ./analytics
COPY backend/webapi-python/etl ./etl

COPY --from=api /out /app/api
COPY --from=web /web/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/app.conf
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && mkdir -p /data

VOLUME /data
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1/api/dataset/status', timeout=4)" || exit 1
ENTRYPOINT ["/entrypoint.sh"]
