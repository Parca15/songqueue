# SongQueue

Sistema de cola de canciones multi-local con integracion de YouTube, generacion de QR por establecimiento, control de dispositivos y gestion en tiempo real via WebSockets.

## Caracteristicas

- **Multi-local**: Cada local tiene su propia cola, configuracion y QR unico
- **QR por local**: Los clientes escanean un QR y acceden directamente a la cola del local
- **YouTube Integration**: Busqueda y reproduccion de videos de YouTube
- **Control por dispositivo**: Limite de canciones por dispositivo usando fingerprint
- **Panel Admin**: Gestion completa de la cola con autenticacion JWT
- **Tiempo real**: WebSockets para sincronizacion instantanea
- **Dockerizado**: MySQL + App en contenedores
- **Testeado**: Suite completa con pytest

## Arquitectura

```
songqueue/
├── docker-compose.yml      # MySQL + App
├── Dockerfile              # Imagen de la app
├── src/
│   ├── main.py             # Entry point FastAPI
│   ├── config.py           # Pydantic Settings
│   ├── database.py         # SQLAlchemy async
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic schemas
│   ├── routers/            # API + WebSockets
│   ├── services/           # Logica de negocio
│   └── utils/              # QR, JWT, Auth
├── alembic/                # Migraciones
├── tests/                  # Tests pytest
├── seed_data.py            # Datos de prueba
└── frontend/               # HTML/JS vanilla
    ├── index.html          # Cliente (QR)
    ├── admin.html          # Panel admin
    └── player.html         # Reproductor TV
```

## Quick Start

### Local (desarrollo)
```bash
# 1. Variables de entorno
cp .env.example .env

# 2. MySQL en Docker
docker-compose up -d db

# 3. Entorno virtual
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Migraciones y seed
alembic upgrade head
python seed_data.py

# 5. Tests
pytest

# 6. Servidor
uvicorn src.main:app --reload
```

### Docker completo
```bash
docker-compose up --build
```

### URLs
- API Docs: http://localhost:8000/docs
- Cliente: http://localhost:8000/static/index.html?venue=1
- Admin: http://localhost:8000/static/admin.html?venue=1
- Reproductor: http://localhost:8000/static/player.html?venue=1

## Plan de Etapas

| Etapa | Descripcion | Estado |
|-------|-------------|--------|
| 1 | Configuracion del proyecto + MySQL Docker | Completado |
| 2 | Migraciones + Seed data + Tests | Completado |
| 3 | API completa + Auth JWT + WebSockets + Broadcast | Completado |
| 4 | Frontend (HTML/JS vanilla) | Completado |
| 5 | Dockerizacion completa | Completado |

## Licencia

MIT - Proyecto de portafolio.
