# 🎵 SongQueue

Sistema de cola de canciones multi-local con integración de YouTube, generación de QR por establecimiento, control de dispositivos y gestión en tiempo real vía WebSockets.

## ✨ Características

- 🏪 **Multi-local**: Cada local tiene su propia cola, configuración y QR único
- 📱 **QR por local**: Los clientes escanean un QR y acceden directamente a la cola del local
- 🎵 **YouTube Integration**: Búsqueda y reproducción de videos de YouTube
- 🔒 **Control por dispositivo**: Límite de canciones por dispositivo usando fingerprint
- 👤 **Panel Admin**: Gestión completa de la cola (reordenar, eliminar, pausar)
- ⚡ **Tiempo real**: WebSockets para sincronización instantánea entre clientes y reproductor
- 🐳 **Dockerizado**: MySQL en contenedor, app lista para containerizar

## 🏗️ Arquitectura

```
songqueue/
├── docker-compose.yml      # MySQL + (app en Etapa 5)
├── src/
│   ├── main.py             # Entry point FastAPI
│   ├── config.py           # Configuración centralizada (Pydantic Settings)
│   ├── database.py         # Conexión SQLAlchemy async
│   ├── models/             # Modelos SQLAlchemy
│   ├── schemas/            # Pydantic schemas
│   ├── routers/            # Endpoints API + WebSockets
│   ├── services/           # Lógica de negocio
│   └── utils/              # Utilidades (QR, seguridad)
├── alembic/                # Migraciones de base de datos
├── tests/                  # Tests con pytest
└── frontend/               # Frontend (Etapa 4)
```

## 🚀 Quick Start

### 1. Clonar y entrar
```bash
git clone <repo>
cd songqueue
```

### 2. Variables de entorno
```bash
cp .env.example .env
# Editar .env con tus valores
```

### 3. Levantar MySQL (Docker)
```bash
docker-compose up -d db
```

### 4. Crear entorno virtual e instalar dependencias
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 5. Ejecutar migraciones
```bash
alembic upgrade head
```

### 6. Iniciar servidor
```bash
uvicorn src.main:app --reload
```

## 📋 Plan de Etapas

| Etapa | Descripción | Estado |
|-------|-------------|--------|
| 1 | Configuración del proyecto + MySQL Docker | 🚧 En progreso |
| 2 | Modelos de datos + Schemas + Migraciones | ⏳ Pendiente |
| 3 | API REST + WebSockets + Servicios | ⏳ Pendiente |
| 4 | Frontend (HTML/JS vanilla → React) | ⏳ Pendiente |
| 5 | Dockerización completa + Deploy | ⏳ Pendiente |

## 📝 Licencia

MIT — Proyecto de portafolio.
