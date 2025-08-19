"""
Lightweight SMTP email helper for integration notifications.

Environment variables:
- SMTP_HOST: SMTP server hostname (required)
- SMTP_PORT: SMTP server port (default: 587)
- SMTP_USERNAME: SMTP username (optional)
- SMTP_PASSWORD: SMTP password (optional)
- SMTP_USE_TLS: "true" to use STARTTLS (default: true when not using SSL)
- SMTP_USE_SSL: "true" to use implicit SSL (default: false)
- NOTIFY_EMAIL_FROM: From email address (default: SMTP_USERNAME or "noreply@localhost")
- NOTIFY_EMAIL_TO: Comma/semicolon-separated recipient list (fallback if `to` not provided)
- NOTIFY_EMAIL_CC: Optional CC list
- NOTIFY_EMAIL_BCC: Optional BCC list
- INTEGRATION_NAME: Optional integration name to include in subjects
"""

from __future__ import annotations

import os
import smtplib
import socket
import traceback
from typing import Iterable, List, Optional, Sequence

try:
    # Safe to import; our module is hpd.email, not top-level email
    from email.message import EmailMessage
except Exception:  # pragma: no cover
    EmailMessage = None  # type: ignore


def _get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _split_recipients(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _default_from_address() -> str:
    return os.getenv("NOTIFY_EMAIL_FROM") or os.getenv("SMTP_USERNAME") or "noreply@localhost"


def _mask_secret(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}{'*' * (len(secret) - 4)}{secret[-2:]}"


class SmtpConfig:
    def __init__(self) -> None:
        self.host: str = os.getenv("SMTP_HOST", "").strip()
        self.port: int = int(os.getenv("SMTP_PORT", "587"))
        self.username: str = os.getenv("SMTP_USERNAME", "").strip()
        self.password: str = os.getenv("SMTP_PASSWORD", "").strip()
        self.use_ssl: bool = _get_bool_env("SMTP_USE_SSL", False)
        self.use_tls: bool = _get_bool_env("SMTP_USE_TLS", True if not self.use_ssl else False)
        self.mail_from: str = _default_from_address()
        self.default_to: List[str] = _split_recipients(os.getenv("NOTIFY_EMAIL_TO"))
        self.default_cc: List[str] = _split_recipients(os.getenv("NOTIFY_EMAIL_CC"))
        self.default_bcc: List[str] = _split_recipients(os.getenv("NOTIFY_EMAIL_BCC"))

    def validate(self) -> None:
        if not self.host:
            raise RuntimeError("SMTP_HOST is not set")
        if self.port <= 0:
            raise RuntimeError("SMTP_PORT must be positive")
        if not self.mail_from:
            raise RuntimeError("NOTIFY_EMAIL_FROM or SMTP_USERNAME must be set")


def _build_message(
    subject: str,
    body_text: str,
    *,
    from_addr: Optional[str] = None,
    to: Optional[Sequence[str]] = None,
    cc: Optional[Sequence[str]] = None,
    bcc: Optional[Sequence[str]] = None,
    reply_to: Optional[str] = None,
    html_body: Optional[str] = None,
) -> EmailMessage:
    if EmailMessage is None:  # pragma: no cover
        raise RuntimeError("email.message.EmailMessage is unavailable")

    msg = EmailMessage()
    msg["Subject"] = subject
    if from_addr:
        msg["From"] = from_addr
    if to:
        msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if reply_to:
        msg["Reply-To"] = reply_to

    if html_body:
        msg.set_content(body_text)
        msg.add_alternative(html_body, subtype="html")
    else:
        msg.set_content(body_text)

    # bcc not placed in headers by design
    return msg


def send_email(
    subject: str,
    body_text: str,
    *,
    to: Optional[Sequence[str]] = None,
    cc: Optional[Sequence[str]] = None,
    bcc: Optional[Sequence[str]] = None,
    reply_to: Optional[str] = None,
    html_body: Optional[str] = None,
) -> dict:
    """
    Send an email using SMTP settings from environment variables.
    Returns a summary dict. Raises on configuration or transport errors.
    """
    print(f"[Email] Sending email: {subject}")

    config = SmtpConfig()
    config.validate()

    # Debug credentials (masked by default; enable full dump via SMTP_DEBUG_SHOW_PASSWORD=true)
    try:
        debug_show = _get_bool_env("SMTP_DEBUG_SHOW_PASSWORD", False)
        print(f"[Email][Debug] SMTP_HOST={config.host!r} PORT={config.port} SSL={config.use_ssl} TLS={config.use_tls}")
        print(f"[Email][Debug] SMTP_USERNAME={config.username!r}")
        if debug_show:
            print(f"[Email][Debug] SMTP_PASSWORD={config.password!r}")
        else:
            print(f"[Email][Debug] SMTP_PASSWORD(masked)={_mask_secret(config.password)} length={len(config.password)}")
        print(f"[Email][Debug] FROM={config.mail_from!r}")
    except Exception:
        pass

    recipients_to = list(to) if to else list(config.default_to)
    recipients_cc = list(cc) if cc else list(config.default_cc)
    recipients_bcc = list(bcc) if bcc else list(config.default_bcc)

    if not recipients_to and not recipients_cc and not recipients_bcc:
        raise RuntimeError("No recipients specified (NOTIFY_EMAIL_TO/CC/BCC are empty)")

    msg = _build_message(
        subject=subject,
        body_text=body_text,
        from_addr=config.mail_from,
        to=recipients_to,
        cc=recipients_cc,
        bcc=recipients_bcc,
        reply_to=reply_to,
        html_body=html_body,
    )

    all_rcpt = list(recipients_to) + list(recipients_cc) + list(recipients_bcc)

    if config.use_ssl:
        server_factory = lambda: smtplib.SMTP_SSL(config.host, config.port, timeout=30)
    else:
        server_factory = lambda: smtplib.SMTP(config.host, config.port, timeout=30)

    try:
        with server_factory() as server:
            server.ehlo()
            if not config.use_ssl and config.use_tls:
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPException:
                    # Proceed without TLS if server doesn't support it
                    pass

            if config.username:
                server.login(config.username, config.password)

            server.send_message(msg, from_addr=config.mail_from, to_addrs=all_rcpt)
    except (smtplib.SMTPException, OSError, socket.error) as exc:
        raise RuntimeError(f"Failed to send email: {exc}") from exc

    return {
        "from": config.mail_from,
        "to": recipients_to,
        "cc": recipients_cc,
        "bcc": recipients_bcc,
        "subject": subject,
        "sent": True,
    }


def notify_integration_started(total_count: int, *, integration_name: Optional[str] = None) -> dict:
    name = integration_name or os.getenv("INTEGRATION_NAME", "Integration")
    subject = f"{name} started: {total_count} products"
    body = (
        f"{name} has started.\n\n"
        f"Total products to process: {total_count}\n"
    )
    return send_email(subject=subject, body_text=body)


def notify_error(
    title: str,
    error: Exception | str,
    *,
    integration_name: Optional[str] = None,
    details: Optional[str] = None,
) -> dict:
    name = integration_name or os.getenv("INTEGRATION_NAME", "Integration")
    subject = f"{name} error: {title}"
    if isinstance(error, Exception):
        error_lines = [f"{type(error).__name__}: {error}"]
        tb = traceback.format_exc()
        if tb and tb != "NoneType: None\n":
            error_lines.append("\nTraceback:\n" + tb)
        error_text = "\n".join(error_lines)
    else:
        error_text = str(error)

    if details:
        error_text = f"{error_text}\n\nDetails:\n{details}"

    body = (
        f"An error occurred in {name}.\n\n"
        f"Title: {title}\n\n"
        f"{error_text}\n"
    )
    return send_email(subject=subject, body_text=body)


