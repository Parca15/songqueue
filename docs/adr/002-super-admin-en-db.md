# ADR 002: Super admin en base de datos

Fecha: 2026-09-08 · Estado: aceptado

## Contexto

Se necesitaba un super admin con acceso a todas las cuentas (crear, borrar,
renombrar, reset de claves, gestionar cualquier local).

## Opciones

1. **Credenciales en variables de entorno** (sin migración).
2. **Tabla `users` con rol `superadmin`** (elegido).

## Decisión

Tabla `users` + JWT con claim `role`.

- Permite rotar la clave, desactivar la cuenta y (a futuro) más roles sin
  redeploy. El bootstrap crea el super desde env solo si no existe ninguno.
- Tokens viejos sin `role` siguen válidos como venue: despliegue sin
  invalidar sesiones.
- `require_venue_access(principal, venue_id)` centraliza el aislamiento por
  tenant en ~17 endpoints en vez de comparaciones ad-hoc.

## Consecuencias

- `POST /venues` pasó de público a solo-super (breaking change controlado:
  tests actualizados).
- El login prueba `users` antes que `venues`; usernames de ambos espacios
  no deben colisionar en la práctica (se documenta).
