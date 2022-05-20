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
        raise APIException('invalid format in query string, <int> is expected')

    logger.info(f'pagination parameters acquired: page={page}, limit={limit}')
    return (page, limit)


def valid_id(_id:int, silent=False):
    '''function that check if an integer is a valid id. 
    returns integer if is valid
    returns None if invalid

    if silent = False, raises an APIException and break the program
    '''
    logger.info(f'valid_id({_id}, {silent})')
    try:
        id = int(_id)
        if id <= 0:
            id = None
            logger.debug("_id can't be < than 0")
    except:
        logger.debug("can't convert _id to integer")
        id = None
    
    if id is None and not silent:
        raise APIException(ErrorMessages().invalidID)
    
    logger.info(f'return id')
    return id


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
