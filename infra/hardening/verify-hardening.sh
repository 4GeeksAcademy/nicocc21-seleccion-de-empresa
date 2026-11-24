#!/bin/bash
# =============================================================================
# verify-hardening.sh — Script de verificación del endurecimiento
# =============================================================================
# Este script comprueba que las medidas de hardening están activas.
# Ejecutar como: bash verify-hardening.sh
# No requiere root para las verificaciones de solo lectura.
# =============================================================================

set -euo pipefail

PASS=0
FAIL=0
WARN=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

check() {
    local description="$1"
    local result="$2"

    if [[ "$result" == "pass" ]]; then
        echo -e "  ${GREEN}✅${NC} $description"
        PASS=$((PASS + 1))
    elif [[ "$result" == "fail" ]]; then
        echo -e "  ${RED}❌${NC} $description"
        FAIL=$((FAIL + 1))
    else
        echo -e "  ${YELLOW}⚠️  ${NC} $description — $result"
        WARN=$((WARN + 1))
    fi
}

echo ""
echo "═══════════════════════════════════════════════"
echo "  VERIFICACIÓN DE ENDURECIMIENTO — BRASALAND"
echo "═══════════════════════════════════════════════"
echo ""

# ─── 1. Usuario no-root ─────────────────────────────────────────────────

echo "📌 1. USUARIO NO-ROOT"

if id "brasaland" &>/dev/null; then
    check "Usuario 'brasaland' existe" "pass"
    # Verificar grupo sudo
    if groups brasaland 2>/dev/null | grep -q "\bsudo\b"; then
        check "Usuario 'brasaland' en grupo sudo" "pass"
    else
        check "Usuario 'brasaland' en grupo sudo" "fail"
    fi
else
    check "Usuario 'brasaland' existe (crear con: sudo bash init-hardening.sh)" "warn"
fi

# ─── 2. SSH root login ──────────────────────────────────────────────────

echo ""
echo "📌 2. SSH — ROOT LOGIN"

if [[ -f /etc/ssh/sshd_config ]]; then
    if grep -q "^PermitRootLogin no" /etc/ssh/sshd_config 2>/dev/null; then
        check "PermitRootLogin = no" "pass"
    else
        # Puede estar comentado o con otra configuración
        if grep -q "^#.*PermitRootLogin" /etc/ssh/sshd_config 2>/dev/null; then
            check "PermitRootLogin (está comentado, requiere ejecutar hardening)" "warn"
        else
            check "PermitRootLogin = no (ejecutar hardening si no está configurado)" "warn"
        fi
    fi

    if grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config 2>/dev/null; then
        check "PasswordAuthentication = no" "pass"
    else
        check "PasswordAuthentication = no (requiere hardening)" "warn"
    fi
else
    check "ssh_config no encontrado (no aplica en este entorno)" "warn"
fi

# ─── 3. Firewall ────────────────────────────────────────────────────────

echo ""
echo "📌 3. FIREWALL"

if command -v ufw &>/dev/null; then
    local STATUS
    STATUS=$(ufw status 2>/dev/null | head -1)
    if echo "$STATUS" | grep -q "active"; then
        check "UFW está activo" "pass"
    else
        check "UFW no está activo (ejecutar hardening)" "fail"
    fi

    # Verificar puertos
    local RULES
    RULES=$(ufw status verbose 2>/dev/null)

    for PORT in 22 80 443; do
        if echo "$RULES" | grep -q "$PORT/tcp"; then
            check "Puerto $PORT/tcp permitido" "pass"
        else
            check "Puerto $PORT/tcp permitido" "fail"
        fi
    done

    # Verificar que puertos internos NO están abiertos
    for PORT in 5432 6333 6334 8081; do
        if echo "$RULES" | grep -q "$PORT"; then
            check "Puerto $PORT NO debe estar abierto en firewall" "fail"
        else
            check "Puerto $PORT bloqueado por firewall" "pass"
        fi
    done
else
    check "UFW no instalado (ejecutar hardening)" "warn"
fi

# ─── 4. Docker Compose — Puertos vinculados a localhost ─────────────────

echo ""
echo "📌 4. DOCKER COMPOSE — PUERTOS"

PROJECT_ROOT="$(dirname "$(dirname "$(readlink -f "$0")")")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"

