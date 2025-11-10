__all__ = [ 'SNPITDBClient' ]

from rkwebutil.rkauth_client import rkAuthClient

from snappl.config import Config
from snappl.logger import SNLogger


class SNPITDBClient( rkAuthClient ):
    """A client for communcating with the Roman SNPIT internal database.

    To use: instantiate.  (See __init__ docstring.)

    For the most part, most people will just pass this on as an argument
    to snappl library calls.

    To use it directly, call one of the two methods "post" or "send".
    Both take two arguments; the first is the *relative* URL to the base
    URL you passed to the constructor.  (So, if the base url is
    "https://snpit-server.domain.org", and you want to conatncat
    "https://snpit-server.domain.org/foo", you would just pass "foo" as
    the URL to post or send.)  The second argument is a dictionary that
    will be pased to the server as POST data.  (See the documentation on
    the web API to figure out what you can send here.)

    "post" will return a requests.Response object.  "send" is what you
    call when you expect a JSON response; it will return you the parsed
    python object from the server (which will be a dictionary or a list).

    """

    default_dbclient = None

    @classmethod
    def get( cls, set_default=True, use_default=True, **kwargs ):
        """Create a SNPITDBClient

        All arguments are optional.  Will pull the url, and username
        from config options systm.db.url and system.db.username
        respectively.  If system.db.password is null, will read the
        password from the file system.db.passwordfile, otherwise will
        use the password in system.db.password.  (NOTE: you should leave
        system.db.password as null, as config files are usually global
        and are often committed to github archives!)

        Parameters
        ----------
          set_default : bool, default True
            If use_default is True and a SNPITDBClient has already been
            created, then just use that one.  Otherwise, save the newly
            created SNPITDBClient as the default.

          use_default : bool, default True
            If a SNPITDBClient has already been created, just return
            that.  If this is False, or one doesn't already exist, make
            a new one.  WARNING : thought required about how this might
            interact with multiprocessing and/or multithreading.  It may
            be safe, but you might want to make sure to always make a
            new dbclient with each new process.

          url : string
            The base URL of the roman snpit internal db.  If not given,
            will use the config value system.db.url

          username : string
            Username on the roman snpit internal db web api.  If not
            given, will use the config value system.db.username

          password : string
            Password on the roman snpit internal db web api.  If not
            given, will first try using the config value system.db.password; if
            that is None, or if that is not in the config file, will
            read the passowrd as the first line in the file given in the
            config value system.db.passwordfile

          retries : int, default 5
            When calling send or post, if the request to the server
            doesn't return a HTTP 200, try again at most this many
            times.

          maxtimeout : float, default 30.
            If retries are taking a very long time, don't keep retrying
            if this much time has passed.

          retrysleep : float, default 0.2
            After the first failed attempt to contact the server, sleep this many seconds
            before retrying.

          sleepfac : float, default 2
            Multiply the sleep time by this much after each retry.

          sleepfuzz : bool, default True
            Randomly adjust the sleep time by 10% of itself (Gaussian, sort of) so that if
            lots of processes are running, they will (hopefully) dsync.

          verify: bool, default True
            Verify SSL certs?  Sometimes for tests when you're using a
            test web server with a self-signed cert you may need to set
            this to fale.

        """
        if ( cls.default_dbclient is None ) or ( not use_default ):
            dbclient = SNPITDBClient( **kwargs )
        else:
            dbclient = cls.default_dbclient

        if set_default:
            cls.default_dbclient = dbclient

        return dbclient


    def __init__( self, url=None, username=None, password=None, passwordfile=None, **kwargs ):
        """Create a SNPITDBClient.

        Parameters
        ----------
          url : string
            The base URL of the roman snpit internal db.  If not given,
            will use the config value system.db.url

          username : string
            Username on the roman snpit internal db web api.  If not
            given, will use the config value system.db.username

          password : string
            Password on the roman snpit internal db web api.  If not
            given, will first try using the config value system.db.password; if
            that is None, or if that is not in the config file, will
            read the passowrd as the first line in the file given in the
            config value system.db.passwordfile

          retries : int, default 5
            When calling send or post, if the request to the server
            doesn't return a HTTP 200, try again at most this many
            times.

          maxtimeout : float, default 30.
            If retries are taking a very long time, don't keep retrying
            if this much time has passed.

          retrysleep : float, default 0.2
            After the first failed attempt to contact the server, sleep this many seconds
            before retrying.

          sleepfac : float, default 2
            Multiply the sleep time by this much after each retry.

          sleepfuzz : bool, default True
            Randomly adjust the sleep time by 10% of itself (Gaussian, sort of) so that if
            lots of processes are running, they will (hopefully) dsync.

          verify: bool, default True
            Verify SSL certs?  Sometimes for tests when you're using a
            test web server with a self-signed cert you may need to set
            this to fale.

        """
        cfg = Config.get()
        url = url if url is not None else cfg.value( 'system.db.url' )
        username = username if username is not None else cfg.value( 'system.db.username' )
        if ( password is None ) and ( passwordfile is None ):
            try:
                password = cfg.value( 'system.db.password' )
            except Exception:
                password = None
            if password is None:
                with open( cfg.value( 'system.db.passwordfile' ) ) as ifp:
                    password = ifp.readline().strip()
        else:
            if password is None:
                with open( passwordfile ) as ifp:
                    password = ifp.readline.strip()

        super().__init__( url, username, password, logger=SNLogger, **kwargs )
