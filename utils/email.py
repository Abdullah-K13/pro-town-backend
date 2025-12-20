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
    is_html: bool = True,
    reply_to: Optional[dict] = None
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

        if reply_to:
            payload["replyTo"] = reply_to

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


def send_customer_welcome_email(customer_name: str, customer_email: str) -> tuple[bool, Optional[str]]:
    """
    Send a welcome email to a newly registered customer.
    Returns (success: bool, error_message: Optional[str])
    """
    subject = "Welcome to ProTown Network! 🎉"
    
    # Create a professional HTML email body
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
                border-radius: 10px 10px 0 0;
            }}
            .content {{
                background: #f9f9f9;
                padding: 30px;
                border-radius: 0 0 10px 10px;
            }}
            .welcome-text {{
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .message {{
                font-size: 16px;
                margin-bottom: 20px;
            }}
            .benefits {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin: 20px 0;
            }}
            .benefit-item {{
                margin: 10px 0;
                padding-left: 25px;
                position: relative;
            }}
            .benefit-item:before {{
                content: "✓";
                position: absolute;
                left: 0;
                color: #667eea;
                font-weight: bold;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #666;
                font-size: 14px;
            }}
            .cta-button {{
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 style="margin: 0;">ProTown Network</h1>
        </div>
        <div class="content">
            <div class="welcome-text">Welcome, {customer_name}! 👋</div>
            <div class="message">
                Thank you for joining ProTown Network! We're thrilled to have you as part of our community.
            </div>
            <div class="message">
                ProTown Network connects you with verified, professional service providers in your area. 
                Whether you need home repairs, renovations, or professional services, we've got you covered.
            </div>
            <div class="benefits">
                <h3 style="margin-top: 0; color: #667eea;">What You Can Do:</h3>
                <div class="benefit-item">Browse verified professionals in your area</div>
                <div class="benefit-item">Request quotes for your projects</div>
                <div class="benefit-item">Read reviews from other customers</div>
                <div class="benefit-item">Manage all your service requests in one place</div>
                <div class="benefit-item">Get connected with trusted service providers</div>
            </div>
            <div class="message">
                Ready to get started? Log in to your account and submit your first service request today!
            </div>
            <div class="message">
                If you have any questions or need assistance, our support team is here to help.
            </div>
            <div class="message" style="margin-top: 30px;">
                Best regards,<br>
                <strong>The ProTown Network Team</strong>
            </div>
        </div>
        <div class="footer">
            <p>© 2025 ProTown Network. All rights reserved.</p>
            <p>You're receiving this email because you signed up for ProTown Network.</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(customer_email, subject, html_body, is_html=True)




def send_contact_form_email(name: str, email: str, subject: str, message: str) -> tuple[bool, Optional[str]]:
    """
    Send an email to ProTown Network with a query from the contact us form.
    """
    to_email = "support@protownnetwork.com"
    email_subject = f"Contact Us Query: {subject}"
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 10px; }}
            .header {{ background-color: #f8f9fa; padding: 10px 20px; border-bottom: 2px solid #667eea; border-radius: 10px 10px 0 0; }}
            .content {{ padding: 20px; }}
            .label {{ font-weight: bold; color: #667eea; }}
            .field {{ margin-bottom: 15px; }}
            .message-box {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #667eea; margin-top: 10px; whitespace: pre-wrap; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2 style="margin: 0; color: #333;">New Contact Form Submission</h2>
            </div>
            <div class="content">
                <div class="field">
                    <span class="label">From:</span> {name} ({email})
                </div>
                <div class="field">
                    <span class="label">Subject:</span> {subject}
                </div>
                <div class="field">
                    <span class="label">Message:</span>
                    <div class="message-box">
                        {message}
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Set reply-to so hitting reply goes to the user
    reply_to = {"email": email, "name": name}
    
    return send_email(to_email, email_subject, html_body, is_html=True, reply_to=reply_to)

