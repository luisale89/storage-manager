import logging
import requests
import os
from requests.exceptions import (
    RequestException
)
from flask import render_template
from app.utils.func_decorators import app_logger

logger = logging.getLogger(__name__)


class Email_api_service:
    """
    SMTP Service via API - SENDINBLUE
    """
    SMTP_API_URL = os.environ['SMTP_API_URL']
    QR_SECRET = os.environ["QR_SECRET_KEY"]
    MAIL_MODE = os.environ['MAIL_MODE']
    API_KEY = os.environ['SMTP_API_KEY']
    DEFAULT_SENDER = {"name": "Luis from MyApp", "email": "luis.lucena89@gmail.com"}
    DEFAULLT_CONTENT = "<!DOCTYPE html><html><body><h1>Email de prueba default</h1><p>development mode</p></body></html> "
    DEFAULT_SUBJECT = "this is a test email"
    ERROR_MSG = "Connection error to smtp server"

    def __init__(self, email_to: str, content=None, sender=None, subject=None):
        self.email_to = email_to
        self.content = content if content is not None else self.DEFAULLT_CONTENT
        self.sender = sender if sender is not None else self.DEFAULT_SENDER
        self.subject = subject if subject is not None else self.DEFAULT_SUBJECT

    def get_recipient(self) -> dict:
        return {
            "email": self.email_to
        }

    def get_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-key": self.API_KEY
        }

    def get_body(self) -> dict:
        return {
            "sender": self.sender,
            "to": self.get_recipient(),
            "subject": self.subject,
            "htmlContent": self.content
        }

    def send_request(self) -> tuple:
        """
        SMTP API request function
        return tuple with status and message:

        * (success:bool, msg:str)

        """
        if self.MAIL_MODE == 'development':
            print(self.content)
            return True, "email printed in console"

        try:
            r = requests.post(headers=self.get_headers(), json=self.get_body(), url=self.SMTP_API_URL, timeout=3)
            r.raise_for_status()

        except RequestException as e:
            return False, {"email_service": f"{e}"}

        return True, f"email sent to user: {self.email_to}"


@app_logger(logger)
def send_verification_email(user_email: str, verification_code: int, user_name: str = None) -> tuple:
    """
    Funcion para enviar un codigo de verificacion al correo electronico, el cual sera ingresado por el usuario a la app

    *returns tuple -> (success: bool, msg: str)
    """
    identifier = user_name if user_name is not None else user_email
    mail = Email_api_service(
        email_to=user_email,
        content=render_template(
            template_name_or_list="email/user-validation.html", 
            params={"code": verification_code, "user_name": identifier}
        ),
        subject="[My App] - Código de Verificación"
    )

    return mail.send_request()


@app_logger(logger)
def send_user_invitation(user_email: str, user_name: str = None, company_name: str = None):
    """
    funcion para invitar a un nuevo usuario a que se inscriba en la aplicacion. Este nuevo usuario fue invitado
    por otro usuario a participar en la gestion de su empresa.

    *returns tuple -> (success: bool, msg: str)
    """
    identifier = user_name if user_name is not None else user_email

    mail = Email_api_service(
        email_to=user_email,
        content=render_template(
            "email/user-invitation.html",
            params={"user_name": identifier, "company_name": company_name}
        ),
        subject="[My App] - Invitación a colaborar"
    )

    return mail.send_request()
