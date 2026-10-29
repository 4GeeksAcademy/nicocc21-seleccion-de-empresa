# Entorno de variables — Brasaland

Este directorio contiene archivos `.example` con todas las variables de entorno
necesarias para cada servicio del monorepo. Solo hay plantillas: **ningún valor
real (claves, contraseñas, URLs con credenciales) debe escribirse aquí.**

## Uso

1. Copia el archivo `.example` correspondiente a tu servicio como `.env` en la
   ubicación indicada.
2. Completa los valores — los marcadores vacíos (`=`) deben reemplazarse con
   valores reales (claves, URLs, etc.).
3. **Nunca subas archivos `.env` al repositorio** — ya están en `.gitignore`.

## Servicios

| Archivo | Destino |
|---|---|
| `backend.example` | `services/brasaland_api/.env` |
| `application.example` | `uis/application/.env` |
| `backoffice.example` | `uis/backoffice/.env` |
| `website.example` | `uis/website/.env` (sin variables por ahora) |

## Notas

- Los valores con `=` vacío son obligatorios y deben rellenarse.
- Los valores con `=algo` son valores por defecto para desarrollo local.
- `JWT_SECRET_KEY` se genera con `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `DATABASE_URL` requiere una base de datos PostgreSQL real (Supabase, local, etc.)
  con el formato `postgresql+psycopg2://USUARIO:CONTRASENA@HOST:PUERTO/BASE_DE_DATOS`.
- `RESEND_API_KEY` requiere una API key de Resend para el envío de correos.
- Las variables `NEXT_PUBLIC_*` se incluyen en el bundle del navegador: nunca
  pongas secretos en ellas.

## Si una credencial se expone

Si una contraseña o clave aparece en un commit, chat o log, rótala en el
proveedor (p. ej. *Reset database password* en Supabase) y actualiza solo tu
`.env` local.