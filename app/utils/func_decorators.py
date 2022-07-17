import functools
from flask import current_app


def app_logger(my_logger):
    """app logger decorator.
    parameter: my_logger -> specific logger to be used by the decorated function"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if current_app.debug:
                # debug_logs
                my_logger.debug(f"executing {func.__name__!r}")
                value = func(*args, **kwargs)
                my_logger.debug(f"{func.__name__!r} returned {value!r}")
            else:
                # production_logs
                value = func(*args, **kwargs)
                my_logger.info(f'{func.__name__!r}: [OK]')

            return value

        return wrapper

    return decorator