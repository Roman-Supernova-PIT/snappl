import collections.abc

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
import astropy.wcs


class BaseWCS:
    def __init__( self ):
        pass

    def pixel_to_world( self, x, y ):
        """Go from (x, y) coordinates to (ra, dec )

        Parmaeters
        ----------
          x: float or sequence of float
             The x position on the image.  The center of the lower-left
             pixel is at x=0.0

          y: float or sequence of float
             The y position on the image.  The center of the lower-left
             pixle is y=0.0

        Returns
        -------
          ra, dec : floats or lists of floats, decimal degrees

          You will get back two floats if x an y were floats.  If x and
          y were lists (or other sequences), you will get back two lists
          of floats.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement pixel_to_world" )

    def world_to_pixel( self, ra, dec ):
        """Go from (ra, dec) coordinates to (x, y)

        Parameters
        ----------
          ra: float or sequence of float
             RA in decimal degrees

          dec: float or sequence of float
             Dec in decimal degrees

        Returns
        -------
           x, y: floats or list of floats

           Pixel position on the image; the center of the lower-left pixel is (0.0, 0.0).

           If ra and dec were floats, x and y are floats.  If ra and dec
           were sequences of floats, x and y will be lists of floats.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement world_to_pixel" )


class AstropyWCS(BaseWCS):
    def __init__( self, apwcs=None ):
        self._wcs = apwcs

    @classmethod
    def from_header( cls, header ):
        wcs = AstropyWCS()
        wcs._wcs = astropy.wcs.WCS( header )
        return wcs

    def pixel_to_world( self, x, y ):
        ra, dec = self._wcs.pixel_to_world_values( x, y )
        # I'm a little irritated that a non-single-value ndarray is not a collections.abc.Sequence
        if not ( isinstance( x, collections.abc.Sequence )
                 or ( isinstance( x, np.ndarray ) and x.size > 1 )
                ):
            ra = float( ra )
            dec = float( dec )
        return ra, dec

    def world_to_pixel( self, ra, dec ):
        scs = SkyCoord( ra, dec, unit=(u.deg, u.deg) )
        x, y = self._wcs.world_to_pixel( scs )
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y



class TotalDisasterASDFWCS(BaseWCS):
    pass
