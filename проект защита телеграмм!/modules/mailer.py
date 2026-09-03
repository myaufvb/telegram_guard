import os
import requests
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GOOGLE_WEBHOOK_URL = os.getenv(
    "GOOGLE_MAIL_WEBHOOK_URL",
    "https://script.google.com/macros/s/AKfycbwa21YJ6OrS-lP-YuUquVGs22rQN0BtCg2lE9Ix2ERiQX7Nc-UghAyFSIhlFSpeHnf5ng/exec"
)

SMTP_USER = "vahobovmuhammadali014@gmail.com"
SMTP_PASSWORD = "bqsexjkugjhikzgc"
SMTP_HOST = "smtp.gmail.com"

def send_email(to_email: str, subject: str, html_body: str) -> dict:
    webhook_url = (os.getenv("GOOGLE_MAIL_WEBHOOK_URL") or "").strip() or GOOGLE_WEBHOOK_URL

    # 1. Primary: HTTPS Webhook to Google Apps Script (Bypasses all Render SMTP blocks!)
    if webhook_url:
        try:
            logging.info(f"Sending email to {to_email} via Google Apps Script Webhook...")
            payload = {
                "to": to_email,
                "subject": subject,
                "htmlBody": html_body
            }
            r = requests.post(webhook_url, json=payload, timeout=35)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    logging.info(f"✅ Email successfully delivered to {to_email} via Google Apps Script!")
                    return {"success": True, "method": "google_script"}
                else:
                    logging.warning(f"Google Script returned error: {data.get('error')}")
            else:
                logging.warning(f"Google Script HTTP status: {r.status_code}")
        except Exception as egas:
            logging.error(f"Google Script Webhook failed: {egas}")

    # 2. Fallback: Direct SMTP (Port 587 then 465)
    user = (os.getenv("SMTP_USER") or "").strip() or SMTP_USER
    password = (os.getenv("SMTP_PASSWORD") or "").strip() or SMTP_PASSWORD
    host = (os.getenv("SMTP_HOST") or "").strip() or SMTP_HOST

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Telegram Guard Security <{user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        server = smtplib.SMTP(host, 587, timeout=8)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return {"success": True, "method": "smtp_587"}
    except Exception as e587:
        pass

    try:
        server = smtplib.SMTP_SSL(host, 465, timeout=8)
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return {"success": True, "method": "smtp_465"}
    except Exception as e465:
        return {"success": False, "error": str(e465)}

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
