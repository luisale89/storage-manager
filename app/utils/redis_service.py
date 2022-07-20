import logging
import redis
import os
import datetime
from app.utils.helpers import DateTimeHelpers
from app.utils.func_decorators import app_logger

logger = logging.getLogger(__name__)

class RedisClient:

    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = os.environ.get("REDIS_PORT", "6379")
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
    
    def __init__(self):
        pass

    def set_client(self):
        return redis.Redis(
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            password=self.REDIS_PASSWORD
        )

    @app_logger(logger)
    def add_jwt_to_blocklist(self, claims) -> tuple:
        """
        function to save a jwt in redis
        * returns tuple -> (success:bool, msg:string)
        """
        r = self.set_client()
        jti = claims["jti"]
        jwt_exp = DateTimeHelpers._epoch_utc_to_datetime(claims["exp"])
        now_date = datetime.datetime.utcnow()

        if jwt_exp < now_date:
            return True, "jwt in request is already expired"

        else:
            expires = jwt_exp - now_date

        try:
            r.set(jti, "", ex=expires)
        except redis.RedisError as re:
            return False, {"blocklist": f"{re}"}
        
        return True, "JWT in blocklist"