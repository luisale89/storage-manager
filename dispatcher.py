from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from app import create_app as create_api
from app_frontend import create_app as create_frontend
from app_landingpage import create_app as landingpage

application = DispatcherMiddleware(landingpage(), {
    '/app': create_frontend(),
    '/api': create_api()
})

if __name__ == '__main__':
    run_simple('localhost', 5000, application=application,
               use_reloader=True, use_debugger=True, use_evalex=True)