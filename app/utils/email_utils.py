import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
import logging
import csv
import io
import base64
from app.core.config import settings

def send_verification_email(to_email: str, code: str):
    try:
        api_key = settings.SENDGRID_API_KEY
        
        if not api_key:
            logging.warning("SENDGRID_API_KEY not found. Email verification will be skipped.")
            return None
            
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        from_email = Email(settings.FROM_EMAIL)
        to_email = To(to_email)
        subject = "Your Verification Code"
        content = Content("text/plain", f"Your verification code is: {code}")
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        
        if response.status_code in [200, 201, 202]:
            return response.status_code
        else:
            return None
            
    except Exception as e:
        return None 

def send_reset_link_email(to_email: str, link: str):
    try:
        api_key = settings.SENDGRID_API_KEY
        if not api_key:
            logging.warning("SENDGRID_API_KEY not found. Password reset email will be skipped.")
            return None
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        from_email = Email(settings.FROM_EMAIL)
        to_email = To(to_email)
        subject = "Reset your password"
        content = Content(
            "text/html",
            f"""
            <h2>Hi!</h2>
            <p>You can reset your FunnelAlchemy password by clicking on the link below.</p>
            <a href='{link}' style='display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;text-decoration:none;border-radius:4px;font-weight:bold;'>Click here to reset your password</a>
            <p>If you did not request a password reset, please ignore this e-mail or <a href='{settings.FROM_EMAIL}'>contact us</a>.</p>
            <p>Thanks,<br/>FunnelAlchemy Team</p>
            """
        )
        mail = Mail(from_email, to_email, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        if response.status_code in [200, 201, 202]:
            return response.status_code
        else:
            return None
    except Exception as e:
        return None 