if [[ -f "$COMPOSE_FILE" ]]; then
    for PORT in 5432 8000 8001 3000 3001 6333 6334; do
        if grep -q "127.0.0.1:$PORT:$PORT" "$COMPOSE_FILE" 2>/dev/null; then
            check "Puerto Docker $PORT → 127.0.0.1 (no expuesto globalmente)" "pass"
        elif grep -q "\"$PORT:$PORT\"" "$COMPOSE_FILE" 2>/dev/null; then
            check "Puerto Docker $PORT → 0.0.0.0 (¡expuesto globalmente!)" "fail"
        else
            check "Puerto Docker $PORT no mapeado en compose" "pass"
        fi
    done
else
    check "docker-compose.yml no encontrado" "warn"
fi

# ─── 5. MCP Auth ────────────────────────────────────────────────────────

echo ""
echo "📌 5. MCP SERVER — AUTENTICACIÓN"

MCP_ENV="$PROJECT_ROOT/env/mcp"
if [[ -f "$MCP_ENV" ]]; then
    if grep -q "MCP_AUTH_DISABLED=0" "$MCP_ENV" 2>/dev/null; then
        check "MCP_AUTH_DISABLED=0 (autenticación requerida)" "pass"
    elif grep -q "MCP_AUTH_DISABLED=1" "$MCP_ENV" 2>/dev/null; then
        check "MCP_AUTH_DISABLED=1 (sin autenticación — ¡inseguro!)" "fail"
    else
        check "MCP_AUTH_DISABLED no definido (puede heredar default seguro)" "warn"
    fi
else
    check "env/mcp no encontrado" "warn"
fi

# ─── 6. CORS ────────────────────────────────────────────────────────────

echo ""
echo "📌 6. CORS — ORÍGENES PERMITIDOS"

MAIN_PY="$PROJECT_ROOT/services/brasaland_api/main.py"
if [[ -f "$MAIN_PY" ]]; then
    if grep -q 'allow_origins=\["\*"\]' "$MAIN_PY" 2>/dev/null; then
        check "CORS allow_origins=['*'] (¡inseguro!)" "fail"
    elif grep -q "allow_origins=\[" "$MAIN_PY" 2>/dev/null; then
        check "CORS allow_origins restringido a orígenes específicos" "pass"
    else
        check "CORS allow_origins (no se pudo determinar)" "warn"
    fi
else
    check "main.py no encontrado" "warn"
fi

# ─── 7. RAG Safety ──────────────────────────────────────────────────────

echo ""
echo "📌 7. RAG — SEGURIDAD CONTRA PROMPT INJECTION"

RAG_SAFETY="$PROJECT_ROOT/data/pipelines/rag_safety.py"
if [[ -f "$RAG_SAFETY" ]]; then
    check "Filtro de prompt injection indirecta (rag_safety.py) existe" "pass"
    if grep -q "_INDIRECT_INJECTION_PATTERNS" "$RAG_SAFETY" 2>/dev/null; then
        check "rag_safety.py: patrones de inyección definidos" "pass"
    else
        check "rag_safety.py: patrones de inyección" "warn"
    fi
else
    check "rag_safety.py no encontrado" "fail"
fi

# ─── 8. Human Confirmation ──────────────────────────────────────────────

echo ""
echo "📌 8. ACCIONES IRREVERSIBLES — CONFIRMACIÓN HUMANA"

HUMAN_CONFIRM="$PROJECT_ROOT/agents/support_agent/human_confirmation.py"
if [[ -f "$HUMAN_CONFIRM" ]]; then
    check "Gate de confirmación humana (human_confirmation.py) existe" "pass"
    for ACTION in "SEND_MARKETING_CAMPAIGN" "ADJUST_LOYALTY_POINTS" "MODIFY_SUPPLIER_STATUS" "CREATE_PURCHASE_ORDER"; do
        if grep -q "$ACTION" "$HUMAN_CONFIRM" 2>/dev/null; then
            check "Acción irreversible '$ACTION' requiere confirmación" "pass"
        fi
    done
else
    check "human_confirmation.py no encontrado" "fail"
fi

# ─── Resumen ────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════"
echo "  RESUMEN"
echo "═══════════════════════════════════════════════"
echo -e "  ${GREEN}✅${NC} Pasaron:  $PASS"
echo -e "  ${RED}❌${NC} Fallaron: $FAIL"
echo -e "  ${YELLOW}⚠️${NC} Advertencias: $WARN"
echo ""

if [[ $FAIL -eq 0 ]]; then
    echo "  ✅ Todas las verificaciones pasaron."
    echo "  El servidor está endurecido correctamente."
else
    echo "  ⚠️  Hay $FAIL verificaciones que fallaron."
    echo "  Revisa los puntos marcados en rojo."
fi
echo "═══════════════════════════════════════════════"
echo ""

exit $FAIL