import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
import logging
import csv
import io
import base64

def send_verification_email(to_email: str, code: str):
    try:
        api_key = os.getenv('SENDGRID_API_KEY')
        
        if not api_key:
            logging.warning("SENDGRID_API_KEY not found. Email verification will be skipped.")
            return None
            
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        from_email = Email('lauren@funnelalchemyhq.com')
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
        api_key = os.getenv('SENDGRID_API_KEY')
        if not api_key:
            return None
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        from_email = Email('lauren@funnelalchemyhq.com')
        to_email = To(to_email)
        subject = "Reset your password"
        content = Content(
            "text/html",
            f"""
            <h2>Hi!</h2>
            <p>You can reset your FunnelAlchemy password by clicking on the link below.</p>
            <a href='{link}' style='display:inline-block;padding:12px 24px;background:#2563eb;color:#fff;text-decoration:none;border-radius:4px;font-weight:bold;'>Click here to reset your password</a>
            <p>If you did not request a password reset, please ignore this e-mail or <a href='lauren@funnelalchemyhq.com'>contact us</a>.</p>
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

def send_leads_awaiting_approval_email(to_email: str, first_name: str, leads: list):
    try:
        api_key = os.getenv('SENDGRID_API_KEY')
        if not api_key:
            return None
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        from_email = Email('lauren@funnelalchemyhq.com')
        to_email = To(to_email)
        subject = "✅ Leads Awaiting Your Approval"
        body = f"""Hi {first_name},\nYou have new leads waiting for approval before they can be added to your campaign.\n(see attached CSV file)\nOnce approved, they'll be added to your sales sequence automatically.\n— Funnel Alchemy"""
        content = Content("text/plain", body)

        if not leads:
            csv_data = "No leads."
        else:   
            fieldnames = set()
            for lead in leads:
                for k, v in lead.items():
                    if v is not None and 'uuid' not in k.lower() and 'id' not in k.lower():
                        fieldnames.add(k)
            fieldnames = list(fieldnames)
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            for lead in leads:
                filtered = {k: v for k, v in lead.items() if v is not None and 'uuid' not in k.lower() and 'id' not in k.lower()}
                writer.writerow(filtered)
            csv_data = output.getvalue()

        encoded = base64.b64encode(csv_data.encode()).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName("leads_awaiting_approval.csv"),
            FileType("text/csv"),
            Disposition("attachment")
        )

        mail = Mail(from_email, to_email, subject, content)
        mail.attachment = attachment
        response = sg.client.mail.send.post(request_body=mail.get())
        if response.status_code in [200, 201, 202]:
            return response.status_code
        else:
            logging.error(f"Failed to send leads awaiting approval email: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Exception sending leads awaiting approval email: {e}")
        return None 