from typing import Literal, Union, Tuple, Annotated
from models.user import User
from models.code import Code
from fastapi import HTTPException
from datetime import datetime, timedelta
import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import dotenv
 

dotenv.load_dotenv()







async def generate_code(type: Literal["password_reset", "account_activation"], user: User) -> bool:
    try:
        code_value = str(random.randint(100000, 999999))
        code = Code(
            type=type,
            value=code_value,
            expires_at=datetime.utcnow() + timedelta(minutes=40),
            user=user
        )
        print("Code", code_value)
        await code.save()
        if type == "password_reset":
            return send_reset_email(user.email, code_value)
        elif type == "account_activation":
            return send_confirmation_email(user.email, code_value)
        else:
            raise ValueError("Invalid code type provided.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate code: {e}")
    
def send_email(to_address: str, subject: str, message_html: str):
    user = os.getenv("SMTP_FROM_USER")
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port_str = os.getenv("SMTP_PORT")
    from_address = os.getenv("SMTP_FROM_ADDRESS")
    password = os.getenv('SMTP_PASSWORD')

    if not all([user, smtp_server, smtp_port_str, from_address, password]):
        raise ValueError("SMTP configuration is not set properly in environment variables.")

    assert user is not None
    assert smtp_server is not None
    assert smtp_port_str is not None
    assert from_address is not None
    assert password is not None
    smtp_port = int(smtp_port_str)
    message = MIMEMultipart()
    message["From"] = f'"{user}" <{from_address}>'
    message["To"] = to_address
    message["Subject"] = subject
    html = message_html
    message.attach(MIMEText(html, "html"))

    try:
        print(f"smtp_port: {smtp_port}")
        print(f"smtp_server : {smtp_server}")
        print(f"from_address: {from_address}")
        print("user: ", user)
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(from_address, password)
            server.send_message(message)
            return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
  



  
def send_confirmation_email(to_email: str, code: Union[str, int]):
    message_html = f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Email Activation</title>
        <style>
            /* General Styles */
            body {{
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
                font-family: Arial, sans-serif;
            }}
            .email-container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background-color: #2752D8;
                padding: 20px;
                text-align: center;
            }}
            .header img {{
                max-width: 150px;
            }}
            .body {{
                padding: 30px;
                color: #333333;
            }}
            .body h1 {{
                color: #2752D8;
                margin-bottom: 20px;
                font-size: 24px;
            }}
            .body p {{
                line-height: 1.6;
                font-size: 16px;
            }}
            .code-box {{
                background-color: #f0f4ff;
                border-left: 4px solid #2752D8;
                padding: 15px;
                margin: 20px 0;
                font-size: 18px;
                font-weight: bold;
                text-align: center;
                letter-spacing: 2px;
                color: #152B72;
                border-radius: 4px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 25px;
                background-color: #2752D8;
                color: #ffffff;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background-color 0.3s ease;
            }}
            .button:hover {{
                background-color: #1f3a99;
            }}
            .footer {{
                background-color: #f4f4f4;
                padding: 20px;
                text-align: center;
                font-size: 14px;
                color: #777777;
            }}
            .footer a {{
                color: #2752D8;
                text-decoration: none;
            }}
            @media only screen and (max-width: 600px) {{
                .body, .header, .footer {{
                    padding: 15px;
                }}
                .button {{
                    width: 100%;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <!-- Header Section -->
             
    
            <!-- Body Section -->
            <div class="body">
                <h1>Hello,</h1>
                <p>Please Enter the following verification code to log into Legal AI</p>
                <div class="code-box">
                    {code}
                </div>                
                <p>If you are having any issues with your account, please contact us at
                <span>
                support@legal.ai
                </span>
                
                </p>
            </div>
    
            <!-- Footer Section -->
            <div class="footer">
                <p>&copy; Legal AI. All rights reserved.</p>
               
            </div>
        </div>
    </body>
    </html>
    """
    subject = "Confirm Email to Activate Account"
    return send_email(to_email, subject, message_html)
    

def send_reset_email(to_email: str, code: Union[str, int]):
   
    
    message_html = f"""\
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset</title>
        <style>
            /* General Styles */
            body {{
                margin: 0;
                padding: 0;
                background-color: #f4f4f4;
                font-family: Arial, sans-serif;
            }}
            .email-container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                background-color: #2752D8;
                padding: 20px;
                text-align: center;
            }}
            .header img {{
                max-width: 150px;
            }}
            .body {{
                padding: 30px;
                color: #333333;
            }}
            .body h1 {{
                color: #2752D8;
                margin-bottom: 20px;
                font-size: 24px;
            }}
            .body p {{
                line-height: 1.6;
                font-size: 16px;
            }}
            .code-box {{
                background-color: #f0f4ff;
                border-left: 4px solid #2752D8;
                padding: 15px;
                margin: 20px 0;
                font-size: 18px;
                font-weight: bold;
                text-align: center;
                letter-spacing: 2px;
                color: #152B72;
                border-radius: 4px;
            }}
            .button {{
                display: inline-block;
                padding: 12px 25px;
                background-color: #2752D8;
                color: #ffffff;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background-color 0.3s ease;
            }}
            .button:hover {{
                background-color: #1f3a99;
            }}
            .footer {{
                background-color: #f4f4f4;
                padding: 20px;
                text-align: center;
                font-size: 14px;
                color: #777777;
            }}
            .footer a {{
                color: #2752D8;
                text-decoration: none;
            }}
            @media only screen and (max-width: 600px) {{
                .body, .header, .footer {{
                    padding: 15px;
                }}
                .button {{
                    width: 100%;
                    text-align: center;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <!-- Header Section -->
            <div class="header">
               
            </div>
    
            <!-- Body Section -->
            <div class="body">
                <h1>Hello,</h1>
                <p>You have requested to reset your password for your <strong>Legal AI</strong> account. Please use the reset code below to proceed:</p>
                
                <div class="code-box">
                    {code}
                </div>
                
                <p>If you did not request this password reset, please ignore this email or contact our support team.</p>
                <p>For any assistance, feel free to reach out to us.</p>
            </div>
    
            <!-- Footer Section -->
            <div class="footer">
                <p>&copy; Legal AI. All rights reserved.</p>
                
            </div>
        </div>
    </body>
    </html>
    """
    subject = "Confirm Email to Reset Password"
    return send_email(to_email, subject, message_html)

