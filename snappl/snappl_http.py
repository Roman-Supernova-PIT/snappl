__all__ = [ 'retry_post' ]

import time
import requests

import numpy as np

from snappl.logger import SNLogger


def retry_post( url, json=None, data=None, retries=5, initsleep=1., sleepfac=1.5, fuzz=True, **kwargs ):
    """Do a python requests post to url, retrying on failures.

    Parameters
    ----------
      url: str
        url to POST to

      json: dict, default None
        What to give the the json= parmaeter of requests.post

      data: dict, default None
        What to give the data= parmaeter of requests.post

      retries: int, default 5
        Number of times to retry before giving up for good

      initsleep: float, default 1.
        Sleep this many seconds after the first failure.

      sleepfac: float, default 1.5
        Increase the sleeptime by this factor after each failure

      fuzz: bool, default True
        Randomly scatter the sleeptime by ~1/5 of the current sleeptime.  This is so
        if you have a bunch of processes all going at once, they don't
        accidentally sync up.

      verify: bool, default True
        Set false to not verify certs.  You usually want this True, may
        need to set it to False for tests or some such.

      **kwargs: further arguments are forwarded to requests.post.

    Returns
    -------
      requests.Response

    """

    sleeptime = initsleep
    previous_fail = False
    t0 = time.perf_counter()
    if fuzz:
        rng = np.random.default_rng()
    for tries in range( retries + 1 ):
        res = None
        try:
            res = requests.post( url, data=data, json=json, **kwargs )
            if res.status_code != 200:
                errmsg = f"Got status {res.status_code} trying to connect to {url}"
                if tries == retries:
                    SNLogger.error( errmsg )
                else:
                    SNLogger.debug( errmsg )
                raise RuntimeError( errmsg )
            if previous_fail:
                dt = time.perf_counter() - t0
                SNLogger.info( f"Connection to {url} succeeded after {tries} retries over {dt:.2f} seconds." )
            return res
        except Exception:
            previous_fail = True
            dt = time.perf_counter() - t0
            if tries < retries:
                actual_sleeptime = sleeptime
                if fuzz:
                    actual_sleeptime = max( initsleep/2., rng.normal( sleeptime, sleeptime/5. ) )
                status_code = "<unknown>" if res is None else res.status_code
                SNLogger.warning( f"Failed to connect to {url} after {tries+1} tries "
                                     f"over {dt:.2f} seconds, got status {status_code}; "
                                     f"sleeping {actual_sleeptime:.1f} seconds and retrying." )
                time.sleep( actual_sleeptime )
                sleeptime *= sleepfac
            else:
                SNLogger.error( f"Failed to connect to {url} after {retries} tries "
                                   f"over {dt:.2f} seconds.  Giving up." )
                if ( res is not None ) and ( res.status_code == 500 ):
                    SNLogger.debug( f"Body of 500 return: {res.text}" )
                raise
