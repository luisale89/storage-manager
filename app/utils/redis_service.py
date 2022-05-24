import redis
import os
import datetime
from app.utils import (
    exceptions, helpers
)
from flask_jwt_extended import decode_token
from flask import abort

def redis_client():
    '''
    define a redis client with os.environ variables.
    '''
    r = redis.Redis(
        host= os.environ.get('REDIS_HOST', 'localhost'),
        port= os.environ.get('REDIS_PORT', '6379'), 
        password= os.environ.get('REDIS_PASSWORD', None)
    )
    return r


def add_jwt_to_blocklist(claims):
    r = redis_client()

    jti = claims['jti']
    jwt_exp = helpers._epoch_utc_to_datetime(claims['exp'])
    now_date = datetime.datetime.now()

    if (jwt_exp < now_date):
        raise exceptions.APIException("jwt in request is expired", status_code=405)
    else:
        expires = jwt_exp - now_date
    try:
        r.set(jti, "", ex=expires)
    except :
        abort(500, 'connection with redis service is down')

    pass