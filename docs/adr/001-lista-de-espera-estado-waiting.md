# ADR 001: Lista de espera como estado WAITING

Fecha: 2026-09-07 · Estado: aceptado

## Contexto

Los clientes pedían canciones que entraban directo a la cola. Se necesitaba
una lista de espera donde el admin aprueba (prioridad o última) o rechaza.

## Opciones

1. **Nueva tabla `waiting_items`** con su propio ciclo de vida.
2. **Nuevo estado `WAITING` en `queue_items`** (elegido).

## Decisión

Estado `WAITING` en la tabla existente.

- La aprobación es solo un cambio de estado + posición; el rechazo reutiliza
  el soft-delete (`REMOVED`). Cero tablas y endpoints duplicados.
- La cola y el reproductor no cambian: filtran `PENDING/PLAYING` como siempre.
- Los límites (por dispositivo, duplicados, tamaño) incluyen `WAITING` con un
  cambio de una línea en cada filtro.
- Los items en espera llevan `position=0` (sin sentido hasta aprobarse),
  evitando colisiones con `move_to_position`.

## Consecuencias

- La migración del ENUM en MySQL requiere `ALTER TABLE` explícito (ver 004).
- A futuro, si la espera necesitara campos propios (motivo de rechazo,
  expiración), se migraría a tabla separada.
