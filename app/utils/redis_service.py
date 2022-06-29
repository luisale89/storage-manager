import logging
import redis
import os
import datetime
from app.utils import helpers
from app.utils.func_decorators import app_logger

logger = logging.getLogger(__name__)


def redis_client():
    """
    define a redis client with environ variables.
    """
    r = redis.Redis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=os.environ.get('REDIS_PORT', '6379'),
        password=os.environ.get('REDIS_PASSWORD', None)
    )
    return r


@app_logger(logger)
def add_jwt_to_blocklist(claims) -> tuple:
    """
    function to save a jwt in redis
    * returns tuple -> (success:bool, msg:string)
    """
    r = redis_client()
    jti = claims['jti']
    jwt_exp = helpers._epoch_utc_to_datetime(claims['exp'])
    now_date = datetime.datetime.now()

    if jwt_exp < now_date:
        return True, 'jwt in request is already expired'
    else:
        expires = jwt_exp - now_date

    try:
        r.set(jti, "", ex=expires)
    except redis.RedisError:
        return False, 'connection with redis service is unavailable'

    return True, 'jwt in blocklist'
