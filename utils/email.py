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



def get_email_template(title_text: str, content_html: str, is_professional: bool = False) -> str:
    """
    Generates a full HTML email using the standard ProTown design.
    """
    # Theme colors
    if is_professional:
        # Green theme for professionals
        header_bg = "linear-gradient(135deg, #42e695 0%, #3bb2b8 100%)"
        accent_color = "#3bb2b8" # Teal/Greenish
        button_color = "#3bb2b8"
    else:
        # Blue/Purple theme for customers (from user snippet)
        header_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
        accent_color = "#667eea"
        button_color = "#667eea"

    return f"""
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
                background: {header_bg};
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
                color: {accent_color};
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
                background: {button_color};
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            /* Specific for contact form or generic sections */
            .label {{ font-weight: bold; color: {accent_color}; }}
            .message-box {{ background-color: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid {accent_color}; margin-top: 10px; whitespace: pre-wrap; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1 style="margin: 0;">{title_text}</h1>
        </div>
        <div class="content">
            {content_html}
        </div>
        <div class="footer">
            <p>© 2025 ProTown Network. All rights reserved.</p>
        </div>
    </body>
    </html>
    """

def send_customer_welcome_email(customer_name: str, customer_email: str) -> tuple[bool, Optional[str]]:
    """
    Send a welcome email to a newly registered customer (Blue Theme).
    """
    subject = "Welcome to ProTown Network! 🎉"
    
    content = f"""
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
    """
    
    html_body = get_email_template("ProTown Network", content, is_professional=False)
    
    return send_email(customer_email, subject, html_body, is_html=True)


def send_professional_welcome_email(professional_name: str, professional_email: str) -> tuple[bool, Optional[str]]:
    """
    Send a welcome email to a newly registered professional (Green Theme).
    """
    subject = "Welcome to ProTown Network! 🚀"
    
    content = f"""
            <div class="welcome-text">Welcome, {professional_name}! 👋</div>
            <div class="message">
                Thank you for joining ProTown Network! We're excited to help you grow your business.
            </div>
            <div class="message">
                ProTown Network connects you with customers in your area who need your specific skills and services.
            </div>
            <div class="benefits">
                <h3 style="margin-top: 0; color: #3bb2b8;">What You Can Do:</h3>
                <div class="benefit-item">Receive leads directly from customers</div>
                <div class="benefit-item">Manage your profile and services</div>
                <div class="benefit-item">Build your reputation with customer reviews</div>
                <div class="benefit-item">Grow your client base effortlessly</div>
            </div>
            <div class="message">
                Your account is currently under review. We will notify you once your profile is verified and active.
            </div>
            <div class="message">
                If you have any questions, our support team is ready to assist you.
            </div>
            <div class="message" style="margin-top: 30px;">
                Best regards,<br>
                <strong>The ProTown Network Team</strong>
            </div>
    """
    
    html_body = get_email_template("ProTown Network", content, is_professional=True)
    
    return send_email(professional_email, subject, html_body, is_html=True)


def send_contact_form_email(name: str, email: str, subject: str, message: str) -> tuple[bool, Optional[str]]:
    """
    Send an email to ProTown Network with a query from the contact us form.
    """
    to_email = "support@protownnetwork.com"
    email_subject = f"Contact Us Query: {subject}"
    
    content = f"""
                <h2 style="margin: 0; color: #333;">New Contact Form Submission</h2>
                <div style="margin-top: 20px;">
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
    """
    # Internal email, can use default (Blue) or maybe Blue is fine.
    html_body = get_email_template("ProTown Admin", content, is_professional=False)
    
    # Set reply-to so hitting reply goes to the user
    reply_to = {"email": email, "name": name}
    
    return send_email(to_email, email_subject, html_body, is_html=True, reply_to=reply_to)

