__all__ = [ 'application' ]

import logging
import flask
import snappl.db.webserver

# Going to use application as the app name because that's what Apache WSGI depends on
#   (even though by default we aren't using Apache)
application = flask.Flask(  __name__ )
# application.logger.setLevel( logging.INFO )
application.logger.setLevel( logging.DEBUG )

snappl.db.webserver.setup_flask_app( application )
