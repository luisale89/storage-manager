import functools
from flask import current_app


def app_logger(my_logger):
    '''app logger decorator. 
    parameter: my_logger -> specific logger to be used by the decorated function'''
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if current_app.debug:
                #debug_logs
                args_repr = [repr(a) for a in args]
                kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
                signature = ", ".join(args_repr + kwargs_repr)
                my_logger.debug(f"executing {func.__name__}({signature})")
                value = func(*args, **kwargs)
                my_logger.debug(f"{func.__name__!r} returned {value!r}")
            else:
                #production_logs
                value = func(*args, **kwargs)
                my_logger.info(f'excecuting {func.__name__!r}: [OK]')

            return value
        return wrapper
    return decorator