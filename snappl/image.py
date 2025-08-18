import re
import types
import pathlib

import numpy as np
from astropy.io import fits
from astropy.nddata.utils import Cutout2D
# from astropy.coordinates import SkyCoord

import galsim.roman
import roman_datamodels as rdm

from snpit_utils.logger import SNLogger
from snappl.wcs import AstropyWCS, GalsimWCS, GWCS


class Exposure:
    pass


class OpenUniverse2024Exposure:
    def __init__( self, pointing ):
        self.pointing = pointing


# ======================================================================
# The base class for all images.  This is not useful by itself, you need
#   to instantiate a subclass.  However, everything that you call on an
#   object you instantiate should have its interface defined in this
#   class.

class Image:
    """Encapsulates a single 2d image."""

    data_array_list = [ 'all', 'data', 'noise', 'flags' ]

    def __init__( self, path, exposure, sca ):
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
            that allows the class to find the image.

          exposure : Exposure (or instance of Exposure subclass)
            The exposure this image is associated with, or None if it's
            not associated with an Exposure (or youdon't care)

          sca : int
            The Sensor Chip Assembly that would be called the
            chip number for any other telescope but is called SCA for
            Roman.

        """
        self.inputs = types.SimpleNamespace()
        self.inputs.path = pathlib.Path( path )
        self.inputs.exposure = exposure
        self.inputs.sca = sca
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
        return self.inputs.sca

    @property
    def path( self ):
        return self.inputs.path

    @property
    def name( self ):
        return self.inputs.path.name

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
        c has magnitude m:

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

    def get_cutout(self, ra, dec, size):

        """Make a cutout of the image at the given RA and DEC.

        Returns
        -------
          snappl.image.Image
        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_cutout" )


    @property
    def coord_center(self):
        """[RA, DEC] (both floats) in degrees at the center of the image"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement coord_center" )


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
        imgs = self.get_data()
        self._data = imgs[0]
        self._noise = imgs[1]
        self._flags = imgs[2]

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
            hdr = self._get_header()
            self._image_shape = ( hdr['NAXIS1'], hdr['NAXIS2'] )
            return self._image_shape

        if self._image_shape is None:
            self._image_shape = self.data.shape

        return self._image_shape

    @property
    def coord_center(self):
        """[ RA and Dec ] at the center of the image."""

        wcs = self.get_wcs()
        return wcs.pixel_to_world( self.image_shape[1] //2, self.image_shape[0] //2 )

    def _get_header( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_header()" )

    def get_wcs( self, wcsclass=None ):
        wcsclass = "AstropyWCS" if wcsclass is None else wcsclass
        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "AstropyWCS":
                hdr = self._get_header()
                self._wcs = AstropyWCS.from_header( hdr )
            elif wcsclass == "GalsimWCS":
                hdr = self._get_header()
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

    def get_cutout(self, x, y, xsize, ysize=None):
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
        astropy_cutout = Cutout2D(data, (x, y), size=(ysize, xsize), mode='strict', wcs=apwcs)
        astropy_noise = Cutout2D(noise, (x, y), size=(ysize, xsize), mode='strict', wcs=apwcs)
        astropy_flags = Cutout2D(flags, (x, y), size=(ysize, xsize), mode='strict', wcs=apwcs)

        snappl_cutout = self.__class__(self.inputs.path, self.inputs.exposure, self.inputs.sca)
        snappl_cutout._data = astropy_cutout.data
        snappl_cutout._wcs = None if wcs is None else AstropyWCS( astropy_cutout.wcs )
        snappl_cutout._noise = astropy_noise.data
        snappl_cutout._flags = astropy_flags.data
        snappl_cutout._is_cutout = True

        return snappl_cutout

    def get_ra_dec_cutout(self, ra, dec, xsize, ysize=None):
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

        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.
        """

        wcs = self.get_wcs()
        x, y = wcs.world_to_pixel( ra, dec )
        x = int( np.floor( x + 0.5 ) )
        y = int( np.floor( y + 0.5 ) )
        return self.get_cutout( x, y, xsize, ysize )


# ======================================================================
# OpenUniverse 2024 Images are gzipped FITS files
#  HDU 0 : (something, no data)
#  HDU 1 : SCI (32-bit float)
#  HDU 2 : ERR (32-bit float)
#  HDU 3 : DQ (32-bit integer)

class OpenUniverse2024FITSImage( FITSImage ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

    def get_data( self, which='all', always_reload=False, cache=False ):
        if self._is_cutout:
            raise RuntimeError( "get_data called on a cutout image, this will return the ORIGINAL UNCUT image. "
                                "Currently not supported.")
        if which not in Image.data_array_list:
            raise ValueError( f"Unknown which {which}, must be all, data, noise, or flags" )

        if not always_reload:
            if ( ( which == 'all' )
                 and ( self._data is not None )
                 and ( self._noise is not None )
                 and ( self._flags is not None )
                ):
                return [ self._data, self._noise, self._flags ]

            if ( which == 'data' ) and ( self._data is not None ):
                return [ self._data ]

            if ( which == 'noise' ) and ( self._noise is not None ):
                return [ self._noise ]

            if ( which == 'flags' ) and ( self._flags is not None ):
                return [ self._flags ]

        SNLogger.info( f"Reading FITS file {self.inputs.path}" )
        with fits.open( self.inputs.path ) as hdul:
            if cache:
                self._header = hdul[1].header
            if which == 'all':
                imgs = [ hdul[1].data, hdul[2].data, hdul[3].data ]
                if cache:
                    self._data = imgs[0]
                    self._noise = imgs[1]
                    self._flags = imgs[2]
                return imgs
            elif which == 'data':
                if cache:
                    self._data = hdul[1].data
                return [ hdul[1].data ]
            elif which == 'noise':
                if cache:
                    self._noise = hdul[2].data
                return [ hdul[2].data ]
            elif which == 'flags':
                if cache:
                    self._flags = hdul[3].data
                return [ hdul[3].data ]
            else:
                raise RuntimeError( f"{self.__class__.__name__} doesn't understand data plane {which}" )

    def _get_header(self):
        """Get the header of the image."""
        if self._header is None:
            with fits.open(self.inputs.path) as hdul:
                self._header = hdul[1].header
        return self._header

    @property
    def band(self):
        """The band the image is taken in (str)."""
        header = self._get_header()
        return header['FILTER'].strip()

    @property
    def mjd(self):
        """The mjd of the image.

        TODO : is this start-time, mid-time, or end-time?

        """
        header = self._get_header()
        return float( header['MJD-OBS'] )

    @property
    def _get_zeropoint( self ):
        header = self._get_header()
        return galsim.roman.getBandpasses()[self.band].zeropoint + header['ZPTMAG']


# ======================================================================
# ManualFITSImage
#
# A FITS image that doesn't know where it got its data from, you just
# feed it the data.

class ManualFITSImage(FITSImage):
    def __init__(self, header, data, noise=None, flags=None, path = None, exposure = None, sca = None, *args, **kwargs):

        self._data = data
        self._noise = noise
        self._flags = flags
        self._header = header
        self._wcs = None
        self._is_cutout = False
        self._image_shape = None

        self.inputs = types.SimpleNamespace()
        self.inputs.path = None
        self.inputs.exposure = None
        self.inputs.sca = None

    def _get_header(self):
        """Get the header of the image."""
        if self._header is None:
            raise RuntimeError("Header is not set for ManualFITSImage.")
        return self._header


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
        self.inputs.sca = int( match.group(1) )


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
