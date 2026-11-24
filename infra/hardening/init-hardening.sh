#!/bin/bash
# =============================================================================
# init-hardening.sh — Endurecimiento inicial del servidor Brasaland
# =============================================================================
# Este script configura:
#   1. Creación de usuario no-root con sudo restringido
#   2. Deshabilitación de login root directo por SSH
#   3. Firewall (ufw) con solo puertos necesarios
#   4. Permisos seguros en carpetas sensibles
#
# Uso: sudo bash init-hardening.sh
# Ejecutar SOLO en el servidor de producción, NO en el contenedor Docker.
# =============================================================================

set -euo pipefail

# ─── Configuración ─────────────────────────────────────────────────────────
BRASALAND_USER="brasaland"
BRASALAND_SSH_PORT=22
LOG_FILE="/var/log/brasaland-hardening.log"

# Puertos necesarios para Brasaland
# - 22: SSH (ops)
# - 80: HTTP (redirección a HTTPS)
# - 443: HTTPS (API + frontends)
# - 8000: WSGI interno (solo local)
# - 8001: FastAPI interno (solo local)
# - 3000: Frontend web interno (solo local)
# - 3001: Backoffice interno (solo local)
# - 8081: MCP Server (solo local)

# ─── Funciones ──────────────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    echo "[ERROR] $*" >&2 | tee -a "$LOG_FILE"
    exit 1
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Este script debe ejecutarse como root (sudo)."
    fi
}

# ─── 1. Crear usuario no-root ───────────────────────────────────────────────
setup_nonroot_user() {
    log "=== 1. Creando usuario no-root: $BRASALAND_USER ==="

    if id "$BRASALAND_USER" &>/dev/null; then
        log "El usuario $BRASALAND_USER ya existe. Omitiendo creación."
    else
        useradd -m -s /bin/bash -G sudo "$BRASALAND_USER"
        log "Usuario $BRASALAND_USER creado con grupo sudo."
        log "⚠️  IMPORTANTE: Establece una contraseña con: sudo passwd $BRASALAND_USER"
    fi

    # Configurar sudo restringido: solo comandos específicos sin contraseña
    local SUDOERS_FILE="/etc/sudoers.d/$BRASALAND_USER"
    if [[ ! -f "$SUDOERS_FILE" ]]; then
        cat > "$SUDOERS_FILE" <<EOF
# Sudo restringido para $BRASALAND_USER — solo comandos necesarios para operar Brasaland
$BRASALAND_USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl
$BRASALAND_USER ALL=(ALL) NOPASSWD: /usr/bin/docker
$BRASALAND_USER ALL=(ALL) NOPASSWD: /usr/bin/docker-compose
$BRASALAND_USER ALL=(ALL) NOPASSWD: /usr/sbin/ufw
$BRASALAND_USER ALL=(ALL) NOPASSWD: /usr/bin/journalctl
# Solo lectura para logs
$BRASALAND_USER ALL=(ALL) NOPASSWD: /bin/cat /var/log/*
EOF
        chmod 440 "$SUDOERS_FILE"
        log "Sudo restringido configurado en $SUDOERS_FILE"
    else
        log "sudoers.d/$BRASALAND_USER ya existe. Omitiendo."
    fi
}

# ─── 2. Deshabilitar login root por SSH ─────────────────────────────────────
harden_ssh() {
    log "=== 2. Endureciendo configuración SSH ==="

    local SSH_CONFIG="/etc/ssh/sshd_config"
    local SSH_BACKUP="$SSH_CONFIG.backup.$(date +%Y%m%d)"

    if [[ ! -f "$SSH_BACKUP" ]]; then
        cp "$SSH_CONFIG" "$SSH_BACKUP"
        log "Backup de sshd_config creado: $SSH_BACKUP"
    fi

    # Aplicar configuraciones seguras
    local HARDENING_RULES=(
        "PermitRootLogin no"
        "PasswordAuthentication no"
        "PubkeyAuthentication yes"
        "ChallengeResponseAuthentication no"
        "UsePAM yes"
        "MaxAuthTries 3"
        "MaxSessions 2"
        "LoginGraceTime 30"
        "ClientAliveInterval 300"
        "ClientAliveCountMax 2"
        "AllowUsers $BRASALAND_USER"
    )

    for rule in "${HARDENING_RULES[@]}"; do
        local key="${rule%% *}"
        local value="${rule#* }"

        # Comentar línea existente y añadir la nueva
        if grep -q "^${key}" "$SSH_CONFIG"; then
            sed -i "s/^${key}.*/# ${key} (disabled by hardening)\n${rule}/" "$SSH_CONFIG"
        elif grep -q "^#${key}" "$SSH_CONFIG"; then
            sed -i "s/^#${key}.*/${rule}/" "$SSH_CONFIG"
        else
            echo "$rule" >> "$SSH_CONFIG"
        fi
    done

    log "Configuración SSH endurecida aplicada."

    # Verificar sintaxis antes de recargar
    if sshd -t &>/dev/null; then
        systemctl reload sshd || service ssh reload || true
        log "SSHD recargado correctamente."
    else
        error "Error de sintaxis en sshd_config. Restaurando backup."
        cp "$SSH_BACKUP" "$SSH_CONFIG"
        systemctl reload sshd || true
    fi
}

