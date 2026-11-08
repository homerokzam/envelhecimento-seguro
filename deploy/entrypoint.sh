#!/bin/sh
# Sobe Python → .NET → nginx; se qualquer processo morrer, o container encerra (e é reiniciado).
set -eu

(cd /app/py && PORT=8091 python -m analytics.server) &
ASPNETCORE_HTTP_PORTS=5090 Analytics__BaseUrl=http://127.0.0.1:8091 dotnet /app/api/EnvelhecimentoSeguro.WebApi.dll &
nginx -g 'daemon off;' &

wait -n
exit 1
