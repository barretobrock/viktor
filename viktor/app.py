import signal

from flask import (
    Flask,
    jsonify,
    request,
)
from pukr import (
    InterceptHandler,
    get_logger,
)
from werkzeug.exceptions import HTTPException
from werkzeug.http import HTTP_STATUS_CODES

from viktor.bot_base import Viktor
from viktor.db_eng import ViktorPSQLClient
from viktor.flask_base import db
from viktor.routes.actions import bp_actions
from viktor.routes.crons import bp_crons
from viktor.routes.events import bp_events
from viktor.routes.helpers import (
    get_app_logger,
    log_after,
    log_before,
)
from viktor.routes.main import bp_main
from viktor.routes.slash import bp_slash
from viktor.settings import Production

ROUTES = [
    bp_actions,
    bp_crons,
    bp_events,
    bp_main,
    bp_slash
]


def handle_err(err):
    _log = get_app_logger()
    _log.error(err)
    if err.code == 404:
        _log.error(f'Path requested: {request.path}')

    if isinstance(err, HTTPException):
        err_msg = getattr(err, 'description', HTTP_STATUS_CODES.get(err.code, ''))
        return jsonify({'message': err_msg}), err.code
    if not getattr(err, 'message', None):
        return jsonify({'message': 'Server has encountered an error.'}), 500
    return jsonify(**err.kwargs), err.http_status_code


def create_app(*args, **kwargs) -> Flask:
    config_class = kwargs.pop('config_class', Production)
    props = kwargs.pop('props')

    app = Flask(__name__, static_url_path='/')
    app.config.from_object(config_class)

    # Initialize database ops
    db.init_app(app)

    # Initialize logger
    logg = get_logger(config_class.BOT_NICKNAME, log_dir_path=config_class.LOG_DIR, show_backtrace=config_class.DEBUG,
                      base_level=config_class.LOG_LEVEL)
    logg.info('Logger started. Binding to app handler...')
    app.logger.addHandler(InterceptHandler(logger=logg))
    # Bind logger so it's easy to call from app object in routes
    app.extensions.setdefault('logg', logg)

    # Register routes
    logg.info('Registering routes...')
    for ruut in ROUTES:
        app.register_blueprint(ruut)

    for err_code, name in HTTP_STATUS_CODES.items():
        if err_code >= 400:
            try:
                app.register_error_handler(err_code, handle_err)
            except ValueError:
                pass

    app.config['db'] = db

    # Set up database connection
    logg.debug('Initializing db engine...')
    eng = ViktorPSQLClient(props=props, parent_log=logg)
    app.extensions.setdefault('eng', eng)

    logg.debug('Instantiating bot...')
    bot = Viktor(eng=eng, props=props, config=config_class, parent_log=logg)
    # Register the cleanup function as a signal handler
    signal.signal(signal.SIGINT, bot.cleanup)
    signal.signal(signal.SIGTERM, bot.cleanup)
    app.extensions.setdefault('bot', bot)

    app.before_request(log_before)
    app.after_request(log_after)

    return app
