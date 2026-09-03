import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_USER = "vahobovmuhammadali014@gmail.com"
SMTP_PASSWORD = "bqsexjkugjhikzgc"
SMTP_HOST = "smtp.gmail.com"

def send_email(to_email: str, subject: str, html_body: str) -> dict:
    user = (os.getenv("SMTP_USER") or "").strip() or SMTP_USER
    password = (os.getenv("SMTP_PASSWORD") or "").strip() or SMTP_PASSWORD
    host = (os.getenv("SMTP_HOST") or "").strip() or SMTP_HOST

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Telegram Guard <{user}>"
    msg["To"] = to_email

    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    errors = []

    # Attempt 1: Port 587 with STARTTLS
    try:
        logging.info(f"Attempting to send email via {host}:587 to {to_email}...")
        server = smtplib.SMTP(host, 587, timeout=12)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        logging.info(f"Email successfully sent to {to_email} via 587!")
        return {"success": True, "port": 587}
    except Exception as e587:
        logging.warning(f"SMTP 587 failed ({e587}), trying port 465 SSL...")
        errors.append(f"587: {e587}")

    # Attempt 2: Port 465 with SSL
    try:
        logging.info(f"Attempting to send email via {host}:465 to {to_email}...")
        server = smtplib.SMTP_SSL(host, 465, timeout=12)
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        logging.info(f"Email successfully sent to {to_email} via 465!")
        return {"success": True, "port": 465}
    except Exception as e465:
        logging.error(f"SMTP 465 failed ({e465})")
        errors.append(f"465: {e465}")

    return {"success": False, "error": "; ".join(errors)}

def send_verification_code_email(to_email: str, code: str, phone_number: str) -> dict:
    subject = "🛡️ Код подтверждения привязки Gmail — Telegram Guard"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; background-color: #0b0f19; color: #f0f4fd; padding: 30px; border-radius: 12px; max-width: 500px; margin: auto;">
        <h2 style="color: #00f2fe; text-align: center; margin-bottom: 20px;">🛡️ Telegram Guard Shield</h2>
        <p style="font-size: 15px; line-height: 1.6;">Здравствуйте!</p>
        <p style="font-size: 15px; line-height: 1.6;">Вы запросили привязку данного адреса Gmail к аккаунту защиты Telegram для номера <strong>{phone_number}</strong>.</p>
        <div style="background: #151c2c; border: 2px dashed #00f2fe; border-radius: 8px; text-align: center; padding: 18px; margin: 25px 0;">
            <span style="font-size: 13px; color: #8c9ba5; display: block; margin-bottom: 6px;">ВАШ 6-ЗНАЧНЫЙ КОД ПОДТВЕРЖДЕНИЯ:</span>
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #00f2fe;">{code}</span>
        </div>
        <p style="font-size: 13px; color: #8c9ba5; line-height: 1.5;">Срок действия кода: 10 минут. Если вы не запрашивали привязку, просто проигнорируйте это письмо.</p>
        <hr style="border: none; border-top: 1px solid #27344d; margin: 25px 0;">
        <p style="font-size: 12px; color: #5a6e85; text-align: center;">Система комплексной защиты Telegram Guard Shield</p>
    </div>
    """
    return send_email(to_email, subject, html_body)

def send_linked_success_email(to_email: str, phone_number: str) -> dict:
    subject = "✅ Резервный Email успешно привязан — Telegram Guard"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; background-color: #0b0f19; color: #f0f4fd; padding: 30px; border-radius: 12px; max-width: 500px; margin: auto;">
        <h2 style="color: #00e676; text-align: center; margin-bottom: 20px;">✅ Привязка завершена!</h2>
        <p style="font-size: 15px; line-height: 1.6;">Ваш адрес <strong>{to_email}</strong> успешно привязан к системе защиты Telegram Guard для номера <strong>{phone_number}</strong>.</p>
        <p style="font-size: 14px; color: #8c9ba5; line-height: 1.6;">Теперь вы можете использовать этот Email для резервного входа в личный кабинет и восстановления доступа к аккаунту в случае потери телефона.</p>
        <hr style="border: none; border-top: 1px solid #27344d; margin: 25px 0;">
        <p style="font-size: 12px; color: #5a6e85; text-align: center;">Telegram Guard Shield &copy; 2026</p>
    </div>
    """
    return send_email(to_email, subject, html_body)
