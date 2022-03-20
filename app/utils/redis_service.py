import redis
import os
import datetime
from app.utils import (
    exceptions, helpers
)
from flask_jwt_extended import decode_token


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
        raise exceptions.APIException("invalid jwt in request", status_code=405)
    else:
        expires = jwt_exp - now_date
    print(expires) #debug
    try:
        r.set(jti, "", ex=expires)
    except :
        raise exceptions.APIException("connection error with redis server", status_code=500)

    pass