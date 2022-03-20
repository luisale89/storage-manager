from app.models.main import (
    User
)
from app.utils.exceptions import APIException


def get_user_by_email(email):
    '''
    Helper function to get user from db, email parameter is required
    '''
    user = User.query.filter_by(email=email).first()

    if user is None:
        raise APIException(f"email: {email} not found in database", status_code=404, app_result="q_not_found")

    return user
