# SongQueue — Sistema de Cola de Canciones Multi-Local

Sistema en tiempo real donde los clientes escanean un QR, registran su nombre y piden canciones de YouTube. El admin aprueba desde una lista de espera y el reproductor las suena en un TV. Incluye super admin con acceso total a las cuentas.

## Stack Tecnológico

### Backend
- **Python 3.12** con **FastAPI** (async/await)
- **SQLAlchemy** async con **aiomysql** (MySQL)
- **Alembic** para migraciones de base de datos
- **WebSockets** para comunicación en tiempo real (broadcast por local y rol)
- **JWT** con roles (`superadmin` / `venue`) y autenticación por tokens
- **Pydantic** para validación de datos y configuración (fail-fast)
- **Rate limiting** con SlowAPI (protección contra abuso)
- **YouTube Data API** + **yt-dlp** para búsqueda de canciones
- Generación de **QR codes** con `qrcode` + PIL

### Frontend
- **HTML/CSS/JS vanilla** (sin frameworks)
- Sistema de diseño propio inspirado en Apple (light/dark mode, materiales translúcidos)
- **Motion.js** para animaciones y transiciones
- 4 vistas: Cliente, Admin, Reproductor TV, Unirse por QR

### Infraestructura y DevOps
- **Docker** multi-stage build (imagen no-root, ~150MB)
- **Docker Compose** (MySQL + App + nginx + Cloudflare Tunnel)
- **nginx** como reverse proxy (estáticos + API + WebSockets)
- **Render.com** (deploy en la nube, Infrastructure as Code con `render.yaml`)
- **TiDB Cloud** Serverless (MySQL compatible, gratis)
- **GitHub Actions** CI/CD (lint, tests, coverage)
- **Cloudflare Tunnel** para demos públicas sin abrir puertos

### Calidad de Código
- **black** + **isort** + **flake8** (formato y linting)
- **pytest** con 38+ tests y cobertura mínima del 50%
- **Pydantic Settings** con validación de secretos (placeholders bloqueados)
- Arquitectura documentada con **ADR** (Architecture Decision Records)

## Arquitectura

```
Clientes (QR) ──→ nginx ──→ FastAPI (API + WebSocket) ──→ MySQL
                   │                                      ↑
Admin ─────────────┤                                      │
                   │                                      │
Reproductor TV ────┘                                      │
                                                          │
                    TiDB Cloud Serverless ◄───────────────┘
```

## Características Clave

- **Multi-local**: cada local tiene su cola, configuración y QR único
- **Lista de espera con aprobación**: el admin aprueba como prioridad o al final
- **Nombres de cliente**: registro único por local, visible en el panel
- **Super admin**: CRUD de cuentas, renombres, reset de claves
- **Tiempo real**: WebSockets con broadcast por local y rol
- **Seguridad**: JWT, rate limiting, CORS explícito, secretos fail-fast
- **Calidad**: tests automatizados, CI/CD, migraciones versionadas

## Habilidades Demostradas

| Categoría | Tecnologías |
|-----------|-------------|
| Backend | Python, FastAPI, SQLAlchemy, WebSockets, JWT, REST API |
| Frontend | HTML5, CSS3, JavaScript vanilla, Design Systems |
| Bases de datos | MySQL, SQL, Migraciones (Alembic), ORM |
| Infraestructura | Docker, Docker Compose, nginx, Cloudflare |
| Cloud | Render.com, TiDB Cloud, GitHub Actions |
| DevOps | CI/CD, Multi-stage builds, Infrastructure as Code |
| Seguridad | Autenticación JWT, Rate limiting, CORS, HTTPS/SSL |
| Calidad | Testing (pytest), Linting, Code Coverage, ADR |

## Enlace

- **Repositorio**: https://github.com/Parca15/songqueue
- **Demo**: https://songqueue.onrender.com
