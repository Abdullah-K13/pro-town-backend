import os
import requests
import logging

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY")

def send_sms(recipient_number: str, message: str, sender: str = None) -> bool:
    """
    Send an SMS using Brevo's Transactional SMS API.
    Returns True if successful, False otherwise.
    """
    if not BREVO_API_KEY:
        logger.error("Brevo API key is missing. Set BREVO_API_KEY env var.")
        return False

    if not sender:
        sender = os.getenv("BREVO_SMS_SENDER", "ProTown")

    url = "https://api.brevo.com/v3/transactionalSMS/sms"

    payload = {
        "sender": sender,
        "recipient": recipient_number,
        "content": message,
        "type": "transactional",
    }

    headers = {
        "api-key": BREVO_API_KEY,
        "accept": "application/json",
        "content-type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"SMS sent successfully to {recipient_number}")
        return True

    except requests.exceptions.RequestException as e:
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
             try:
                 error_detail = e.response.json()
             except:
                 pass
        
        logger.error(f"Error sending SMS to {recipient_number}: {error_detail}")
        return False
