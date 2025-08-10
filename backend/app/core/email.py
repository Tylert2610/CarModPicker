from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import From, Mail, To

from app.core.config import settings
from app.core.logging import logger


def send_email(to_email: str, template_id: str, dynamic_template_data: dict):
    """
    Send an email using SendGrid.
    Args:
        to_email (str): Recipient's email address.
        template_id (str): ID of the email template to use.
        dynamic_template_data (dict): Dynamic data to populate the email template.
    Returns:
        int: HTTP status code of the response if successful, None if an error occurs.
    """
    message = Mail(
        from_email=From(settings.EMAIL_FROM),
        to_emails=To(to_email),
    )
    message.template_id = template_id
    message.dynamic_template_data = dynamic_template_data

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        return response.status_code
    except Exception as e:
        # Log or handle error as needed
        logger.error(f"Failed to send email: {e}")
        return None
