# SongQueue

![CI](https://github.com/Parca15/songqueue/actions/workflows/ci.yml/badge.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![Coverage 51%+](https://img.shields.io/badge/coverage-51%25%2B-green)
[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Parca15/songqueue)

Sistema de cola de canciones multi-local: los clientes escanean un QR, registran su nombre y piden canciones de YouTube; el admin aprueba desde una lista de espera y el reproductor las suena en un TV. Todo en tiempo real por WebSockets. Hay un super admin con acceso total a las cuentas.

## Características

- **Multi-local**: cada local tiene su cola, configuración y QR único
- **Lista de espera con aprobación**: el admin aprueba como prioridad o al final, o rechaza (el toggle por local permite entrada directa)
- **Nombres de cliente**: registro único por local, visible junto a cada canción en el panel
- **Super admin**: CRUD de cuentas, renombres, reset de claves, gestión de cualquier local
- **Tiempo real**: WebSockets con broadcast por local y rol (cliente/player/admin)
- **Seguridad**: JWT con roles, rate limiting, CORS explícito, secretos fail-fast, sin defaults inseguros
- **Calidad**: 38 tests pytest, black/isort/flake8 + coverage en CI, migraciones Alembic

## Arquitectura

```mermaid
flowchart LR
    subgraph Clientes
        C[Cliente QR]
        A[Panel admin]
        T[Reproductor TV]
    end
    subgraph Edge
        N[nginx estáticos + proxy]
        CF[Cloudflare Tunnel]
    end
    subgraph App[FastAPI]
        R[(MySQL)]
        WS[Broadcast WS por local]
    end
    C --> N
    A --> N
    T --> N
    N --> App
    CF --> N
    App --> R
    WS --> C
    WS --> A
    WS --> T
```

```
songqueue/
├── docker-compose.yml      # MySQL + App + nginx (+ cloudflared opcional)
├── Dockerfile              # Imagen no-root de la app
├── src/
│   ├── main.py             # Entry point FastAPI (lifespan, CORS, rate limit)
│   ├── config.py           # Pydantic Settings fail-fast
│   ├── database.py         # SQLAlchemy async
│   ├── models/             # Venue, QueueItem, User, VenueClient, ...
│   ├── schemas/            # Pydantic schemas
│   ├── routers/            # auth, super, venues, songs, queue, playlists, ws
│   ├── services/           # Lógica de negocio
│   └── utils/              # JWT, auth por rol, rate limiting, QR
├── alembic/                # Migraciones (005: users)
├── tests/                  # pytest (38 tests, SQLite temporal)
├── docs/adr/               # Decisiones de arquitectura
├── seed_data.py            # Datos de ejemplo (uso manual/dev)
└── frontend/               # HTML/CSS/JS vanilla + design-system propio
    ├── index.html / join.html  # Cliente (QR)
    ├── admin.html          # Panel admin + vista super admin
    └── player.html         # Reproductor TV (YouTube embed)
```

## Quick Start

### Local (desarrollo)

```bash
# 1. Variables de entorno (SECRET_KEY obligatorio: openssl rand -hex 32)
cp .env.example .env

# 2. MySQL en Docker
docker compose up -d db

# 3. Entorno virtual
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Migraciones y seed (opcional)
alembic upgrade head
python seed_data.py

# 5. Lint + tests
black --check src/ tests/ && isort --check-only src/ tests/ \
  && flake8 src/ tests/ --max-line-length=120 --extend-ignore=E203,W503
pytest -q --cov=src --cov-fail-under=50

# 6. Servidor
uvicorn src.main:app --reload
```

### Docker completo

```bash
# Requiere DB_PASSWORD y SECRET_KEY en .env (falla rápido si faltan)
docker compose up -d --build
```

### Demo pública (Cloudflare Tunnel)

```bash
CLOUDFLARE_TUNNEL_TOKEN=xxx SERVER_BASE_URL=https://tu-dominio \
  docker compose --profile tunnel up -d --build
```

### Deploy en Render (producción)

```bash
# 1. Crear cuenta en https://render.com (conectar GitHub)

# 2. Crear base de datos MySQL en TiDB Cloud (gratis)
#    → https://tidbcloud.com → Create Cluster → Serverless
#    → Copiar connection string

# 3. En Render → New + → Web Service → Conectar repo
#    → Configurar env vars:
#       DATABASE_URL=mysql+aiomysql://user:pass@host:4000/songqueue
#       SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(32))">
#       SUPER_ADMIN_USERNAME=superadmin
#       SUPER_ADMIN_PASSWORD=<contraseña_segura>
#       SERVER_BASE_URL=https://songqueue.onrender.com

# 4. Auto-deploy: cada push a main despliega automáticamente
```

| Servicio | URL |
|----------|-----|
| Admin | `https://songqueue.onrender.com/admin.html` |
| Cliente | `https://songqueue.onrender.com/?venue=1` |
| Reproductor | `https://songqueue.onrender.com/player.html?venue=1` |
| Salud | `https://songqueue.onrender.com/health` |

### URLs (vía nginx en :80)

- Cliente: `http://localhost:80/?venue=1` (o `/join/<qr_token>`)
- Admin: `http://localhost:80/admin.html`
- Reproductor: `http://localhost:80/player.html?venue=1`
- Salud: `http://localhost:8000/health` · Ready (con DB): `http://localhost:8000/ready`

## Seguridad

- Sin secretos en el repo: `SECRET_KEY`/`DB_PASSWORD` obligatorios, placeholders bloqueados, `CORS` explícito por env.
- Rate limiting en login, altas a cola, búsqueda y registro de nombres (slowapi, clave por IP real tras proxy).
- JWT con `role` (`venue`/`superadmin`); tokens viejos sin rol siguen válidos como venue.
- `auto-skip` limitado (20/min) + guard anti-duplicado; alta a cola atómica por local (lock + `SELECT COUNT`).
- Si expones una API key (como pasó con la de YouTube en el historial): revócala en el proveedor, no basta con borrarla del código.

## Decisiones técnicas (ADRs en `docs/adr/`)

- [001](docs/adr/001-lista-de-espera-estado-waiting.md): lista de espera como estado `WAITING`, no tabla separada.
- [002](docs/adr/002-super-admin-en-db.md): super admin en base de datos, no en entorno.
- [003](docs/adr/003-cloudflare-tunnel.md): demo pública con Tunnel en vez de reescribir a serverless.

## Licencia

MIT - Proyecto de portafolio.
