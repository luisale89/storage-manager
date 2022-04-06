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
        raise APIException(f"email: {email} not found in database", status_code=404, app_result="not found")

    return user

def get_user_by_id(user_id, company_required=False):
    '''
    Helper function to get user from db, using identifier
    '''
    if user_id is None:
        raise APIException("user_id not found in jwt")

    user = User.query.get(user_id)

    if company_required and user.company is None:
        raise APIException("user has no company", app_result="no_content")

    if user is None:
        raise APIException(f"user_id: {user_id} does not exists in database", status_code=404, app_result='not found')

    return user