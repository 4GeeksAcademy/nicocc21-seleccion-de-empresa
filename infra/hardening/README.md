# Endurecimiento del Servidor — Brasaland

## Archivos en este directorio

| Archivo | Propósito |
|---------|-----------|
| `init-hardening.sh` | Script de endurecimiento inicial del servidor (ejecutar como root) |
| `docker-compose.yml` (raíz) | Modificado para limitar puertos a localhost |
| `env/mcp` | Modificado: `MCP_AUTH_DISABLED=0` por defecto |
| `env/mcp.example` | Actualizado con comentarios de seguridad |

## Resumen de cambios aplicados

### Puertos
| Puerto | Antes | Después |
|--------|-------|---------|
| 5432 (PostgreSQL) | `0.0.0.0:5432` | `127.0.0.1:5432` |
| 8000 (WSGI) | `0.0.0.0:8000` | `127.0.0.1:8000` |
| 8001 (FastAPI) | `0.0.0.0:8001` | `127.0.0.1:8001` |
| 3000 (Website) | `0.0.0.0:3000` | `127.0.0.1:3000` |
| 3001 (Backoffice) | `0.0.0.0:3001` | `127.0.0.1:3001` |
| 6333 (Qdrant API) | `0.0.0.0:6333` | `127.0.0.1:6333` |
| 6334 (Qdrant Dashboard) | `0.0.0.0:6334` | `127.0.0.1:6334` |

### CORS
| Aspecto | Antes | Después |
|---------|-------|---------|
| `allow_origins` | `["*"]` | `["http://localhost:3000", "http://localhost:3001", ...]` |

### MCP Server
| Aspecto | Antes | Después |
|---------|-------|---------|
| `MCP_AUTH_DISABLED` | `1` (sin auth) | `0` (auth requerida) |

## Cómo aplicar el hardening

```bash
# 1. Hacer ejecutable y ejecutar como root
sudo chmod +x infra/hardening/init-hardening.sh
sudo bash infra/hardening/init-hardening.sh

# 2. Configurar proxy inverso (Nginx/Caddy) para HTTPS
# Ejemplo con Caddy:
#     brasaland.com {
#         reverse_proxy localhost:3000
#     }
#     api.brasaland.com {
#         reverse_proxy localhost:8001
#     }

# 3. Copiar clave SSH al nuevo usuario
ssh-copy-id brasaland@<servidor>
```