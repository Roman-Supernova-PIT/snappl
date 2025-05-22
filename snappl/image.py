import types

import numpy as np
from astropy.io import fits
from astropy.nddata.utils import Cutout2D

import roman_datamodels as rdm

from snpit_utils.logger import SNLogger
from snappl.wcs import AstropyWCS


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
        self.inputs.path = path
        self.inputs.exposure = exposure
        self.inputs.sca = sca
        self._wcs = None      # a BaseWCS object (in wcs.py)
        self._is_cutout = False

    @property
    def data( self ):
        """The image data, a 2d numpy array or something that behaves similarly.

        Don't assume it's exactly a 2d numpy array; it might actually be
        something else.  However, for the most part, you can do things
        to it that you do to numpy arrays.  Indexing, slicing, .shape,
        .sum, .mean, .std, etc. should all work more or less as it does
        in numpy.  You can also pass it, often, to functions requiring a
        numpy array.
        """

        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data" )

    @data.setter
    def data( self, new_value ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data setter" )

    @property
    def noise( self ):
        """The 1σ pixel noise, type the same as the type of data."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement noise" )

    @noise.setter
    def noise( self, new_value ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement noise setter" )

    @property
    def flags( self ):
        """An integer array of pixel masks / flags TBD; see data for datatype warnings.

        NOTE : we currently do not document the meaning of anything in
        these flags!  If you need to use them, let's talk.  Do NOT
        assume that 0 = good, not 0 = bad, because that may well not be
        the case!

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
          list (length 1 or 3 ) of 2d numpy arrays.  If 3, is in the order data, noise, flags

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_data" )


    def free( self ):
        """Try to free memory."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement free" )

    def get_wcs( self ):
        """Get image WCS.  Will be an object of type BaseWCS (from wcs.py) (really likely a subclass).

        Returns
        -------
          snappl.wcs.BaseWCS

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_wcs" )

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

    def get_wcs( self ):
        if self._wcs is None:
            hdr = self._get_header()
            self._wcs = AstropyWCS.from_header( hdr )
        return self._wcs

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
        data, noise, flags = self.get_data( 'all', always_reload=False )

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


# ======================================================================

class RomanDatamodelL2Image( Image ):
    """A Roman L2 image in ASDF, read using roman_datamodels."""

    def __init__( self, path, exposure, sca ):
        super().__init__( path, exposure, sca )
        self._dm_file = rdm.open( path )
        if len( self._dm_file.shape ) != 2:
            raise ValueError( f"Error, {path} has shape {self._dm_file.shape}, which is not 2d." )

    def __del__( self ):
        if self._dm_file is not None:
            self._dm_file.close()

    @property
    def data( self ):
        return self._dm_file.data

    @data.setter
    def data( self, val ):
        # TODO : figure out the right way to wholesale replace the data array
        #   in a datamodel file.
        raise NotImplementedError( "RomanDatamodelL2Image doesn't support setting data" )

    @property
    def noise( self, val ):
        return self._dm_file.err

    @noise.setter
    def noise( self, val ):
        # TODO : figure out the right way to wholesale replace the err array
        #   in a datamodel file.
        raise NotImplementedError( "RomanDatamodelL2Image doesn't support setting noise" )

    @property
    def flags( self ):
        return self._dm_file.dq

    @flags.setter
    def flags( self, val ):
        # TODO : figure out the right way to wholesale replace the dq array
        #   in a datamodel file.
        raise NotImplementedError( "RomanDatamodelL2Image doesn't support setting noise" )

    @property
    def image_shape( self ):
        return self._dm_file.shape

    @property
    def exptime( self ):
        # TODO : is this the right thing?  Or should we bse using "exposure_time"?
        return self._dm_file.meta.exposure[ 'effective_exposure_time' ]

    @property
    def band( self ):
        # TODO : this looks right based on my inspection of a file, but
        #   I haven't found any documentation telling me that I'm doing
        #   the right thing.
        return self._dm_file.meta.instrument['optical_element']

    def get_data( self, which='all', always_reload=False, cache=False ):
        if not always_reload:
            # In this case, we're going to ignore cache; because of
            #   how the roman_datamodel works, I don't know how
            #   to read the data but then not have it use up memory.
            if not cache:
                SNLogger.warning( "get_data ignoring cache=False for RomanDatamodelL2Image" )
            if which == 'all':
                return [ self.data, self.noise, self.flags ]
            else:
                return [ getattr( self, which ) ]

        else:
            # We said always reload, so open a different datamodel file, pull out the data, then close it
            if cache:
                # TODO : think about the right way to support this if we want to.  Maybe
                #   just reopen the whole file?  But that would cache everything, not just
                #   the plane we want.
                raise NotImplementedError( "get_data with always_reload=True and cache=True not supported "
                                           "for RomanDatamodelL2Image" )
            newdm = None
            try:
                newdm = rdm( self.inputs.path )
                if which == 'all':
                    return [ newdm.data[:], newdm.err[:], newdm.dq[:] ]
                elif which == 'data':
                    return [ newdm.data[:] ]
                elif which == 'noise':
                    return [ newdm.err[:] ]
                elif which == 'flags':
                    return [ newdm.dq[:] ]
                else:
                    raise ValueError( f"Unknown which {which}, must be all, data, noise, or flags" )

            finally:
                # Even though we're closing the file, the arrays we accessed above will stil
                #   be in memory.  (In fact, I think that a copy was made when we did [:].)
                if newdm is not None:
                    newdm.close()
                    del newdm

    def get_wcs( self ):
        raise NotImplementedError( "WCS not yet implemented for RomanDatamodelL2Image" )
