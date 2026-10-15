# Entorno de variables — Brasaland

Este directorio contiene archivos `.example` con todas las variables de entorno
necesarias para cada servicio del monorepo.

## Uso

1. Copia el archivo `.example` correspondiente a tu servicio como `.env` en la
   ubicación indicada.
2. Completa los valores — los marcadores vacíos (`=`) deben reemplazarse con
   valores reales (claves, URLs, etc.).
3. **Nunca subas archivos `.env` al repositorio** — ya están en `.gitignore`.

## Servicios

| Archivo | Destino típico |
|---|---|
| `backend.example` | `services/brasaland_api/.env` o raíz del proyecto |
| `backoffice.example` | `uis/backoffice/.env` |
| `website.example` | `uis/website/.env` |

## Notas

- Los valores con `=` vacío son obligatorios y deben rellenarse.
- Los valores con `=algo` tienen un valor por defecto seguro para desarrollo local.
- `DATABASE_URL` requiere una base de datos PostgreSQL real (Supabase, local, etc.).
- `RESEND_API_KEY` requiere una API key de Resend para el envío de correos.