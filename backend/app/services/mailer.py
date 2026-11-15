"""Outgoing e-mail for invitations and password resets.

Backends:
  smtp    — real delivery (required in production).
  console — development only: prints the message to the API process's stdout.
  file    — development only: writes .eml files to var/outbox/.
Production refuses non-SMTP backends (see config._production_guards), so tokens never end up in
production logs.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid

from app.config import BACKEND_DIR, get_settings

log = logging.getLogger("baysahne.mail")


def send_mail(to: str, subject: str, text: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"] = s.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain="baysahne.local")
    msg.set_content(text)

    if s.email_backend == "smtp":
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            if s.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(msg)
        log.info("mail sent to=%s subject=%s", to, subject)
        return

    if not s.is_dev:
        raise RuntimeError("Non-SMTP e-mail backend is only allowed in development/test")

    if s.email_backend == "file":
        outbox = BACKEND_DIR / "var" / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        (outbox / f"{msg['Message-ID'].strip('<>').split('@')[0]}.eml").write_bytes(bytes(msg))
        log.info("mail written to outbox to=%s subject=%s", to, subject)
        return

    print(f"\n----- [DEV MAIL] to={to} subject={subject} -----\n{text}\n----- [END DEV MAIL] -----\n", flush=True)


def invitation_mail(to: str, full_name: str, inviter: str | None, link: str, hours: int) -> None:
    by = f"{inviter} sizi" if inviter else "Sizi"
    send_mail(
        to,
        "Bay Sahne yönetim paneline davet",
        f"Merhaba {full_name},\n\n{by} Bay Sahne yönetim paneline davet etti.\n"
        f"Hesabınızı oluşturmak ve parolanızı belirlemek için aşağıdaki bağlantıyı kullanın:\n\n{link}\n\n"
        f"Bu bağlantı {hours} saat geçerlidir ve yalnızca bir kez kullanılabilir.\n"
        "Bu daveti beklemiyorsanız e-postayı yok sayabilirsiniz.\n\nBay Sahne",
    )


def password_reset_mail(to: str, full_name: str, link: str, minutes: int) -> None:
    send_mail(
        to,
        "Bay Sahne yönetim paneli — parola sıfırlama",
        f"Merhaba {full_name},\n\nParolanızı sıfırlamak için aşağıdaki bağlantıyı kullanın:\n\n{link}\n\n"
        f"Bağlantı {minutes} dakika geçerlidir ve yalnızca bir kez kullanılabilir.\n"
        "Bu isteği siz yapmadıysanız e-postayı yok sayın; parolanız değişmeyecektir.\n\nBay Sahne",
    )
