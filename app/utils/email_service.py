import email
import requests
import os
from requests.exceptions import (
    ConnectionError, HTTPError
)
from flask import (
    current_app,
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

    def __init__(self, recipient, content=default_content, sender=default_sender, subject=default_subject):
        self.content = content
        self.sender = sender
        self.recipient = recipient
        self.subject = subject
        self.errorMessage = "Connection error to smtp server"

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
            return True

        try:
            r = requests.post(headers=self.header(), json=self.body(), url=smtp_api_url, timeout=3)
            r.raise_for_status()

        except (ConnectionError, HTTPError) as e:
            current_app.logger.error(f'email not sended - {e}')
            return False

        return True

    def handle_mail_error(self):
        raise APIException(self.errorMessage, status_code=503)


def send_verification_email(verification_code, user:dict=None):
    '''
    Funcion para enviar un codigo de verificacion al correo electronico, el cual sera ingresado por el usuario a la app
    '''
    user_email = user.get('email')

    if user_email is None:
        raise APIException("Missing parameters in 'send_verification_email' function", status_code=503)

    mail = Email_api_service(
        user_email, 
        content=render_template("email/user-validation.html", params = {"code":verification_code, "user_name": user_email}),
        subject="[My App] - Código de Verificación"
    )

    sended = mail.send_request()
    if not sended:
        mail.handle_mail_error()

    pass


def send_user_invitation(user_email, company_name, user_name=None):
    '''
    funcion para invitar a un nuevo usuario a que se inscriba en la aplicacion. Este nuevo usuario fue invitado
    por otro usuario a participar en la gestion de su empresa.
    '''
    identifier = user_name if user_name is not None else user_email

    mail = Email_api_service(
        recipient= user_email,
        content=render_template("email/user-invitation.html", params={"user_name": identifier, "company_name": company_name}),
        subject="[My App] - Invitación a colaborar"
    )

    sended = mail.send_request()
    if not sended:
        mail.handle_mail_error()

    pass