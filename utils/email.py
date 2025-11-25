import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Brevo (Sendinblue) Configuration (from environment variables)
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", "ProTown Newsletter")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(
    to_email: str,
    subject: str,
    body: str,
    is_html: bool = True
) -> tuple[bool, Optional[str]]:
    """
    Send a single email using Brevo API.
    Returns (success: bool, error_message: Optional[str])
    """
    try:
        # Prepare email payload for Brevo API
        payload = {
            "sender": {
                "name": BREVO_FROM_NAME,
                "email": BREVO_FROM_EMAIL
            },
            "to": [
                {
                    "email": to_email
                }
            ],
            "subject": subject
        }

        # Add HTML or text content
        if is_html:
            payload["htmlContent"] = body
        else:
            payload["textContent"] = body

        # Make API request to Brevo
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }

        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers=headers,
            timeout=10
        )

        # Check response
        if response.status_code == 201:
            return True, None
        else:
            error_data = response.json() if response.content else {}
            error_msg = f"Brevo API error for {to_email}: {response.status_code} - {error_data.get('message', response.text)}"
            logger.error(error_msg)
            return False, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f"Network error sending to {to_email}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error sending to {to_email}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
