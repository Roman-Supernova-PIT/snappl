__all__ = [ 'Image', 'Numpy2DImage', 'FITSImage', 'ManualFITSImage', 'FITSImageOnDisk',
            'OpenUniverse2024FITSImage', 'RomanDatamodelImage' ]

import re
import pathlib
import random

import numpy as np
import pandas
from astropy.io import fits
from astropy.nddata.utils import Cutout2D
from astropy.coordinates import SkyCoord
from astropy.wcs.utils import skycoord_to_pixel
from astropy.table import Table
from astropy.modeling.fitting import NonFiniteValueError
import astropy.units
from photutils.aperture import CircularAperture, aperture_photometry, ApertureStats
from photutils.psf import PSFPhotometry
from photutils.background import LocalBackground, MMMBackground, Background2D


import galsim.roman
import roman_datamodels as rdm

from snpit_utils.logger import SNLogger
from snpit_utils.config import Config
from snappl.wcs import AstropyWCS, GalsimWCS, GWCS


# ======================================================================
# The base class for all images.  This is not useful by itself, you need
#   to instantiate a subclass.  However, everything that you call on an
#   object you instantiate should have its interface defined in this
#   class.

class Image:
    """Encapsulates a single 2d image.

    Properties inclue the following.  Some of these properties may not
    be defined for some subclasses of Image.

    * path : pathlib.Path; absolute path to the image on disk
    * pointing : int (str?); a unique identifier of the exposure associated with the image
    * sca : int (str?); the SCA of this image
    * band : str; filter
    * mjd : float; mjd of the start of the image
    * position_angle : float; position anglke in degree east of north (yes?) (is this defined?)
    * exptime : float; exposure time in seconds
    * sky_level : float; an estimate of the sky level in ADU if defined, which it often isn't
    * zeropoint : float; convert to AB mag with -2.5*log(adu) + zeropoint, where adu is the units of data

    * image_shape : tuple (ny, nx) of ints; the image size
    * data : 2d numpy array; the data of this image
    * noise : 2d numpy array; a 1σ noise image (if defined)
    * flags : 2d numpy array of ints; a pixel flags image (if defined)
    * coord_center : SOMETHING; ra and dec at the center of the image.

    """

    data_array_list = [ 'all', 'data', 'noise', 'flags' ]

    def __init__( self, path, pointing=None, sca=None ):
        """Instantiate an image.  You probably don't want to do that.

        This is an abstract base class that has limited functionality.
        You probably want to instantiate a subclass.

        For all implementations, the properties data, noise, and flags
        are lazy-loaded.  That is, they start empty, but when you access
        them, an internal buffer gets loaded with that data.  This means
        it can be very easy for lots of memory to get used without your
        realizing it.  There are a couple of solutions.  The first, is
        to call Image.free() when you're sure you don't need the data
        any more, or if you know you want to get rid of it for a while
        and re-read it from disk later.  The second is just not to
        access the data, noise, and flags properties, instead use
        Image.get_data(), and manage the data object lifetime yourself.

        Parameters
        ----------
          path : str
            Path to image file, or otherwise some kind of indentifier
            that allows the object to find the image.  Exactly what
            this needs to be is subclass-dependent, but it is usually
            a full absolute path on disk.

            If you don't know the path, but only know (say) the
            pointing, band, and sca of an image, then either use the
            get_image() method of an appropriate ImageCollection instead
            of instantiating an Image directly, or use the
            get_image_path() method of an appropriate ImageCollection.

          pointing : int (str?), default None
            The exposure this image is associated with.  If None, then
            the image will try to figure out the pointing from the path,
            if the specific Image subclass is able to do that.

          sca : int, default None
            The Sensor Chip Assembly that would be called the
            chip number for any other telescope but is called SCA for
            Roman.

        """
        self.path = pathlib.Path( path )
        self._pointing = pointing
        self._sca = sca
        self._wcs = None      # a BaseWCS object (in wcs.py)
        self._is_cutout = False
        self._zeropoint = None

    @property
    def data( self ):
        """The image data, a 2d numpy array."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data" )

    @data.setter
    def data( self, new_value ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data setter" )

    @property
    def noise( self ):
        """The 1σ pixel noise, a 2d numpy array."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement noise" )

    @noise.setter
    def noise( self, new_value ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement noise setter" )

    @property
    def flags( self ):
        """An integer 2d numpy array of pixel masks / flags TBD

        TODO : think about what we mean by this.  Right now it's subclass-dependent.  But, for
        usage, we need a way of making this more general. Issue #45.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement flags" )

    @flags.setter
    def flags( self, new_value ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement flags setter" )

    @property
    def image_shape( self ):
        """Tuple: (ny, nx) pixel size of image."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement image_shape" )

    @property
    def sca( self ):
        if self._sca is None:
            raise NotImplementedError( f"{self.__class__.__name__} doesn't know how to figure out the sca." )
        return self._sca

    @sca.setter
    def sca( self, val ):
        self._sca = val

    @property
    def pointing( self ):
        if self._pointing is None:
            raise NotImplementedError( f"{self.__class__.__name__} doesn't know how to figure out the pointing." )
        return self._pointing

    @pointing.setter
    def pointing( self, val ):
        self._pointing = val

    @property
    def name( self ):
        return self.path.name

    @property
    def sky_level( self ):
        """Estimate of the sky level in ADU."""
        raise NotImplementedError( "Do.")

    @property
    def exptime( self ):
        """Exposure time in seconds."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement exptime" )

    @property
    def band( self ):
        """Band (str)"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement band" )

    @property
    def zeropoint( self ):
        """Image zeropoint for AB magnitudes.

        The zeropoint zp is defined so that an object with total counts
        c (in whatever units data is in) has AB magnitude m:

           m = -2.5 * log(10) + zp

        """
        if self._zeropoint is None:
            self._get_zeropoint()
        return self._zeropoint

    @zeropoint.setter
    def zeropoint( self, val ):
        self._zeropoint = val

    @property
    def mjd( self ):
        """MJD of the start of the image (defined how? TAI?)"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement mjd" )

    @property
    def position_angle( self ):
        """Position angle in degrees east of north (or what)?"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement position_angle" )

    def fraction_masked( self ):
        """Fraction of pixels that are masked."""
        raise NotImplementedError( "Do.")

    def get_data( self, which='all', always_reload=False, cache=False ):
        """Read the data from disk and return one or more 2d numpy arrays of data.

        Parameters
        ----------
          which : str
            What to read:
              'data' : just the image data
              'noise' : just the noise data
              'flags' : just the flags data
              'all' : data, noise, and flags

          always_reload: bool, default False
            Whether this is supported depends on the subclass.  If this
            is false, then get_data() has the option of returning the
            values of self.data, self.noise, and/or self.flags instead
            of always loading the data.  If this is True, then
            get_data() will ignore the self._data et al. properties.

          cache: bool, default False
            Normally, get_data() just reads the data and does not do any
            internal caching.  If this is True, and the subclass
            supports it, then the object will cache the loaded data so
            that future calls with always_reload will not need to reread
            the data, nor will accessing the data, noise, and flags
            properties.

        The data read not stored in the class, so when the caller goes
        out of scope, the data will be freed (unless the caller saved it
        somewhere.  This does mean it's read from disk every time.

        Returns
        -------
          list (length 1 or 3 ) of 2d numpy arrays

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_data" )


    def free( self ):
        """Try to free memory."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement free" )

    def get_wcs( self, wcsclass=None ):
        """Get image WCS.  Will be an object of type BaseWCS (from wcs.py) (really likely a subclass).

        Parameters
        ----------
          wcsclass : str or None
            By default, the subclass of BaseWCS you get back will be
            defined by the Image subclass of the object you call this
            on.  If you want a specific subclass of BaseWCS, you can put
            the name of that class here.  It may not always work; not
            all types of images are able to return all types of wcses.

        Returns
        -------
          object of a subclass of snappl.wcs.BaseWCS

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_wcs" )

    def _get_zeropoint( self ):
        """Set self._zeropoint; see "zeropoint" property above."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_zeropoint" )

    def get_ra_dec_cutout(self, ra, dec, xsize, ysize=None, mode="strict", fill_value=np.nan):
        """Creates a new snappl image object that is a cutout of the original image, at a location in pixel-space.

        Parameters
        ----------
        ra : float
            RA coordinate of the center of the cutout, in degrees.
        dec : float
            DEC coordinate of the center of the cutout, in degrees.
        xsize : int
            Width of the cutout in pixels.
        ysize : int
            Height of the cutout in pixels. If None, set to xsize.
        mode : str, default 'strict'
            Passed to astropy.nddata.Cutout2D.  See its documentation for details. Essentially,
            "strict" does not allow for partial overlap, "partial" will fill in non-overlapping pixels with fill_value.
        fill_value : float, default np.nan
            Passed to astropy.nddata.Cutout2D.  Fill value for pixels that are outside the original
            image when mode='partial'.

        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.
        """
    raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_ra_dec_cutout" )

    def get_cutout(self, ra, dec, xsize, ysize=None, mode='strict', fill_value=np.nan):

        """Make a cutout of the image at the given RA and DEC.
        This implementation assumes that the image WCS is an AstropyWCS.

        Parameters
        ----------
        x : int
            x pixel coordinate of the center of the cutout.
        y : int
            y pixel coordinate of the center of the cutout.
        xsize : int
            Width of the cutout in pixels.
        ysize : int
            Height of the cutout in pixels. If None, set to xsize.
        mode : str, default 'strict'
            Passed to astropy.nddata.Cutout2D.  See its documentation for details. Essentially,
            "strict" does not allow for partial overlap, "partial" will fill in non-overlapping pixels with fill_value.
        fill_value : float, default np.nan
            Passed to astropy.nddata.Cutout2D.  Fill value for pixels that are outside the original
            image when mode='partial'.

        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_cutout" )


    @property
    def coord_center(self):
        """[RA, DEC] (both floats) in degrees at the center of the image"""
        wcs = self.get_wcs()
        return wcs.pixel_to_world( self.image_shape[1] //2, self.image_shape[0] //2 )


    def includes_radec( self, ra, dec ):
        wcs = self.get_wcs()
        sc = SkyCoord( ra=ra * astropy.units.deg, dec=dec * astropy.units.deg )
        try:
            x, y = skycoord_to_pixel( sc, wcs.get_astropy_wcs() )
        except astropy.wcs.wcs.NoConvergence:
            return False
        # NOTE : we're assuming a full-size image here.  Think about cutouts!
        return ( x >= 0 ) and ( x < 4088 ) and ( y >= 0 ) and ( y < 4008 )


    def ap_phot( self, coords, ap_r=9, method='subpixel', subpixels=5, bgsize=511, **kwargs ):
        """Do aperture photometry on the image at the specified coordinates.

        Does background subtraction using
        photutils.background.Background2D with box size bgsize.

        Parameters
        ----------
          coords: astropy.table.Table
            Must have (at least) columns 'x' and 'y' representing
            0-origin pixel coordinates. (CHECK THIS)

          ap_r: float, default 9
            Aperture radius in pixels

          method: str, default 'subpixel'
            Passed to the "method" parmeter of photutils.photometry.aperture_photometry

          subpixels: int, default 5
            Number of subpixels to use for the 'subpixel' method.

          bgsize: int, default 511
            Box size for photutils Background2D background subtraction.
            Set to <=0 to not do background subtraction.

          **kwargs : further arguments are passed directly to photutils.photometry.aperture_photometry

        Returns
        -------
          results: astropy.table.Table
            Results of photutils.aperture.aperture_photometry

        """

        x = np.array(coords['x'])
        y = np.array(coords['y'])
        photcoords = np.transpose(np.vstack([x, y]))
        apertures = CircularAperture(photcoords, r=ap_r)

        # This is potentially slow; thing about caching background if we're ever going to use ap_phot for real,
        #   especially if it's going to be called repeatedly on the same image.
        bg = 0. if bgsize <= 0 else Background2D( self.data, box_size=bgsize ).background

        ap_results = aperture_photometry( self.data - bg,
                                          apertures,
                                          method=method,
                                          subpixels=subpixels,
                                          **kwargs )
        apstats = ApertureStats(self.data, apertures)
        ap_results['max'] = apstats.max

        return ap_results


    def psf_phot( self, init_params, psf, forced_phot=True, fit_shape=(5, 5),
                  bginner=15, bgouter=25 ):
        """Do psf photometry.

        Does local background subtraction.

        Parameters
        ----------
          init_params: something
             passed to the init_params of a call to a
             photutils.psf.PSFPHotometry object.

          psf: snappl.psf.PSF
             The PSF profile to fit to the image.

          forced_phot: bool, default True
             If True, then the x and y positions are fixed.  If False,
             then they will be fit along with the flux.

          fit_shape: tuple of (int, int), default (5, 5)
             Shape of the stamp around the positions in which to do the fit.

          bginner: float, default 15
             Radius of inner boundry of annulus in which to measure background.

          bouter: float, default 25
             Radius of outer boundry of annulus in which to measure background.

        Returns
        -------
          TODO

        """

        if 'flux_init' not in init_params.colnames:
            raise Exception('Astropy table passed to kwarg init_params must contain column \"flux_init\".')

        psfmod = psf.getImagePSF()
        if forced_phot:
            SNLogger.debug( 'psf_phot: x, y are fixed!' )
            psfmod.x_0.fixed = True
            psfmod.y_0.fixed = True
        else:
            SNLogger.debug( 'psf_phot: x, y are fitting parameters!' )
            psfmod.x_0.fixed = False
            psfmod.x_0.fixed = False

        try:
            bkgfunc = LocalBackground(bginner, bgouter, MMMBackground())
            psfphot = PSFPhotometry(psfmod, fit_shape, localbkg_estimator=bkgfunc)
            psf_results = psfphot(self.data, error=self.noise, init_params=init_params)

            return psf_results

        except NonFiniteValueError:
            SNLogger.exception( 'fit_shape overlaps with edge of image, and therefore encloses NaNs! '
                                'Photometry cancelled.' )
            raise


# ======================================================================
# Lots of classes will probably internally store all of data, noise, and
#   flags as 2d numpy arrays.  Common code for those classes is here.

class Numpy2DImage( Image ):
    """Abstract class for classes that store their array internall as a numpy 2d array."""

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

        self._data = None
        self._noise = None
        self._flags = None
        self._image_shape = None

    @property
    def data( self ):
        if self._data is None:
            self._load_data()
        return self._data

    @data.setter
    def data(self, new_value):
        if ( isinstance(new_value, np.ndarray)
             and np.issubdtype(new_value.dtype, np.floating)
             and len(new_value.shape) ==2
            ):
            self._data = new_value
        else:
            raise TypeError( "Data must be a 2d numpy array of floats." )

    @property
    def noise( self ):
        if self._noise is None:
            self._load_data()
        return self._noise

    @noise.setter
    def noise( self, new_value ):
        if ( isinstance( new_value, np.ndarray )
             and np.issubdtype( new_value.dtype, np.floating )
             and len( new_value.shape ) == 2
            ):
            self._noise = new_value
        else:
            raise TypeError( "Noise must be a 2d numpy array of floats." )

    @property
    def flags( self ):
        if self._flags is None:
            self._load_data()
        return self._flags

    @flags.setter
    def flags( self, new_value ):
        if ( isinstance( new_value, np.ndarray )
             and np.issubdtype( new_value.dtype, np.integer )
             and len( new_value.shape ) == 2
            ):
            self._flags = new_value
        else:
            raise TypeError( "Flags must be a 2d numpy array of integers." )

    @property
    def image_shape( self ):
        """Subclasses probably want to override this!

        This implementation accesses the .data property, which will load the data
        from disk if it hasn't been already.  Actual images are likely to have
        that information availble in a manner that doesn't require loading all
        the image data (e.g. in a header), so subclasses should do that.

        """
        if self._image_shape is None:
            self._image_shape = self.data.shape
        return self._image_shape

    def _load_data( self ):
        """Loads (or reloads) the data from disk."""
        self.get_data( which="all", cache=True, always_reload=False )

    def free( self ):
        self._data = None
        self._noise = None
        self._flags = None


# ======================================================================
# A base class for FITSImages which use an AstropyWCS wcs.  Not useful
#   by itself, because which image you load will have different
#   assumptions about which HDU holds image, weight, flags, plus header
#   information will be different etc.  However, there will be some
#   shared code between all FITS implementations, so that's here.

class FITSImage( Numpy2DImage ):
    """Base class for classes that read FITS images and use an AstropyWCS wcs."""

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

        self._data = None
        self._noise = None
        self._flags = None
        self._header = None

    @property
    def image_shape(self):
        """tuple: (ny, nx) shape of image"""

        if not self._is_cutout:
            hdr = self.get_fits_header()
            self._image_shape = ( hdr['NAXIS1'], hdr['NAXIS2'] )
            return self._image_shape

        if self._image_shape is None:
            self._image_shape = self.data.shape

        return self._image_shape

    def get_fits_header( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_fits_header()" )

    def get_wcs( self, wcsclass=None ):
        wcsclass = "AstropyWCS" if wcsclass is None else wcsclass
        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "AstropyWCS":
                hdr = self.get_fits_header()
                self._wcs = AstropyWCS.from_header( hdr )
            elif wcsclass == "GalsimWCS":
                hdr = self.get_fits_header()
                self._wcs = GalsimWCS.from_header( hdr )
        return self._wcs

    def get_data(self, which="all"):
        if self._is_cutout:
            raise RuntimeError(
                "get_data called on a cutout image, this will return the ORIGINAL UNCUT image. Currently not supported."
            )
        if which not in Image.data_array_list:
            raise ValueError(f"Unknown which {which}, must be all, data, noise, or flags")

        if (which == "all"):
            if (self._data is not None) and (self._noise is not None) and (self._flags is not None):
                return [self._data, self._noise, self._flags]
            else:
                raise RuntimeError(
                    f"get_data called with which='all', but not all data arrays are set. "
                    f"Data: {self._data is not None}, Noise: {self._noise is not None},"
                    f" Flags: {self._flags is not None}"
                )

        if (which == "data"):
            if (self._data is not None):
                return [self._data]
            else:
                raise RuntimeError("get_data called with which='data', but data is not set.")

        if (which == "noise"):
            if (self._noise is not None):
                return [self._noise]
            else:
                raise RuntimeError("get_data called with which='noise', but noise is not set.")

        if (which == "flags"):
            if (self._flags is not None):
                return [self._flags]
            else:
                raise RuntimeError("get_data called with which='flags', but flags are not set.")

    def get_cutout(self, x, y, xsize, ysize=None, mode='strict', fill_value=np.nan):
        """Creates a new snappl image object that is a cutout of the original image, at a location in pixel-space.

        This implementation (in FITSImage) assumes that the image WCS is an AstropyWCS.

        Parameters
        ----------
        x : int
            x pixel coordinate of the center of the cutout.
        y : int
            y pixel coordinate of the center of the cutout.
        xsize : int
            Width of the cutout in pixels.
        ysize : int
            Height of the cutout in pixels. If None, set to xsize.
        mode: str, default 'strict'
            Passed to astropy.nddata.Cutout2D.  See its documentation for details. Essentially,
            "strict" does not allow for partial overlap, "partial" will fill in non-overlapping pixels with fill_value.
        fill_value: float, default np.nan
            Passed to astropy.nddata.Cutout2D.  Fill value for pixels that are outside the original 
            image when mode='partial'.

        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.

        """
        if not all( [ isinstance( x, (int, np.integer) ),
                      isinstance( y, (int, np.integer) ),
                      isinstance( xsize, (int, np.integer) ),
                      ( ysize is None or isinstance( ysize, (int, np.integer) ) )
                     ] ):
            raise TypeError( "All of x, y, xsize, and ysize must be integers." )

        if ysize is None:
            ysize = xsize
        if xsize % 2 != 1 or ysize % 2 != 1:
            raise ValueError( f"Size must be odd for a well defined central "
                              f"pixel, you tried to pass a size of {xsize, ysize}.")

        SNLogger.debug(f'Cutting out at {x , y}')
        data, noise, flags = self.get_data( 'all' )

        wcs = self.get_wcs()
        if ( wcs is not None ) and ( not isinstance( wcs, AstropyWCS ) ):
            raise TypeError( "Error, FITSImage.get_cutout only works with AstropyWCS wcses" )
        apwcs = None if wcs is None else wcs._wcs

        # Remember that numpy arrays are indexed [y, x] (at least if they're read with astropy.io.fits)

        astropy_cutout = Cutout2D(data, (x, y), size=(ysize, xsize), wcs=apwcs, mode=mode, fill_value=fill_value)
        astropy_noise = Cutout2D(noise, (x, y), size=(ysize, xsize), wcs=apwcs, mode=mode, fill_value=fill_value)
        # Because flags are integer, we can't use the same fill_value as the default.
        # Per the slack channel, it seemed 1 will be used for bad pixels.
        # https://github.com/spacetelescope/roman_datamodels/blob/main/src/roman_datamodels/dqflags.py
        astropy_flags = Cutout2D(flags, (x, y), size=(ysize, xsize), wcs=apwcs, mode=mode, fill_value=1)

        snappl_cutout = self.__class__(self.path)
        snappl_cutout._data = astropy_cutout.data
        snappl_cutout._wcs = None if wcs is None else AstropyWCS( astropy_cutout.wcs )
        snappl_cutout._noise = astropy_noise.data
        snappl_cutout._flags = astropy_flags.data
        snappl_cutout._is_cutout = True

        return snappl_cutout

    def get_ra_dec_cutout(self, ra, dec, xsize, ysize=None, mode='strict', fill_value=np.nan):
        """Creates a new snappl image object that is a cutout of the original image, at a location in pixel-space.

        Parameters
        ----------
        ra : float
            RA coordinate of the center of the cutout, in degrees.
        dec : float
            DEC coordinate of the center of the cutout, in degrees.
        xsize : int
            Width of the cutout in pixels.
        ysize : int
            Height of the cutout in pixels. If None, set to xsize.
        mode : str, default 'strict'
            Passed to astropy.nddata.Cutout2D.  See its documentation for details. Essentially,
            "strict" does not allow for partial overlap, "partial" will fill in non-overlapping pixels with fill_value.
        fill_value : float, default np.nan
            Passed to astropy.nddata.Cutout2D.  Fill value for pixels that are outside the original
            image when mode='partial'.

        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.
        """

        wcs = self.get_wcs()
        x, y = wcs.world_to_pixel( ra, dec )
        x = int( np.floor( x + 0.5 ) )
        y = int( np.floor( y + 0.5 ) )
        return self.get_cutout( x, y, xsize, ysize, mode=mode, fill_value=fill_value )


# ======================================================================
# ManualFITSImage
#
# A FITS image that doesn't know where it got its data from, you just
# feed it the data.

class ManualFITSImage(FITSImage):
    def __init__(self, header, data=None, noise=None, flags=None,
                 path = None, exposure = None, sca = None, *args, **kwargs):

        self._data = data
        self._noise = noise
        self._flags = flags
        self._header = header
        self._wcs = None
        self._is_cutout = False
        self._image_shape = None

        self.path = None
        self.exposure = None
        self.sca = None

    def get_fits_header(self):

        """Get the header of the image."""
        if self._header is None:
            raise RuntimeError("Header is not set for ManualFITSImage.")
        return self._header


# ======================================================================
# A class that's a FITS Image with a corresponding file or
#  set of files on disk.
#
# If noisepath and flagspath are None, that means that all of it is
#   packed into different HDUs of the smage image, in path.

class FITSImageOnDisk( FITSImage ):
    """An Image which is represnted by a FITS file on disk.

    Either there are three FITS files, one for image, one for noise, one
    for flags, or there is one FITS file.  If there is one FITS file,
    then imagehdu, noisehdu, and flagshdu must all be different.

    (It's also possible that there's *only* an image, which is used for
    some intermediate data products within pipelines.)

    """

    def __init__( self, *args, noisepath=None, flagspath=None,
                  imhdu=0, noisehdu=0, flagshdu=0, **kwargs ):
        super().__init__( *args, **kwargs )

        self.noisepath = pathlib.Path( noisepath ) if noisepath is not None else None
        self.flagspath = pathlib.Path( flagspath ) if flagspath is not None else None
        self.imhdu = imhdu
        self.noisehdu = noisehdu
        self.flagshdu = flagshdu

    def uncompressed_version( self, include=[ 'data', 'noise', 'flags' ], base_dir=None ):
        """Make sure to get a FITSImageOnDisk that's not compressed.

        If none of the files for the current FITSImageOnDisk object are
        compressed, just return this object.

        Otherwise, will write out up to three single-HDU FITS files in
        base_dir (which defaults to photometry.snappl.temp_dir from the
        config).

        Parameters
        ----------
          include : sequence of str
            Can include any of 'data', 'noise', 'flags'; which things to
            write.  Ignored if the current image isn't compressed.

          base_dir : Path
            The path to write the files

        Returns
        -------
          FITSImageOnDisk
            The path, noisepath, and flagspath properties will be set
            with the random filenames to which the FITS files were written.

        """
        if all( [ ( ( self.path is None ) or ( self.path.name[-5:] == '.fits' ) ),
                  ( ( self.noisepath is None ) or ( self.noisepath.name[-5:] == '.fits' ) ),
                  ( ( self.flagspath is None ) or ( self.flagspath.name[-5:] == '.fits' ) ) ] ):
            return self

        base_dir = pathlib.Path( base_dir if base_dir is not None
                                 else Config.get().value( 'photometry.snappl.temp_dir' ) )
        barf = "".join( random.choices( '0123456789abcdef', k=10 ) )
        impath = None
        noisepath = None
        flagspath = None
        header = self.get_fits_header()

        if 'data' in include:
            hdul = fits.HDUList( [ fits.PrimaryHDU( data=self.data, header=header ) ] )
            impath = base_dir / f"{barf}_image.fits"
            hdul.writeto( impath  )

        if 'noise' in include:
            hdul = fits.HDUList( [ fits.PrimaryHDU( data=self.noise, header=fits.header.Header() ) ] )
            noisepath = base_dir / f"{barf}_noise.fits"
            hdul.writeto( noisepath )

        if 'flags' in include:
            hdul = fits.HDUList( [ fits.PrimaryHDU( data=self.flags, header=fits.header.Header() ) ] )
            flagspath = base_dir / f"{barf}_flags.fits"
            hdul.writeto( flagspath )

        return FITSImageOnDisk( path=impath, noisepath=noisepath, flagspath=flagspath )


    def set_header( self, hdr ):
        if not isinstance( hdr, fits.header.Header ):
            raise TypeError( f"hdr must be a fits.header.Header, not a {type(hdr)}" )
        self._header = hdr

    def get_fits_header( self ):
        if self._header is None:
            with fits.open( self.path ) as hdul:
                self._header = hdul[ self.imhdu ].header
        return self._header

    def get_data( self, which="all", always_reload=False, cache=False ):
        if self._is_cutout:
            raise RuntimeError( "get_data called on a cutout image, this will return the ORIGINAL UNCUT image. "
                                "Currently not supported.")

        if which not in ( "all", "data", "noise", "flags" ):
            raise ValueError( f"Unknown which {which}" )
        toload = [ 'data', 'noise', 'flags' ] if which == "all" else [ which ]

        if not always_reload:
            if ( 'data' in toload ) and ( self._data is not None ):
                toload.remove( 'data' )
                data = self._data
            if ( 'noise' in toload ) and ( self._noise is not None ):
                toload.remove( 'noise' )
                noise = self._noise
            if ( 'flags' in toload ) and ( self._flags is not None ):
                toload.remove( 'flags' )
                flags = self._flags

        if len( toload ) > 0:
            # If we get here, we know we have to load data.

            # Open the data, and do everything else inside that with just in case
            #   noise and flags are part of the same FITS image.
            with fits.open( self.path ) as imhdul:
                if "data" in toload:
                    header = imhdul[ self.imhdu ].header
                    data = imhdul[ self.imhdu ].data
                    if cache:
                        self._data = data
                        self._header = header

                if "noise" in toload:
                    if self.noisepath is not None:
                        with fits.open( self.noisepath ) as noihdul:
                            noise = noihdul[ self.noisehdu ].data
                    else:
                        noise = imhdul[ self.noisehdu ].data
                    if cache:
                        self._noise = noise

                if "flags" in toload:
                    if self.flagspath is not None:
                        with fits.open( self.flagspath ) as flghdul:
                            flags = flghdul[ self.flagshdul ].data
                    else:
                        flags = imhdul[ self.flagshdu ].data
                    if cache:
                        self._flags = flags

        return ( [ data ] if which == "data"
                 else [ noise ] if which == "noise"
                 else [ flags ] if which == "flags"
                 else [ data, noise, flags ] )


    def save_data( self, which="all", overwrite=False,
                   path=None, imhdu=0,
                   noisepath=None, noisehdu=None,
                   flagspath=None, flagshdu=None ):
        """Write the data to the file."""
        raise NotImplementedError( "OMG needs to be done" )




# ======================================================================
# OpenUniverse 2024 Images are gzipped FITS files
#  HDU 0 : (something, no data)
#  HDU 1 : SCI (32-bit float)
#  HDU 2 : ERR (32-bit float)
#  HDU 3 : DQ (32-bit integer)

class OpenUniverse2024FITSImage( FITSImageOnDisk ):
    def __init__( self, *args, noisepath=None, flagspath=None, imhdu=1, noisehdu=2, flagshdu=3, **kwargs ):
        super().__init__( *args,
                          noisepath=noisepath, flagspath=flagspath,
                          imhdu=imhdu, noisehdu=noisehdu, flagshdu=flagshdu,
                          **kwargs )

    _filenamere = re.compile( r'^Roman_TDS_simple_model_(?P<band>[^_]+)_(?P<pointing>\d+)_(?P<sca>\d+).fits' )

    @property
    def pointing( self ):
        if self._pointing is None:
            # Irritatingly, the pointing is not in the header.  So, we have to
            #   parse the filename to get the pointing.
            mat = self._filenamere.search( self.path.name )
            if mat is None:
                raise ValueError( f"Failed to parse {self.path.name} for pointing" )
            self._pointing = int( mat.group( 'pointing' ) )
        return self._pointing

    @property
    def sca( self ):
        if self._sca is None:
            header = self.get_fits_header()
            self._sca = int( header['SCA_NUM'] )
        return self._sca

    @property
    def band(self):
        """The band the image is taken in (str)."""
        header = self.get_fits_header()
        return header['FILTER'].strip()

    @property
    def mjd(self):
        """The mjd of the image.

        TODO : is this start-time, mid-time, or end-time?

        """
        header = self.get_fits_header()
        return float( header['MJD-OBS'] )

    @property
    def exptime( self ):
        # Galsim has fixed exptimes for roman filters
        exptimes = {'F184': 901.175,
                   'J129': 302.275,
                   'H158': 302.275,
                   'K213': 901.175,
                   'R062': 161.025,
                   'Y106': 302.275,
                   'Z087': 101.7 }
        if self.band not in exptimes:
            raise ValueError( f"Don't know exptime for band {self.band}" )
        return exptimes[ self.band ]

    @property
    def truthpath( self ):
        """Path to truth catalog.  WARNING: this is OpenUniverse2024FITSImage-specific, use with care."""
        tds_base = pathlib.Path( Config.get().value( 'ou24.tds_base' ) )
        return ( tds_base / f'truth/{self.band}/{self.pointing}/'
                 f'Roman_TDS_index_{self.band}_{self.pointing}_{self.sca}.txt' )

    def _get_zeropoint( self ):
        header = self.get_fits_header()
        return galsim.roman.getBandpasses()[self.band].zeropoint + header['ZPTMAG']

    def _get_zeropoint_the_hard_way( self, psf, ap_r=9 ):
        """This is here hopefully as legacy code.

        If, however, it turns out that
        galsim.roman.getBandpasses()[self.band].zeropoint +
        header['ZPTMAG'] is not a good enough zeropoint, we may need to
        resort to this.

        """
        # Get stars from the truth
        truth_colnames = ['object_id', 'ra', 'dec', 'x', 'y', 'realized_flux', 'flux', 'mag', 'obj_type']
        truth_pd = pandas.read_csv(self.truthpath, comment='#', skipinitialspace=True, sep=' ', names=truth_colnames)
        star_tab = Table.from_pandas(truth_pd)
        star_tab['mag'].name = 'mag_truth'
        star_tab['flux'].name = 'flux_truth'
        # Gotta do the FITS vs. C offset
        star_tab['x'] -= 1
        star_tab['y'] -= 1

        star_tab = star_tab[ ( star_tab['obj_type'] == 'star' )
                             & ( star_tab['x'] >= 0 ) & ( star_tab['x'] < self.image_shape[1] )
                             & ( star_tab['y'] >= 0 ) & ( star_tab['y'] < self.image_shape[0] ) ]


        init_params = self.ap_phot( star_tab, ap_r=ap_r )
        # Needs to be 'xcentroid' and 'ycentroid' for PSF photometry.
        init_params['object_id'] = star_tab['object_id'].value
        init_params.rename_column( 'xcenter', 'xcentroid' )
        init_params.rename_column( 'ycenter', 'ycentroid' )
        init_params.rename_column( 'aperture_sum', 'flux_init' )
        final_params = self.psf_phot( init_params, psf, forced_phot=True )

        # Do not need to cross match. Can just merge tables because they
        # will be in the same order.  Remove redundant column flux_init
        final_params.remove_columns( [ 'flux_init'] )
        photres = astropy.table.join(star_tab, init_params, keys=['object_id'])
        photres = astropy.table.join(photres, final_params, keys=['id'])

        # Get the zero point.
        gs_zpt = galsim.roman.getBandpasses()[self.band].zeropoint
        area_eff = galsim.roman.collecting_area
        star_ap_mags = -2.5 * np.log10(photres['flux_init'])
        star_fit_mags = -2.5 * np.log10(photres['flux_fit'])
        star_truth_mags = ( -2.5 * np.log10(photres['flux_truth']) + gs_zpt
                            + 2.5 * np.log10(self.exptime * area_eff) )

        # Eventually, this should be a S/N cut, not a mag cut.
        zpt_mask = np.logical_and(star_truth_mags > 19, star_truth_mags < 21.5)
        zpt = np.nanmedian(star_truth_mags[zpt_mask] - star_fit_mags[zpt_mask])
        _ap_zpt = np.nanmedian(star_truth_mags[zpt_mask] - star_ap_mags[zpt_mask])

        return zpt


# ======================================================================
# RomanDatamodelImage
#
# An image read from a roman datamodel ASDF file
#
# Empirically:
#   self._dm.err**2 == self._dm.var_poisson + self._dm.var_rnoise + self.dm.var_flat

class RomanDatamodelImage( Image ):
    """An image read from a roman datamodel ASDF file.

    See Issue #46 for concerns about performance/memory and imlementation of this object.

    """

    _detectormatch = re.compile( "^WFI([0-9]{2})$" )

    def __init__( self, path ):
        super().__init__( path, None, None )
        # We really want to open the image readonly, because otherwise normal use of
        #   this class will modify the image on disk.  We really don't want to modify
        #   our input data, and want to be explicit about saving like we are used
        #   to with FITS files.
        self._dm = rdm.open( path, mode='r' )
        match = self._detectormatch.search( self._dm.meta.instrument.detector )
        if match is None:
            raise ValueError( f'Failed to parse self._dm.meat.instrument.detector= '
                              f'"{self._dm.meta.instrument.detector} for "WFInn"' )
        self.sca = int( match.group(1) )


    @property
    def band( self ):
        return self.dm.meta.instrument.optical_element

    @property
    def mjd( self ):
        return self.dm.meta.exposure.mid_time.mjd

    @property
    def data( self ):
        # WORRY.  This actually returns a asdf.tags.core.ndarray.NDArrayType.
        # I'm hoping it will be duck-typing equivalent to a numpy array.
        # TODO : investigate memory use when you do numpy array things
        # with one of these.
        return self.dm.data

    @property
    def noise( self ):
        # See comment in data
        return self.dm.err

    @property
    def flags( self ):
        # See comment in data
        # TODO : https://roman-pipeline.readthedocs.io/en/latest/roman/dq_init/reference_files.html#reference-files
        # We probably need to do some translation.  We have to think about what we are defining
        #   as a "bad" pixel.
        return self.dm.dq

    def get_data( self, which='all', always_reload=False, cache=False ):
        """Read the data from disk and return one or more 2d numpy arrays of data.

        See Image.get_data for definition of parameters.

        Subclass-specific wrinkle:

        get_data will return actual 2d numpy arrays, which means that
        the memory will always be copied from what is stored from the
        open roman_datamodels file.  We may revisit this later as we
        think about memory implications.  (Issue #46.)

        Once you get the data, it will always be cached, even if you
        pass cache=False.  (This is because we keep the roman_datamodels
        file open, and currently there's no way to free the data without
        closing and reopening the file.)  So, cache=False does not save
        any memory, alas.  (Again, Issue #46.)

        As such, always_reload and cache are ignored for this class.
        This is not great, because always_reload ought to get a fresh
        copy of the data even if it's been modified.  To really behave
        that way, though, we'd have to reimplement the class to not hold
        open the roman_datamodels image.

        """
        if self._is_cutout:
            raise RuntimeError( f"{self.__class__.__name__} images don't know how to deal with being cutouts." )

        if which == 'all':
            return [ np.array(self.data), np.array(self.noise), np.array(self.flags) ]

        if which == 'data':
            return [ np.array(self.data) ]

        if which == 'noise':
            return [ np.array(self.noise) ]

        if which == 'flags':
            return [ np.array(self.flags) ]

        raise ValueError( f"Unknown value of which: {which}" )


    @property
    def dm( self ):

        """This property should usually not be used outside of this class."""
        # THOUGHT REQUIRED : worry a little about accessing members of
        #   the dm object and memory getting eaten.  Perhaps implement
        #   a "free" method for Image and subclasses.  Alas, for this
        #   class, based on feedback from ST people, the only way to free
        #   things is to delete and reopen the self._dm object.  Make sure
        #   to do that carefully if we do that.
        if self._dm is None:
            self._dm = rdm.open( self.input.path )
        return self._dm

    def get_wcs( self, wcsclass=None ):
        wcsclass = "GWCS" if wcsclass is None else wcsclass
        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "GWCS":
                self._wcs = GWCS( gwcs=self.dm.meta.wcs )
            else:
                raise NotImplementedError( "RomanDataModelImage can't (yet?) get a WCS of type {wcsclass}" )
        return self._wcs
