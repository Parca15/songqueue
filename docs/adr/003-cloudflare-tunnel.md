# ADR 003: Demo pública con Cloudflare Tunnel

Fecha: 2026-09-08 · Estado: aceptado

## Contexto

Exponer una demo pública del proyecto (útil para portafolio y pruebas con
celulares reales escaneando QRs).

## Opciones

1. **Cloudflare Tunnel** hacia el stack actual (elegido).
2. VPS con DNS/proxy de Cloudflare.
3. Reescritura full-serverless (Workers + D1 + Durable Objects).

## Decisión

Tunnel (`cloudflared` como servicio opcional por perfil en compose).

- Cero cambios de código de negocio: FastAPI + MySQL + WebSockets en memoria
  siguen en una réplica; el túnel solo publica el puerto 80.
- `SERVER_BASE_URL=https://dominio` hace que los QR apunten al dominio
  público; el fallback `.local`/IP LAN solo aplica sin dominio configurado.
- La opción 3 se descartó: SQLAlchemy + aiomysql + yt-dlp + WS en memoria no
  son portables a Workers y el costo de reescritura no compensa para una demo.

## Consecuencias

- Una sola réplica (el broadcast WS y los locks de alta son en memoria).
- Escalar horizontalmente requeriría pub/sub externo (p. ej. Redis) — fuera
  de alcance actual, documentado aquí como límite conocido.
