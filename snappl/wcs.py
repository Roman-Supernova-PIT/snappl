import collections.abc

import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
import astropy.wcs

import galsim


class BaseWCS:
    def __init__( self ):
        self._wcs = None
        self._wcs_is_astropy = False
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
          ra, dec : floats or arrays of floats, decimal degrees

          You will get back two floats if x an y were floats.  If x and
          y were lists (or other sequences), you will get back two numpy
          arrays of floats.

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
           x, y: floats or arrays of floats

           Pixel position on the image; the center of the lower-left pixel is (0.0, 0.0).

           If ra and dec were floats, x and y are floats.  If ra and dec
           were sequences of floats, x and y will be numpy arrays of floats.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement world_to_pixel" )

    @classmethod
    def from_header( cls, header ):
        """Create an object from a FITS header.

        May not be implemented for all subclasses.

        Parmaeters
        ----------
          header : astropi.io.fits.Header or dict
             Something that an astropy WCS is able to create itself from.

        Returns
        -------
          An object of the class this class method was called on.

        """
        # This is a dubious function, since it will only work for WCSes based out of FITS, and
        #   won't work for all FITS subclasses.
        raise NotImplementedError( f"{cls.__name__} can't do from_header" )

    def get_galsim_wcs( self ):
        """Return a glasim.AstropyWCS object, if possible."""
        raise NotImplementedError( f"{self.__class__.__name__} can't return a galsim.AstropyWCS" )

    def to_fits_header( self ):
        """Return an astropy.io.fits.Header object, if possible, with the WCS in it."""
        raise NotImplementedError( f"{self.__class__.__name__} can't save itself to a FITS header." )


class AstropyWCS(BaseWCS):
    def __init__( self, apwcs=None ):
        super().__init__()
        self._wcs = apwcs
        self._wcs_is_astropy = True

    @classmethod
    def from_header( cls, header ):
        wcs = AstropyWCS()
        wcs._wcs = astropy.wcs.WCS( header )
        return wcs

    def to_fits_header( self ):
        return self._wcs.to_header( relax=True )

    def get_galsim_wcs( self ):
        return galsim.AstropyWCS( wcs=self._wcs )

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


class GalsimWCS(BaseWCS):
    def __init__( self, gsimwcs=None ):
        super().__init__()
        self._gsimwcs = gsimwcs

    @classmethod
    def from_header( cls, header ):
        wcs = GalsimWCS()
        wcs._gsimwcs = galsim.AstropyWCS( header=header )
        return wcs

    def to_fits_header( self ):
        return self._gsimwcs.wcs.to_header( relax=True )

    def get_galsim_wcs( self ):
        return self._gsimwcs

    def pixel_to_world( self, x, y ):
        if isinstance( x, collections.abc.Sequence ) and not isinstance( x, np.ndarray ):
            x = np.array( x )
            y = np.array( y )
        # Galsim WCSes are 1-indexed
        ra, dec = self._gsimwcs.toWorld( x+1, y+1, units='deg' )
        if not ( isinstance( x, collections.abc.Sequence )
                 or ( isinstance( x, np.ndarray ) and ra.size > 1 )
                ):
            ra = float( ra )
            dec = float( dec )
        return ra, dec

    def world_to_pixel( self, ra, dec ):
        if isinstance( ra, collections.abc.Sequence ) and not isinstance( ra, np.ndarray ):
            ra = np.array( ra )
            dec = np.array( dec )
        x, y = self._gsimwcs.toImage( ra, dec, units='deg' )
        # Convert from 1-indexed galsim pixel coordaintes to 0-indexed
        x -= 1
        y -= 1
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y


class TotalDisasterASDFWCS(BaseWCS):
    pass
