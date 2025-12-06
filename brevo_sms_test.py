import os
import requests
from dotenv import load_dotenv

# Load .env file (optional)
load_dotenv()

BREVO_API_KEY = os.getenv("BREVO_API_KEY")  # required
SMS_SENDER = os.getenv("BREVO_SMS_SENDER", "ProTown")  # fallback
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

def send_sms(recipient, message):
    """
    Sends an SMS using Brevo's Transactional SMS API.
    """

    # In dev mode, don't actually send SMS
    if DEV_MODE:
        print("[DEV MODE] SMS not sent. Payload would have been:")
        print({
            "sender": SMS_SENDER,
            "recipient": recipient,
            "content": message,
            "type": "transactional"
        })
        return {"dev_mode": True, "message": "SMS skipped in dev mode"}

    url = "https://api.brevo.com/v3/transactionalSMS/sms"

    payload = {
        "sender": SMS_SENDER,
        "recipient": recipient,
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
        response.raise_for_status()  # raises for HTTP 4xx/5xx
        print("SMS successfully sent!")
        print("Response:", response.json())
        return response.json()

    except requests.HTTPError as http_err:
        error_data = response.json() if response.content else str(http_err)
        print("HTTP Error:", error_data)
        return {"error": True, "details": error_data}

    except Exception as e:
        print("Unexpected error:", str(e))
        return {"error": True, "details": str(e)}


if __name__ == "__main__":
    print("=== Brevo SMS Test ===")

    # Replace with your own phone number (E.164 format)
    test_number = "+18632756381"

    test_message = "Hello from ProTown! 🚀 SMS test via Brevo API."

    # Run test
    send_sms(test_number, test_message)