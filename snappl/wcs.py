__all__ = [ 'BaseWCS', 'AstropyWCS', 'GalsimWCS', 'GWCS' ]

import collections.abc

import numpy as np
import astropy.coordinates
from astropy.coordinates import SkyCoord
import astropy.units as u
import astropy.wcs

import galsim
import roman_datamodels as rdm

# ASTROPY NOTE:
#
# We have played with astropy, and using pixel_to_world DOES include
# both SIP and TPV transformations (we are pretty sure).  In any event,
# if you make a WCS that's the linear approximation, you get different
# answers, meaning that the full WCS isn't just using the linear
# approximation.
#
# Note that to write out a header that includes SIP coefficients, you
# have to do wcs.to_header( relax=True ) where wcs is an astropy.wcs.WCS
# object.


# ======================================================================

class BaseWCS:
    """The base class that defines the WCS interface that should be used elsewhere.

    Code outside this module should only call methods that are defined
    in this class.  This class doesn'ta ctually do antyhing, however; to
    actually get a working WCS, you need to instantiate a subclass.

    """

    def __init__( self ):
        self._wcs = None
        self._wcs_is_astropy = False
        pass

    def pixel_to_world( self, x, y ):
        """Go from (x, y) coordinates to ICRS (ra, dec)

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

        Parameters
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

    def get_astropy_wcs( self, readonly=True, degree=None ):
        """Return an astropy.wcs.WCS object, if possible.

        Parameters
        ----------
          readonly: bool, default True
            If True, you are promising not to modify the WCS you get back!  If you're going to
            modify it, set readonly to False.  (For some subclasses, this doesn't actually change
            behavior.)

          degree: int
            The degree of the astropy WCS used to approximate the WCS in the object.  The default
            is subclass-dependent.  Ignored by some subclasses.

        For some subclasses, this astropy.wcs.WCS may only be an
        approximation of the true WCS represented by the object.

        """
        raise NotImplementedError( f"{self.__class__.__name__} can't return an astropy.wcs.WCS" )

    def to_fits_header( self ):
        """Return an astropy.io.fits.Header object, if possible, with the WCS in it."""
        raise NotImplementedError( f"{self.__class__.__name__} can't save itself to a FITS header." )


# ======================================================================


class AstropyWCS(BaseWCS):
    """A WCS that is defined by an astropy.wcs.WCS."""

    def __init__( self, apwcs=None ):
        super().__init__()
        self._wcs = apwcs
        self._wcs_is_astropy = True

    @classmethod
    def _fix_wcs_tan_with_pv1_0( cls, header ):
        if header['CTYPE1'] == 'RA---TAN' and 'PV1_0' in header:
            _hdr = header.copy()
            _hdr['CTYPE1'] = 'RA---TPV'
            _hdr['CTYPE2'] = 'DEC--TPV'
            return _hdr
        else:
            return header

    @classmethod
    def from_header( cls, header ):
        """Create an AstropyWCS from a FITS header.

        NOTE: if the header claims that the transformation type is "TAN"
        (i.e. CTYPE1 is "RA---TAN"), but the header also has a "PV1_0"
        keyword, this function will assume that the transformation is
        actually TPV.

        See:
        https://github.com/thomasvrussell/sfft/blob/45efa77452f020b8832a14c8682b87c5ffee4a93/sfft/utils/ReadWCS.py

        Parameters
        ----------
          header: duckish astropy.io.fits.header.Header
            Something that behaves like a FITS header, in that it can be
            accessed as a dictionary, has the copy() method, and canbe
            fead to astropy.wcs.WCS().

        Returns
        -------
          AstropyWCS

        """
        wcs = AstropyWCS()
        wcs._wcs = astropy.wcs.WCS( cls._fix_wcs_tan_with_pv1_0( header ) )
        return wcs

    def to_fits_header( self ):
        return self._wcs.to_header( relax=True )

    def get_galsim_wcs( self ):
        return galsim.AstropyWCS( wcs=self._wcs )

    def get_astropy_wcs( self, readonly=True ):
        if readonly:
            return self._wcs
        else:
            return self._wcs.deepcopy()

    def pixel_to_world( self, x, y ):
        ra, dec = self._wcs.pixel_to_world_values( x, y )
        # I'm a little irritated that a non-single-value ndarray is not a collections.abc.Sequence
        if not ( isinstance( x, collections.abc.Sequence )
                 or ( isinstance( x, np.ndarray ) and x.size > 1 )
                ):
            ra = float( ra )
            dec = float( dec )
        return ra, dec

    def world_to_pixel( self, ra, dec):
        frame = self._wcs.wcs.radesys.lower()  # Needs to be lowercase for SkyCoord
        scs = SkyCoord( ra, dec, unit=(u.deg, u.deg), frame = frame)
        x, y = self._wcs.world_to_pixel( scs )
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y


# ======================================================================

class GalsimWCS(BaseWCS):
    """A WCS speicifc to Galsim."""

    def __init__( self, gsimwcs=None ):
        super().__init__()
        self._gsimwcs = gsimwcs

    @classmethod
    def from_header( cls, header ):
        """Create a GalsimWCS from a FITS header.

        Does TAN-TPV conversion the same as AstropyWCS.from_header.

        Parameters
        ----------
          header: astropy.io.fits.header.Header
            See AstropyWCS.from_header

        Returns
        -------
          GalsimWCS

        """
        wcs = GalsimWCS()
        wcs._gsimwcs = galsim.AstropyWCS( header=AstropyWCS._fix_wcs_tan_with_pv1_0( header ) )
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


# ======================================================================

class GWCS(BaseWCS):
    """A "G" (Generalized?) WCS : https://gwcs.readthedocs.io/en/latest/

    In the current code, these are only read from ASDF files

    """

    def __init__( self, gwcs=None ):
        super().__init__()
        self._gwcs = gwcs

    @classmethod
    def from_adsf( cls, asdf_file ):
        """Load the WCS from the specified ASDF image file.  (Also see RomanDatamodelImage.get_wcs.)"""
        # read the ASDF file and get the WCS
        dm = rdm.open(asdf_file)
        wcs = GWCS()
        wcs._gwcs = dm.meta.wcs
        return wcs

    def pixel_to_world( self, x, y ):
        if not isinstance( self._gwcs.output_frame.reference_frame, astropy.coordinates.ICRS ):
            raise TypeError( "Error, the gwcs output frame is of type {type(self._gwcs.output_frame)}, "
                             "but we need it to be ICRS." )
        if isinstance( x, collections.abc.Sequence ) and not isinstance( x, np.ndarray ):
            x = np.array( x )
            y = np.array( y )

        # ADSF WCSes are 0-indexed (lower-left pixel is (0.5,0.5)) like astropy WCS, so no need to convert
        SkyCoord = self._gwcs.pixel_to_world(x, y)
        ra, dec = SkyCoord.ra.deg, SkyCoord.dec.deg
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

        # ADSF WCSes are 0-indexed (lower-left pixel is (0.5,0.5)) like astropy WCS, so no need to convert
        skyCoord = SkyCoord( ra, dec, unit=(u.deg, u.deg), frame=self._gwcs.output_frame.reference_frame )
        x, y = self._gwcs.world_to_pixel(skyCoord)
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y

    def get_astropy_wcs( self , readonly=True, degree=5 ):
        # ... I think there's a more direct way to do this other than writing a header?
        #  Ask Russel.  (He probably told me once and I forgot --Rob.)
        hdr = self._gwcs.to_fits(degree=degree)[0]
        return astropy.wcs.WCS( hdr )
