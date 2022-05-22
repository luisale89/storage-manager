import logging
from flask import request
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages

logger = logging.getLogger(__name__)

def get_pagination_params() -> tuple:

    '''
    function to get pagination parameters from request
    default values are given if no parameter is in request.

    Return Tupple -> (page, limit)
    '''
    logger.info('get_pagination_params()')
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
    except:
        raise APIException.from_error(ErrorMessages(parameter="pagination_params", expected='int').invalidFormat)

    logger.info(f'pagination parameters acquired: page={page}, limit={limit}')
    return (page, limit)


def pagination_form(p_object) -> dict:
    '''
    Receive an pagination object from flask, returns a dict with pagination data, set to return to the user.
    '''
    return {
        "pagination": {
            "pages": p_object.pages,
            "has_next": p_object.has_next,
            "has_prev": p_object.has_prev,
            "current_page": p_object.page,
            "total_items": p_object.total
        }
    }
