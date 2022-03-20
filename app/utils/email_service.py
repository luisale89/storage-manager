import requests
import os
from requests.exceptions import (
    ConnectionError, HTTPError
)
from flask import (
    render_template
)
from app.utils.exceptions import APIException

# constantes para la configuracion del correo
smtp_api_url = os.environ['SMTP_API_URL']
mail_mode = os.environ['MAIL_MODE']
api_key = os.environ['SMTP_API_KEY']
default_sender = {"name": "Luis from MyApp", "email": "luis.lucena89@gmail.com"}
default_content = "<!DOCTYPE html><html><body><h1>Email de prueba</h1><p>development mode</p></body></html>"
default_subject = "this is a test"


class Email_api_service():

    '''
    SMTP Service via API
    '''

    def __init__(self, recipient, content=default_content, sender=default_sender, subject=default_subject) -> None:
        self.content = content
        self.sender = sender
        self.recipient = recipient
        self.subject = subject

    def header(self):
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-key": api_key
        }

    def body(self):
        return {
            "sender": self.sender,
            "to": self.recipient,
            "subject": self.subject,
            "htmlContent": self.content
        }

    def send_request(self):
        '''
        SMTP API request function
        '''

        if mail_mode == 'development':
            print(self.content)
            return None

        try:
            r = requests.post(headers=self.header(), json=self.body(), url=smtp_api_url, timeout=3)
            r.raise_for_status()

        except (ConnectionError, HTTPError):
            raise APIException("Connection error to smtp server", status_code=503)

        pass


def send_verification_email(verification_code, user:dict=None):
    '''
    Funcion para enviar un codigo de verificacion al correo electronico, el cual sera ingresado por el usuario a la app
    '''
    user_name, user_email = user.get('fname'), user.get('email')

    if user_name is None or user_email is None:
        raise APIException("Missing parameters in verification function", status_code=503)

    email = Email_api_service(
        user_email, 
        content=render_template("email/user-validation.html", params = {"code":verification_code, "user_name": user_name}),
        subject="[My App] - Código de Verificación"
    )

    email.send_request()

    pass