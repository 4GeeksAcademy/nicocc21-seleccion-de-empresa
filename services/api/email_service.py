"""Servicio de email transaccional vía Resend API.

Requiere la variable de entorno RESEND_API_KEY.
Usa httpx para llamar a la API de Resend sin dependencias adicionales pesadas.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
FROM_EMAIL = "onboarding@resend.dev"  # Remitente por defecto en desarrollo


@dataclass
class EmailResult:
    success: bool
    message: str
    email_id: str | None = None


def _get_api_key() -> str | None:
    return os.getenv("RESEND_API_KEY")


def send_reset_email(to_email: str, reset_link: str) -> EmailResult:
    """Envía un email de restablecimiento de contraseña.

    Args:
        to_email: Dirección de correo del destinatario.
        reset_link: Enlace completo de restablecimiento (con token).

    Returns:
        EmailResult indicando éxito o fallo.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.error("RESEND_API_KEY no está configurada")
        return EmailResult(success=False, message="Servicio de email no configurado")

    html_body = _build_reset_email_html(reset_link)
    text_body = (
        f"Has solicitado restablecer tu contraseña en Brasaland.\n\n"
        f"Haz clic en el siguiente enlace para restablecerla:\n{reset_link}\n\n"
        f"Si no solicitaste este cambio, ignora este mensaje.\n"
        f"El enlace expira en 15 minutos."
    )

    payload = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": "Brasaland — Restablece tu contraseña",
        "html": html_body,
        "text": text_body,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                RESEND_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.is_success:
            data = response.json()
            email_id = data.get("id")
            logger.info("Email enviado a %s: id=%s", to_email, email_id)
            return EmailResult(
                success=True,
                message="Email enviado correctamente",
                email_id=email_id,
            )
        else:
            logger.error(
                "Error al enviar email a %s: status=%s body=%s",
                to_email,
                response.status_code,
                response.text,
            )
            return EmailResult(
                success=False,
                message=f"Error del servicio de email: {response.status_code}",
            )
    except httpx.RequestError as exc:
        logger.error("Error de conexión con Resend: %s", exc)
        return EmailResult(
            success=False,
            message="No se pudo conectar con el servicio de email",
        )


def _build_reset_email_html(reset_link: str) -> str:
    """Construye un HTML legible en móvil para el email de restablecimiento."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f5f5f0;font-family:Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f0;padding:20px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width:480px;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#b45309,#d97706);padding:24px 32px;text-align:center;">
              <h1 style="margin:0;color:#ffffff;font-size:24px;">Brasaland</h1>
              <p style="margin:4px 0 0;color:#fde68a;font-size:14px;">Restablece tu contraseña</p>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;color:#44403c;font-size:15px;line-height:1.5;">
                Has solicitado restablecer tu contraseña. Haz clic en el botón para continuar:
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:24px 0;">
                <tr>
                  <td style="border-radius:8px;background:linear-gradient(135deg,#b45309,#d97706);padding:12px 32px;text-align:center;">
                    <a href="{reset_link}" target="_blank" style="color:#ffffff;font-size:16px;font-weight:bold;text-decoration:none;display:inline-block;">
                      Restablecer contraseña
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:16px 0 0;color:#78716c;font-size:13px;line-height:1.5;">
                Si no puedes hacer clic, copia este enlace en tu navegador:<br>
                <span style="color:#b45309;word-break:break-all;">{reset_link}</span>
              </p>
              <hr style="border:none;border-top:1px solid #e7e5e4;margin:24px 0;">
              <p style="margin:0;color:#a8a29e;font-size:12px;line-height:1.5;">
                Si no solicitaste este cambio, ignora este mensaje.<br>
                El enlace expira en 15 minutos.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""