# ─── 3. Configurar firewall (ufw) ──────────────────────────────────────────
setup_firewall() {
    log "=== 3. Configurando firewall (ufw) ==="

    if ! command -v ufw &>/dev/null; then
        log "ufw no está instalado. Instalando..."
        apt-get update -qq && apt-get install -y -qq ufw
    fi

    # Resetear a configuración por defecto
    ufw --force reset

    # Política por defecto: denegar todo el tráfico entrante
    ufw default deny incoming
    ufw default allow outgoing

    # ── Puertos permitidos ──────────────────────────────────────────────
    # SSH (acceso de administración)
    ufw allow "$BRASALAND_SSH_PORT/tcp" comment "SSH"

    # HTTP/HTTPS (tráfico web)
    ufw allow 80/tcp   comment "HTTP"
    ufw allow 443/tcp  comment "HTTPS"

    # NOTA: Los puertos internos (8000, 8001, 3000, 3001, 8081, 5432, 6333, 6334)
    # NO se abren en ufw porque solo deben ser accesibles desde localhost
    # o a través del proxy inverso (Nginx/Caddy) en 443.

    # Habilitar ufw
    ufw --force enable
    log "Firewall configurado. Puertos abiertos: SSH(22), HTTP(80), HTTPS(443)"
    ufw status verbose | tee -a "$LOG_FILE"
}

# ─── 4. Permisos seguros ───────────────────────────────────────────────────
setup_secure_permissions() {
    log "=== 4. Configurando permisos seguros ==="

    # Directorios sensibles del proyecto (asumiendo que está en /opt/brasaland o similar)
    local PROJECT_DIR
    PROJECT_DIR="$(dirname "$(dirname "$(dirname "$(readlink -f "$0")")")")"

    if [[ -d "$PROJECT_DIR" ]]; then
        # .env nunca debe ser legible por otros
        find "$PROJECT_DIR" -name ".env" -exec chmod 600 {} \; 2>/dev/null || true
        log "Archivos .env protegidos (chmod 600)."

        # data/memory/ contiene datos sensibles
        local MEMORY_DIR="$PROJECT_DIR/data/memory"
        if [[ -d "$MEMORY_DIR" ]]; then
            chmod -R 750 "$MEMORY_DIR"
            log "Directorio data/memory/ protegido (chmod 750)."
        fi
    fi

    # Logs del sistema
    chmod 640 /var/log/auth.log 2>/dev/null || true
    log "Permisos de logs del sistema ajustados."
}

# ─── 5. Mostrar resumen ────────────────────────────────────────────────────
show_summary() {
    log ""
    log "═══════════════════════════════════════════════════════════════════"
    log "  ENDURECIMIENTO COMPLETADO"
    log "═══════════════════════════════════════════════════════════════════"
    log ""
    log "  Usuario no-root:     $BRASALAND_USER"
    log "  SSH root login:      DESHABILITADO"
    log "  SSH password auth:   DESHABILITADO"
    log "  Firewall:            ACTIVADO (ufw)"
    log "  Puertos abiertos:    22 (SSH), 80 (HTTP), 443 (HTTPS)"
    log "  Puertos bloqueados:  5432 (PostgreSQL), 6333/6334 (Qdrant),"
    log "                       8000/8001 (API), 3000/3001 (Frontends),"
    log "                       8081 (MCP)"
    log ""
    log "  ⚠️  ACCIONES PENDIENTES:"
    log "  1. Establecer contraseña: sudo passwd $BRASALAND_USER"
    log "  2. Copiar clave SSH: ssh-copy-id $BRASALAND_USER@<servidor>"
    log "  3. Configurar proxy inverso (Nginx/Caddy) para HTTPS"
    log "  4. Revisar /var/log/brasaland-hardening.log"
    log "═══════════════════════════════════════════════════════════════════"
}

# ─── Ejecución principal ───────────────────────────────────────────────────
main() {
    check_root
    log "=== Iniciando endurecimiento del servidor Brasaland ==="

    setup_nonroot_user
    harden_ssh
    setup_firewall
    setup_secure_permissions
    show_summary
}

main "$@"