import logging
import redis
import os
import datetime
from app.utils import helpers

logger = logging.getLogger(__name__)

def redis_client():
    '''
    define a redis client with os.environ variables.
    '''
    logger.info('excecute redis-client()')
    r = redis.Redis(
        host= os.environ.get('REDIS_HOST', 'localhost'),
        port= os.environ.get('REDIS_PORT', '6379'), 
        password= os.environ.get('REDIS_PASSWORD', None)
    )
    return r


def add_jwt_to_blocklist(claims) -> tuple:
    '''function to save a jwt in redis
    * returns tuple -> (success:bool, msg:string)
    '''
    r = redis_client()

    jti = claims['jti']
    jwt_exp = helpers._epoch_utc_to_datetime(claims['exp'])
    now_date = datetime.datetime.now()

    if (jwt_exp < now_date):
        logger.debug('jwt in request is expired')
        return (True, 'jwt in request is already expired')
    else:
        expires = jwt_exp - now_date

    try:
        r.set(jti, "", ex=expires)
    except :
        logger.error("connection with redis service has failed")
        return (False, 'connection with redis service is unavailable')

    return (True, 'jwt in blocklist')