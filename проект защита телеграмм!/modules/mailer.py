import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_USER = os.getenv("SMTP_USER", "vahobovmuhammadali014@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "yiymvfopcrgbnfzq")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))

def send_email(to_email: str, subject: str, html_body: str) -> dict:
    if not SMTP_PASSWORD:
        logging.warning(f"[SIMULATION] SMTP_PASSWORD is not set. Email to {to_email}: {subject}")
        return {"success": True, "simulated": True, "message": "Письмо смоделировано (укажите SMTP_PASSWORD в переменных Render)"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Telegram Guard Shield <{SMTP_USER}>"
        msg["To"] = to_email

        html_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(html_part)

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)

        logging.info(f"Email successfully sent to {to_email}")
        return {"success": True, "simulated": False}
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {e}")
        return {"success": False, "simulated": False, "error": str(e)}

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
