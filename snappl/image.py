__all__ = [ 'Image', 'Numpy2DImage', 'FITSImage', 'FITSImageStdHeaders', 'CompressedFITSImage', 'FITSImageOnDisk',
            'OpenUniverse2024FITSImage', 'RomanDatamodelImage' ]

import re
import pathlib
import random
import simplejson

import numpy as np
import pandas
import fitsio
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

from snappl.logger import SNLogger
from snappl.config import Config
from snappl.wcs import BaseWCS, AstropyWCS, GalsimWCS, GWCS
from snappl.utils import asUUID, SNPITJsonEncoder
from snappl.provenance import Provenance
from snappl.dbclient import SNPITDBClient
from snappl.pathedobject import PathedObject


# ======================================================================
# The base class for all images.  This is not useful by itself, you need
#   to instantiate a subclass.  However, everything that you call on an
#   object you instantiate should have its interface defined in this
#   class.

class Image( PathedObject ):
    """Encapsulates a single 2d image.

    Properties inclue the following.  Some of these properties may not
    be defined for some subclasses of Image.

    If possible, avoid using all "path" properties, and instead use the
    other properties to get access to image data.  Note that "noisepath"
    and "flagspath" are not defined for all Image subclasses, and will
    only be defined sometimes for some subclasses (depending on how data
    is stored).

    * filepath : pathlib.Path ; path *relative to the base path* of the image file. This may just
                                have the image data itself, or it may be a *base* filepath, or it
                                may have everything, depending on the subclass.
                                If you can avoid using this property, do so.  Use .data, etc, instead.
    * filename : string ; just the name part of filepath (so if filepath is Path("/foo/bar"), name is "bar")
    * full_filepath : pathlib.Path ; absolute path to file on system.  (Same as base_path / filepath.)
    * base_path : base path for images; usually will be Config value system.paths.images
    * base_dir : synonym for base_path

    * path : pathlib.Path; absolute path to the image on disk, sort of, in a complicatd way.
             HERE FOR BACKWARDS COMPATIBILITY ONLY
    * name : str; synonym for filename.  HERE FOR BACKWARDS COMPATIBILITY ONLY.

    * pointing : int (str?); a unique identifier of the exposure associated with the image
    *            WARNING, this property name will probably change once we fighre out the
    *            right thing from the roman datamodel we want to use
    * sca : int (str?); the SCA of this image
    * ra: float; the nominal RA at the center of the image in decimal degrees, usu. from the header
    * dec: float; the nominal RA at the center of the image in decimal degrees, usu. from the header
    * ra_corner_00: float; decimal degrees, ra of pixel (0, 0)
    * ra_corner_10: float; decimal degrees, ra of pixel (width-1, 0)
    * ra_corner_01: float; decimal degrees, ra of pixel (0, height)
    * ra_corner_11: float; decimal degrees, ra of pixel (width-1, height-1)
    * dec_corner_00: float; decimal degrees, dec of pixel (0, 0)
    * dec_corner_10: float; decimal degrees, dec of pixel (width-1, 0)
    * dec_corner_01: float; decimal degrees, dec of pixel (0, height)
    * dec_corner_11: float; decimal degrees, dec of pixel (width-1, height-1)
    * band : str; filter
    * mjd : float; mjd of the start of the image
    * position_angle : float; position angle in degrees north of east (CHECK THIS)
    * exptime : float; exposure time in seconds
    * sky_level : float; an estimate of the sky level (in ADU) if known, None otherwise
    * zeropoint : float; convert to AB mag with -2.5*log(adu) + zeropoint, where adu is the units of data

    * width : the width (xorizontal size as viewed on ds9) of the image in pixels
    * height : the height (y/vertical size as viewed on ds9) of the image in pixels
    * image_shape : tuple (height, width) of ints; the image size
    * coord_center : tuple of (ra, dec) [I THINK] : center of the image calculated from the WCS

    * data : 2d numpy array; the data of this image
    * noise : 2d numpy array; a 1σ noise image (if defined)
    * flags : 2d numpy array of ints; a pixel flags image (if defined)

    IMPORTANT NOTE: because of how numpy arrays are indexed, if you want to get
    value of the pixel at (ix, iy), you would do image.data[iy, ix].

    For all implementations, the properties data, noise, and flags are
    lazy-loaded.  That is, they start empty, but when you access them,
    an internal buffer gets loaded with that data.  This means it can be
    very easy for lots of memory to get used without your realizing it.
    There are a couple of solutions.  The first, is to call Image.free()
    when you're sure you don't need the data any more, or if you know
    you want to get rid of it for a while and re-read it from disk
    later.  The second is just not to access the data, noise, and flags
    properties, instead use Image.get_data(), and manage the data object
    lifetime yourself.

    """

    # How close in degrees should the right- and up- calculated position angles match?
    _close_enough_position_angle = 3

    # This is just a conveneince varaible used by the vearious get_data methods
    data_array_list = [ 'all', 'data', 'noise', 'flags' ]

    # SEE THE VERY BOTTOM OF THIS FILE
    # There a class variable _format_def is defined that explains the "format" field
    #  in the l2images table in the database.  (It's defined at the bottom of the
    #  file so all the classes will be defined by the time we get there.)


    def __init__( self, path=None, filepath=None, base_path=None, base_dir=None,
                  full_filepath=None, no_base_path=False,
                  id=None, provenance_id=None, width=None, height=None,
                  pointing=None, sca=None, ra=None, dec=None,
                  ra_corner_00=None, ra_corner_01=None, ra_corner_10=None, ra_corner_11=None,
                  dec_corner_00=None, dec_corner_01=None, dec_corner_10=None, dec_corner_11=None,
                  band=None, mjd=None, position_angle=None, exptime=None, sky_level=None, zeropoint=None,
                  format=-1, is_superclass=False, **kwargs ):
        """Instantiate an image.  You probably don't want to do that.

        This is an abstract base class that has limited functionality.
        You probably want to instantiate a subclass if you're creating a
        new image.

        If you're trying to pull an image out of the database, then
        probably what you really want is to use the Image.get_image or
        Image.find_images class methods.

        If you're working with non-database images and are trying to get
        a pre-existing image, then probably what you really want to do
        is call the get_image() method of an ImageCollection object.

        Parameters
        ----------
          filepath : str or Path, default None
            Path of the image relative to the base path for images,
            unless less no_base_path is True, in which case this is the
            full absolute path to the image.  For datbase images, you do
            not want to create a path yourself, but leave it at None and
            let the class create the filepath.  See PathedObject.

          full_filepath : str or Path, default None
            The full path to the image.  If you're using an Image subclass
            to deal with an image that's not in the database, you probably
            want to set this to the absolute path of the image, and you
            probably want to set no_base_path to True, but you might also
            set base_path yourself and leave no_base_path at False.

          base_path : str or Path, default None
            Always leave this at None for images associated with
            database, and the default will be used.  Otherwise, the
            absolute path of the image is base_path / filepath (which
            should be exactly the same as full_filepath).  Must be None
            if no_base_path is True.

          base_dir : str or Path, default None
            Synonym for base_path

          no_base_path : bool, default False
            For images associated with the database, leave this at
            False, and make filepath relative to the base path (which
            may be system dependent).  For images that aren't associated
            with the database, you can make this True and set filepath
            to be just the path to the image.

          id : UUID or str that can be converted to UUID, default None
            Database ID of the image.  This is only relevant if the
            image is in the l2image table of the Roman SNPIT internal
            database (but is required in that case).

          provenance_id : UUID or str that can be converted to UUID, default NOne
            The id of the provenance of the image.  Only relevant if the
            image is in the l2image table of the Roman SNPIT internal
            database (but is required in that case).

          width, height: int, default None
            The width and height of the image in pixels if known.

          format : int, default -1
            Index into the table Image._format_def at the bottom of this file.

          pointing : int (str?), default None (WARNING: this parameter keyword will change)
          sca: int, default None
          ra: float, default None
          dec: float, default None
          (ra|dec)_corner_(00|01|10|11): float, default None
          band: str, default None
          mjd: float, default None
          position_angle: float, default None
          exptime: float, default None
          sky_level: float, default None
          zeropoint: float, default None
            All of these are the values that should be set for these
            properties (see Image class docstring).  If they are None,
            how they get populated depends on the image subclass.  In
            many cases, they will be lazy-loaded from the header.

        """
        if path is not None:
            if full_filepath is not None:
                # This next error message is a bit of a lie.  It's
                #   aspirational; use the real thing, not the backwards
                #   compatible thing.  But, existing code will use path, from
                #   before full_filepath was defined, and we want it to keep
                #   working.  If somebody uses both, then they're just wrong,
                #   so tell them to use the new thing.
                raise ValueError( "Do not use path, only use full_filepath." )
            full_filepath = path

        # This has to be set before superclass init because the
        #   PathedObject init will (indirectly) use it (by calling
        #   _set_base_path).
        self._format = format

        super().__init__( filepath=filepath, base_path=base_path, base_dir=base_dir,
                          full_filepath=full_filepath, no_base_path=no_base_path )

        self._declare_consumed_kwargs( { 'path', 'filepath', 'base_path', 'base_dir',
                                         'full_filepath', 'no_base_path',
                                         'id', 'provenance_id', 'width', 'height', 'pointing', 'sca', 'ra', 'dec',
                                         'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                                         'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                                         'band', 'mjd', 'position_nagle', 'exptime', 'sky_level', 'zeropoint' } )
        self._verify_all_consumed_kwargs( **kwargs )

        self._id = asUUID( id ) if id is not None else None
        self._provenance_id = asUUID( provenance_id ) if provenance_id is not None else None
        self._width = width
        self._height = height
        self._pointing = pointing
        self._sca = sca
        self._ra = ra
        self._dec = dec
        self._ra_corner_00 = ra_corner_00
        self._ra_corner_01 = ra_corner_01
        self._ra_corner_10 = ra_corner_10
        self._ra_corner_11 = ra_corner_11
        self._dec_corner_00 = dec_corner_00
        self._dec_corner_01 = dec_corner_01
        self._dec_corner_10 = dec_corner_10
        self._dec_corner_11 = dec_corner_11
        self._band = band
        self._mjd = mjd
        self._position_angle = position_angle
        self._exptime = exptime
        self._sky_level = sky_level
        self._zeropoint = zeropoint

        self._wcs = None      # a BaseWCS object (in wcs.py)
        self._is_cutout = False


    def _declare_consumed_kwargs( self, consumed_kwargs ):
        if hasattr( self, '_consumed_kwargs' ):
            overlaps = self._consumed_kwargs.intersection( consumed_kwargs )
            if len(overlaps) != 0:
                raise RuntimeError( f"Programming error in {self.__class__.__name__}: the following kwargs "
                                    f"are interpreted by more than one constructor in the inheritance chain: "
                                    f"{overlaps}" )
            self._consumed_kwargs = self._consumed_kwargs.union( consumed_kwargs )
        else:
            self._consumed_kwargs = consumed_kwargs.copy()

    def _verify_all_consumed_kwargs( self, **kwargs ):
        unconsumed = set( kwargs.keys() ) - self._consumed_kwargs
        if len(unconsumed) != 0:
            # Do we want this to be an exeption or just a warning?
            raise RuntimeError( f"{self.__class__.__name__} constructor didn't recognize "
                                f"keyword arguments: {unconsumed} " )
            # SCLogger.warning( f"{self.__class__.__name__} constructor didn't recognize "
            #                   f"keyword arguments: {unconsumed} " )



    _image_class_base_path_config_item = None


    def _set_base_path( self, base_path=None, no_base_path=False ):
        # This is unpleasant but the tortured logic is necessary to
        #  preserve backwards compatibility for Image with what we did
        #  in early 2025 with how things came in once we started
        #  defining the database in late 2025.
        if no_base_path:
            if base_path is not None:
                raise ValueError( "Cannot specify a base_path (or base_dir) if no_base_path is True." )
            self._no_base_path = no_base_path
            self._base_path = None

        else:
            if base_path is not None:
                self._no_base_path = False
                self._base_path = pathlib.Path( base_path ).resolve()

            else:
                if self._format not in Image._format_def:
                    raise ValueError( "Unknown image format {self._format}" )
                fmtbasepathdef = Image._format_def[ self._format ][ 'base_path_config' ]
                if fmtbasepathdef is None:
                    fmtbasepathdef = self._image_class_base_path_config_item

                if fmtbasepathdef is None:
                    self._no_base_path = True
                    self._base_path = None

                else:
                    self._no_base_path = False
                    self._base_path = pathlib.Path( Config.get().value( fmtbasepathdef ) ).resolve()


    # The path property is just for backwards compatibilty
    @property
    def path( self ):
        return self.full_filepath

    @path.setter
    def path( self, val ):
        raise RuntimeError( "You aren't supposed to set path.  If you really need to do this, talk to Rob "
                            "to find out what you should be doing instead.  It might be painful." )

    @property
    def name ( self ):
        return self.filename

    @property
    def id( self ):
        """The database image uuid in the l2image table."""
        return self._id

    @id.setter
    def id( self, new_value ):
        """USE THIS WITH CARE.  It doesn't change the database, only the object in memory.  You may become confused."""
        self._id = asUUID( new_value ) if new_value is not None else None

    @property
    def provenance_id( self ):
        """The database provenance uuid of the image in the l2image table."""
        return self._provenance_id

    @provenance_id.setter
    def provenance_id( self, new_value ):
        """USE THIS WITH CARE.  It doesn't change the database, only the object in memory.  You may become confused."""
        self._provenance_id = asUUID( new_value ) if new_value is not None else None


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
        return ( self.height, self.width )

    @property
    def width( self ):
        """Int: the width (x-size, second index in numpy arrays) of the image"""
        if self._width is None:
            self._get_image_shape()
        return self._width

    @property
    def height( self ):
        """Int: height (y-size, first index in numpy arrays) of the image"""
        if self._height is None:
            self._get_image_shape()
        return self._height

    @property
    def pointing( self ):
        """Str or int or something; the exposure/pointing/visit/SOMETHING for the image"""
        if self._pointing is None:
            self._get_pointing()
        return self._pointing

    @pointing.setter
    def pointing( self, val ):
        self._pointing = val

    @property
    def sca( self ):
        """Int; the chip of the image"""
        if self._sca is None:
            self._get_sca()
        return self._sca

    @sca.setter
    def sca( self, val ):
        self._sca = int( val ) if val is not None else None

    @property
    def ra( self ):
        """Float; decimal degrees; nominal RA of the image (probably from the header)"""
        if self._ra is None:
            self._get_ra_dec()
        return self._ra

    @ra.setter
    def ra( self, val ):
        self._ra = float( val ) if val is not None else None

    @property
    def dec( self ):
        """Float; decimal degrees; nominal dec of the image (probably from the header)"""
        if self._dec is None:
            self._get_ra_dec()
        return self._dec

    @dec.setter
    def dec( self, val ):
        self._dec = float( val ) if val is not None else None

    @property
    def ra_corner_00( self ):
        """Float; decimal degrees; tha RA of pixel (x=0, y=0)"""
        if self._ra_corner_00 is None:
            self._get_corners()
        return self._ra_corner_00

    @ra_corner_00.setter
    def ra_corner_00( self, val ):
        self._ra_corner_00 = float( val ) if val is not None else None

    @property
    def ra_corner_01( self ):
        """Float; decimal degrees; the RA of pixel (x=0, y=height-1)"""
        if self._ra_corner_01 is None:
            self._get_corners()
        return self._ra_corner_01

    @ra_corner_01.setter
    def ra_corner_01( self, val ):
        self._ra_corner_01 = float( val ) if val is not None else None

    @property
    def ra_corner_10( self ):
        """Float; decimal degrees; the RA of pixel (x=width-1, height=0)"""
        if self._ra_corner_10 is None:
            self._get_corners()
        return self._ra_corner_10

    @ra_corner_10.setter
    def ra_corner_10( self, val ):
        self._ra_corner_10 = float( val ) if val is not None else None

    @property
    def ra_corner_11( self ):
        """Float; decimal degrees; the RA of pixel (x=width-1, y=height=1)"""
        if self._ra_corner_11 is None:
            self._get_corners()
        return self._ra_corner_11

    @ra_corner_11.setter
    def ra_corner_11( self, val ):
        self._ra_corner_11 = float( val ) if val is not None else None

    @property
    def dec_corner_00( self ):
        """Float; decimal degrees; the dec of pixel (x=0, y=0)"""
        if self._dec_corner_00 is None:
            self._get_corners()
        return self._dec_corner_00

    @dec_corner_00.setter
    def dec_corner_00( self, val ):
        self._dec_corner_00 = float( val ) if val is not None else None

    @property
    def dec_corner_01( self ):
        """Float; decimal degrees; the dec of pixel (x=0, y=height-1)"""
        if self._dec_corner_01 is None:
            self._get_corners()
        return self._dec_corner_01

    @dec_corner_01.setter
    def dec_corner_01( self, val ):
        self._dec_corner_01 = float( val ) if val is not None else None

    @property
    def dec_corner_10( self ):
        """Float; decimal degrees; the dec of pixel (x=width-1, y=0)"""
        if self._dec_corner_10 is None:
            self._get_corners()
        return self._dec_corner_10

    @dec_corner_10.setter
    def dec_corner_10( self, val ):
        self._dec_corner_10 = float( val ) if val is not None else None

    @property
    def dec_corner_11( self ):
        """Float; decimal degrees; the dec of pixel (x=width-1, y=height-1)"""
        if self._dec_corner_11 is None:
            self._get_corners()
        return self._dec_corner_11

    @dec_corner_11.setter
    def dec_corner_11( self, val ):
        self._dec_corner_11 = float( val ) if val is not None else None

    @property
    def band( self ):
        """Band (str)"""
        if self._band is None:
            self._get_band()
        return self._band

    @band.setter
    def band( self, val ):
        self._band = str( val ) if val is not None else None

    @property
    def mjd( self ):
        """MJD of the start of the image (defined how? TAI?)"""
        if self._mjd is None:
            self._get_mjd()
        return self._mjd

    @mjd.setter
    def mjd( self, val ):
        self._mjd = float( val ) if val is not None else None

    @property
    def position_angle( self ):
        """Position angle in degrees north of east (CHECK THIS)"""
        if self._position_angle is None:
            self._get_position_angle()
        return self._position_angle

    @position_angle.setter
    def position_angle( self, val ):
        self._position_angle = float( val ) if val is not None else None

    @property
    def exptime( self ):
        """Exposure time in seconds."""
        if self._exptime is None:
            self._get_exptime()
        return self._exptime

    @exptime.setter
    def exptime( self, val ):
        self._exptime = float( val ) if val is not None else None

    @property
    def sky_level( self ):
        """Estimate of the sky level in ADU."""
        if self._sky_level is None:
            self._get_sky_level()
        return self._sky_level

    @sky_level.setter
    def sky_level( self, val ):
        self._sky_level = float( val ) if val is not None else None

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
        self._zeropoint = float( val ) if val is not None else None


    def _get_image_shape( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_image_shape" )

    def _get_pointing( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_pointing" )

    def _get_sca( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_sca" )

    def _get_ra_dec( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_ra_dec" )

    def _get_corners( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_corners" )

    def _get_band( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_band" )

    def _get_mjd( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_mjd" )

    def _get_exptime( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_exptime" )

    def _get_sky_level( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_sky_level" )

    def _get_zeropoint( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_zeropoint" )


    def _get_position_angle( self ):
        """Position angle in degrees north of east (CHECK THIS)"""
        wcs = self.get_wcs()
        ny, nx = self.image_shape
        midra, middec = wcs.pixel_to_world( nx/2., ny/2. )
        cosdec = np.cos( middec * np.pi / 180. )
        rightra, rightdec = wcs.pixel_to_world( nx/2.+1, ny/2. )
        drightra = ( rightra - midra ) * cosdec
        drightdec = rightdec - middec
        upra, updec = wcs.pixel_to_world( nx/2., ny/2.+1 )
        dupra = ( upra - midra ) * cosdec
        dupdec = updec - middec
        rightang = np.arctan2( -drightdec, drightra ) * 180. / np.pi
        upang = np.arctan2( dupra, dupdec ) * 180 / np.pi

        # Have to deal with the edge case where they are around ±180.
        if ( ( ( rightang > 0 ) != ( upang > 0 ) )
             and
             ( np.fabs( np.fabs(rightang) - 180. ) <= self._close_enough_position_angle )
             and
             ( np.fabs( np.fabs(upang) - 180. ) <= self._close_enough_position_angle )
            ):
            if rightang < 0:
                rightang += 360.
            if upang < 0:
                upang += 360.

        if np.abs( rightang - upang ) > self._close_enough_position_angle:
            raise ValueError( f"Calculated position angle of {rightang:.2f}° looking to the right "
                              f"and {upang:.2f}° looking up; these are inconsistent!" )
        self._position_angle = ( rightang + upang ) / 2.

        # Leftover from dealing with the RA~±180 edge case
        if self._position_angle > 180.:
            self._position_angle -= 360.

        return self._position_angle


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
            "strict" does not allow for partial overlap between the cutout and the original image,
            "partial" will fill in non-overlapping pixels with fill_value. This is identical to the
            mode parameter of astropy.nddata.Cutout2D.
        fill_value : float, default np.nan
            Fill value for pixels that are outside the original
            image when mode='partial'. This is identical to the fill_value parameter
            of astropy.nddata.Cutout2D.

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
            "strict" does not allow for partial overlap between the cutout and the original image,
            "partial" will fill in non-overlapping pixels with fill_value. This is identical to the
            mode parameter of astropy.nddata.Cutout2D.
        fill_value : float, default np.nan
            Fill value for pixels that are outside the original
            image when mode='partial'. This is identical to the fill_value parameter
            of astropy.nddata.Cutout2D.

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
        """Check to see if (ra, dec)  is included within the image borders.

        Parameters
        ---------
          ra, dec: float
            The coordinate in decimal degrees to check.

        Return
        ------
          True if (ra, dec) is within the image borders, False otherwise.
        """

        wcs = self.get_wcs()
        sc = SkyCoord( ra=ra * astropy.units.deg, dec=dec * astropy.units.deg )
        try:
            x, y = skycoord_to_pixel( sc, wcs.get_astropy_wcs() )
        except astropy.wcs.wcs.NoConvergence:
            return False
        # NOTE : we're assuming a full-size image here.  Think about cutouts!
        return ( x >= 0 ) and ( x < self.width ) and ( y >= 0 ) and ( y < self.height )


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

    def save_data( self, which='all', path=None, imagepath=None, noisepath=None, flagspath=None, overwrite=False ):
        """Same as save; here for backwards compatibility.  Use save."""
        self.save( which=which, path=path, noisepath=noisepath, flagspath=flagspath, overwrite=overwrite )


    def save( self, which='all', path=None, imagepath=None, noisepath=None, flagspath=None, overwrite=False ):
        """Save the image to its path(s).

        May have side-effects on the internal data structure (e.g. FITS
        subclasses modify the internally stored header).

        Paramters
        ---------
          which : str, default "all"
            One of 'data', 'noise', 'flags', or 'all'

          imagepath : str, default None
            Full Path to write the image to.  If not specified, will use use
            self.full_filepath.  Does NOT update any of the path properties of
            the image.  You can leave this at None, and the path that the
            Image figured out when it was constructed will be used.  Usually,
            that's what you should do.

          path : str, default None
            A synonym for imagepath.  Do not use.  Here for backwards
            compatibility.

          noisepath : str, default None
            Path to write the noise image to, if the noise image is stored as
            a separate image.  (It isn't always; some subclasses have it as a
            separate part of the data structure that also has the image.)  If
            None, use an internally stored noisepath.  If that is not set, and
            noisepath is None, and this isn't a subclass that combines all the
            data planes into one file, then any noise data array will not be
            written.  Usually, you don't want to have to specify this.

          flagspath : str, default None
            Path to write the flags image to, similar to noisepath.

          overwrite : bool, default False
            Clobber existing images?

        Not implemented for all subclasses.

        """
        raise NotImplementedError( f"{self.__class__.__name} doesn't implement save" )


    @classmethod
    def get_image( cls, image_id, dbclient=None ):
        """Get an Image from the database based on its image id.

        Parmameters
        -----------
          image_id : UUID or str that can be converted to UUID
            The ID of the image to get.

          dbclient : SNPITDBClient, default None
            The connection to the database.  If None, a new connection
            will be created based on what's it the config.

        """
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        row = dbclient.send( f"/getl2image/{image_id}" )

        if row['format'] not in Image._format_def:
            raise ValueError( f"Database {image_id} has format {row['format']}, which is unknown." )
        image_class = Image._format_def[ row['format'] ][ 'image_class' ]

        # Remove things the Image constroctor won't know
        del row['extension']
        del row['properties']
        return image_class( **row )

    @classmethod
    def find_images( cls, provenance=None, provenance_tag=None, process=None, dbclient=None, **kwargs ):
        """Search the database for images.

        Parameters
        ----------
          provenance : Provenance or UUID, default None
            Either provenance, or both of provenacne_tag and process,
            are required.  provenacne is the provenance of images to
            search.

          provenance_tag : string, default None
            The provenance tag to search.  Required if provenance is
            None.

          process : string, deafault None
            The process, used with provenance_tag, to find the
            provenance.  Required if provenacne_tag is not None.

          dbclient: SNPITDBClient, default None
            The connection to the database.  If None, a new connection
            will be created based on what's it the config.

          filepath: pathlib.Path or str, default None
            Path of the image (relative to the base path for all images) of
            the image to search for.  Usually if you feed it this, you don't
            want to feed it nay other parameters.

          mjd_min : float, default None
            Only return images at this mjd or later

          mjd_max : float, default None
            Only return images at this mjd or earlier.

          ra: float, default None
            Only return images that contain this ra

          dec: float, default None
            Only return images that containe this dec

          ra_min, ra_max, dec_min, dec_max : float, default None
            Only return images whose nominal central RA/dec are
            greater/lesser than the specified limits.

          band: str, default None
            Only include images from this band

          exptime_min: float, default None
            Only include images with at least this exptime in seconds.

          exptime_max: float, default None
            Only include images with at most this exptime in seconds.

          sca: int
            Only include images from this sca.

          order_by: str or list, default None
            By default, the returned images are not sorted in any
            particular way.  Put a keyword here to sort by that value
            (or by those values).  Options include 'id',
            'provenance_id', 'pointing', 'sca', 'ra', 'dec', 'filepath',
            'width', 'height', 'mjd', 'exptime'.  Not all of these are
            necessarily useful, and some of them may be null for many
            objects in the database.

          limit : int, default None
            Only return this many objects at most.

          offset : int, default None
            Useful with limit and order_by ; offset the returned value
            by this many entries.  You can make repeated calls to
            find_objects to get subsets of objects by passing the same
            order_by and limit, but different offsets each time, to
            slowly build up a list.

        Returns
        -------
          imagelist: list of snappl.image.Image
            Really it will be list of objects of a subclass of
            snappl.image.Image, but you shouldn't need to know that.

        """
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        kwargs = kwargs.copy()
        if provenance is not None:
            if isinstance( provenance, Provenance ):
                kwargs[ 'provenance' ] = provenance.id
            else:
                kwargs[ 'provenance' ] = asUUID( provenance )
        if provenance_tag is not None:
            if process is None:
                raise ValueError( "Must specify process with provenance_tag" )
            kwargs[ 'provenance_tag' ] = provenance_tag
            kwargs[ 'process' ] = process
        if ( 'provenance' in kwargs ) == ( 'provenance_tag' in kwargs ):
            raise ValueError( "Must specify either provenance, or both of provenance_tag and process; "
                              "cannot specify both provenance and provenance_tag" )

        # Find things

        rows = dbclient.send( "/findl2images",
                              data=simplejson.dumps( kwargs, cls=SNPITJsonEncoder ),
                              headers={'Content-Type': 'application/json'} )

        images = []
        for row in rows:
            if row['format'] not in Image._format_def:
                raise ValueError( f"Database image {row['id']} has format {row['format']}, which is unknown." )
            image_class = Image._format_def[ row['format'] ][ 'image_class' ]
            # Remove things the Image constructor won't know
            del row['extension']
            del row['properties']
            images.append( image_class( **row ) )

        return images


# ======================================================================
# Lots of classes will probably internally store all of data, noise, and
#   flags as 2d numpy arrays.  Common code for those classes is here.

class Numpy2DImage( Image ):
    """Abstract class for classes that store their array internall as a numpy 2d array."""

    def __init__( self, *args, data=None, noise=None, flags=None, **kwargs ):
        self._declare_consumed_kwargs( { 'data', 'noise', 'flags' } )
        super().__init__( *args, **kwargs )

        self._data = data
        self._noise = noise
        self._flags = flags

    @property
    def data( self ):
        if self._data is None:
            self._load_data( which='data' )
        return self._data

    @data.setter
    def data(self, new_value):
        if ( isinstance(new_value, np.ndarray)
             and np.issubdtype(new_value.dtype, np.floating)
             and len(new_value.shape) ==2
            ) or (new_value is None):
            self._data = new_value
        else:
            raise TypeError( "Data must be a 2d numpy array of floats." )

    @property
    def noise( self ):
        if self._noise is None:
            self._load_data( which='noise' )
        return self._noise

    @noise.setter
    def noise( self, new_value ):
        if (
            isinstance(new_value, np.ndarray)
            and np.issubdtype(new_value.dtype, np.floating)
            and len(new_value.shape) == 2
        ) or (new_value is None):
            self._noise = new_value
        else:
            raise TypeError( "Noise must be a 2d numpy array of floats." )

    @property
    def flags( self ):
        if self._flags is None:
            self._load_data( which='flags' )
        return self._flags

    @flags.setter
    def flags( self, new_value ):
        if (
            isinstance(new_value, np.ndarray)
            and np.issubdtype(new_value.dtype, np.integer)
            and len(new_value.shape) == 2
        ) or (new_value is None):
            self._flags = new_value
        else:
            raise TypeError( "Flags must be a 2d numpy array of integers." )


    def _get_image_shape( self ):
        """Subclasses probably want to override this!

        This implementation accesses the .data property, which will load the data
        from disk if it hasn't been already.  Actual images are likely to have
        that information availble in a manner that doesn't require loading all
        the image data (e.g. in a header), so subclasses should do that.

        """
        if ( self._width is None ) or ( self._height is None ):
            self._height, self._width = self.data.shape
        return ( self.height, self.width )

    def _load_data( self, which="all" ):
        """Loads (or reloads) the data from disk."""
        self.get_data( which=which, cache=True, always_reload=False )

    def free( self ):
        self._data = None
        self._noise = None
        self._flags = None


# ======================================================================
# A base class for FITSImages which use an AstropyWCS wcs.
#
# There are three basic models for how the FITS image is stored on disk:
#
# (1) Multiple HDUs in one file
#
#     In this case, filepath holds the path to the file (full_filepath for the
#     full location), and imagehdu, nosiehdu, and flagshdu hold the index of
#     the hdu that has the respective data array.  noisepath and flagspath are
#     None.  If you get the FITS header, you get the header associated with
#     the imagehdu... which might not be what you want, but oh well.
#
# (2) Three separate files
#
#     In thise case, imagepath, noisepath, and flagspath properties are the
#     full absolute paths to the image data, noise data, and dq flags
#     respectively.  Usually, though not necessarily, all of imagehdu,
#     noisehdu, and flagshdu will be 0, since we are dealing with single-hdu
#     files.  The filepath property holds *something* relative to the base
#     path, depending on details, but it might be the image data.  If you
#     get the header, you get the image file's header.
#
# (3) One file with just data
#     There is no noise or flags, just data.
#
# If constructed with std_imagenames=True, then this assumes model (2), and
#   full_filepath should be a _base_ name; the data is in
#   {full_filepath}_image.fits, the noise in {full_filepath}_noise.fits, and
#   the flags in {full_filepath}_flags.fits.

class FITSImage( Numpy2DImage ):
    """Base class for classes that read FITS images and uses an AstropyWCS wcs.

    Properties imagepath, noisepath, and flagspath are full paths to where
    those files actually live on disk.  Generally, they should only be used
    internally.

    """

    def __init__( self, *args, noisepath=None, flagspath=None,
                  imagehdu=0, noisehdu=0, flagshdu=0, header=None, wcs=None,
                  std_imagenames=False, **kwargs ):
        self._declare_consumed_kwargs( { 'noisepath', 'flagspath', 'imagehdu', 'noisehdu', 'flagshdu',
                                         'header', 'wcs', 'std_imagenames' } )
        super().__init__( *args, **kwargs )

        if ( header is not None ) and ( not isinstance( header, astropy.io.fits.header.Header ) ):
            raise TypeError( f"header must be an astropy.io.fits.header.Header, not a {type(header)}" )
        self._header = header

        if ( wcs is not None ) and ( not isinstance( wcs, BaseWCS ) ):
            raise TypeError( f"wcs must be an instance of a subclass of snappl.wcs.BaseWCS, "
                             f"not a {type(wcs)}" )
        self._wcs = wcs

        self._std_imagenames = std_imagenames
        if std_imagenames:
            if any( i != 0 for i in ( imagehdu, noisehdu, flagshdu ) ):
                raise ValueError( "std_imagenames requireds (image|noise|flags)hdu = 0" )
            if ( noisepath is not None ) or ( flagspath is not None ):
                raise ValueError( "std_imagenames can't be passed with noisepath or flagspath" )

            self.imagehdu = 0
            self.noisehdu = 0
            self.flagshdu = 0

        else:
            self._noisepath = pathlib.Path( noisepath ) if noisepath is not None else self.imagepath
            self._flagspath = pathlib.Path( flagspath ) if flagspath is not None else self.imagepath
            self.imagehdu = imagehdu
            self.noisehdu = noisehdu
            self.flagshdu = flagshdu

    @property
    def path( self ):
        return self.imagepath


    @property
    def imagepath( self ):
        if self._std_imagenames:
            return self.full_filepath.parent / f"{self.full_filepath.name}_image.fits"
        else:
            return self.full_filepath

    @imagepath.setter
    def imagepath( self, val ):
        if self._std_imagenames:
            val = str( val )
            if val[-11:] != '_image.fits':
                raise ValueError( f"Invalid imagepath {val}" )
            if self._no_base_path:
                self.filepath = val[:-11]
                return
            val = pathlib.Path( val[:-11] )
        else:
            val = pathlib.Path( val )

        if self._no_base_path:
            relpath = val
        else:
            try:
                relpath = val.relative_to( self.base_path )
            except ValueError:
                raise ValueError( f"Invalid imagepath {val}, it's underneath {self.base_path}" )

        self.filepath = relpath

    @property
    def noisepath( self ):
        if self._std_imagenames:
            return self.full_filepath.parent / f"{self.full_filepath.name}_noise.fits"
        else:
            return self._noisepath

    @noisepath.setter
    def noisepath( self, val ):
        if self._std_imagenames:
            raise RuntimeError( "Can't set nosiepath for a std_imagenames FITSImage." )
        self._noisepath = pathlib.Path( val )

    @property
    def flagspath( self ):
        if self._std_imagenames:
            return self.full_filepath.parent / f"{self.full_filepath.name}_flags.fits"
        else:
            return self._flagspath

    @flagspath.setter
    def flagspath( self, val ):
        if self._std_imagenames:
            raise RuntimeError( "Can't set flagspath for a std_imagenames FITSImage." )
        self._flagspath = pathlib.Path( val )


    @classmethod
    def _fitsio_header_to_astropy_header( cls, hdr ):
        # I'm agog that astropy.io.fits.Header can't just take a fitsio HEADER
        #   as a constructor argument, but there you have it.

        if not isinstance( hdr, fitsio.header.FITSHDR ):
            raise TypeError( "_fitsio_header_to_astropy_header expects a fitsio.header.FITSHDR" )

        ahdr = fits.Header()
        for rec in hdr.records():
            if 'comment' in rec:
                ahdr[ rec['name'] ] = ( rec['value'], rec['comment'] )
            else:
                ahdr[ rec['name'] ] = rec['value']

        return ahdr


    @classmethod
    def _astropy_header_to_fitsio_header( cls, ahdr ):
        if not isinstance( ahdr, astropy.io.fits.header.Header ):
            raise TypeError( "_astropy_header_to_fitsio_header expects a astrop.io.fits.header.Header" )

        hdr = fitsio.header.FITSHDR()
        for i, kw in enumerate( ahdr ):
            rec = { 'name': kw, 'value': ahdr[i] }
            if len( ahdr.comments[i] ) > 0:
                rec['comment'] = ahdr.comments[i]
            hdr.add_record( rec )

        return hdr


    def _get_image_shape(self):
        """tuple: (ny, nx) shape of image"""

        if not self._is_cutout:
            hdr = self.get_fits_header()
            self._width = hdr[ 'NAXIS1' ]
            self._height = hdr[ 'NAXIS2' ]
        else:
            self._height, self._width = self.data.shape

        return ( self._height, self._width )

    def set_fits_header( self, hdr ):
        if not isinstance( hdr, fits.Header ) and hdr is not None:
            raise TypeError( "FITS header must be an astropy.fits.io.header.Header" )
        self._header = hdr

    # Subclasses may want to replace this with something different based on how they work
    def get_fits_header( self ):
        """Get the header of the image.

        Note that FITSImage and subclasses set self._header here, inside get_fits_header.
        """
        if self._header is None:
            with fitsio.FITS( self.imagepath ) as f:
                hdr = f[ self.imagehdu ].read_header()
                self._header = FITSImage._fitsio_header_to_astropy_header( hdr )
        return self._header


    def _strip_wcs_header_keywords( self ):
        """Try to strip all wcs keywords from self._header.

        Useful as a pre-step for saving the image if you want to write
        the WCS to the image.  Using this makes sure (as best possible)
        that you don't end up with conflicting WCS keywords in the
        header.

        This may not be complete, as it pattern matches expected keywords.
        If it's missing some patterns, those won't get stripped.

        """

        self.get_fits_header()

        basematch = re.compile( r"^C(RVAL|RPIX|UNIT|DELT|TYPE)[12]$" )
        cdmatch = re.compile( r"^CD[12]_[12]$" )
        sipmatch = re.compile( r"^[AB]P?_(ORDER|(\d+)_(\d+))$" )
        tpvmatch = re.compile( r"^P[CV]\d+_\d+$" )

        tonuke = set()
        for kw in self._header.keys():
            if ( basematch.search(kw) or cdmatch.search(kw) or sipmatch.search(kw) or tpvmatch.search(kw) ):
                tonuke.add( kw )

        for kw in tonuke:
            del self._header[kw]


    def get_wcs( self, wcsclass=None ):
        wcsclass = "AstropyWCS" if wcsclass is None else wcsclass

        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "AstropyWCS":
                hdr = self.get_fits_header()
                self._wcs = AstropyWCS.from_header( hdr )
            elif wcsclass == "GalsimWCS":
                hdr = self.get_fits_header()
                self._wcs = GalsimWCS.from_header( hdr )
            else:
                raise TypeError( f"{self.__class__.__name__} doesn't know how to get a WCS of type {wcsclass}" )

        return self._wcs

    def get_data( self, which="all", always_reload=False, cache=False ):
        """As a side effect, also loads the image header if image data is loaded if cache is True."""

        if self._is_cutout:
            raise RuntimeError(
                "get_data called on a cutout image, this will return the ORIGINAL UNCUT image. Currently not supported."
            )

        if which not in Image.data_array_list:
            raise ValueError(f"Unknown which {which}, must be all, data, noise, or flags")
        which = [ 'data', 'noise', 'flags' ] if which == 'all' else [ which ]

        pathmap = { 'data': self.imagepath,
                    'noise': self.noisepath,
                    'flags': self.flagspath }
        hdumap = { 'data': self.imagehdu,
                   'noise': self.noisehdu,
                   'flags': self.flagshdu }

        rval = []
        for plane in which:
            prop = f'_{plane}'
            data = getattr( self, prop )
            if always_reload or ( data is None ):
                with fitsio.FITS( pathmap[plane] ) as f:
                    data = f[ hdumap[plane] ].read()
                    if cache:
                        setattr( self, prop, data )
                        if plane == 'data':
                            hdr = f[ hdumap[plane] ].read_header()
                            self._header = FITSImage._fitsio_header_to_astropy_header( hdr )
            rval.append( data )

        return rval


    def get_cutout(self, x, y, xsize, ysize=None, mode='strict', fill_value=np.nan):
        """See Image.get_cutout

        The mode and fill_value parameters are passed directly to astropy.nddata.Cutout2D for FITSImage.
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

        snappl_cutout = self.__class__(full_filepath=self.full_filepath, no_base_path=True, width=xsize, height=ysize)
        snappl_cutout._data = astropy_cutout.data
        snappl_cutout._wcs = None if wcs is None else AstropyWCS( astropy_cutout.wcs )
        snappl_cutout._noise = astropy_noise.data
        snappl_cutout._flags = astropy_flags.data
        snappl_cutout._is_cutout = True

        return snappl_cutout

    def get_ra_dec_cutout(self, ra, dec, xsize, ysize=None, mode='strict', fill_value=np.nan):
        """See Image.get_ra_dec_cutout

        The mode and fill_value parameters are passed directly to astropy.nddata.Cutout2D for FITSImage.
        """

        wcs = self.get_wcs()
        x, y = wcs.world_to_pixel( ra, dec )
        x = int( np.floor( x + 0.5 ) )
        y = int( np.floor( y + 0.5 ) )
        return self.get_cutout( x, y, xsize, ysize, mode=mode, fill_value=fill_value )

    def save( self, which='all', path=None, imagepath=None, noisepath=None, flagspath=None,
              imagehdu=None, noisehdu=None, flagshdu=None, overwrite=False ):
        """Write image to its path.  See Image.save

        Has the side-effect of loading self._header if it is None, and
        if replacing WCS keywords in self._header with keywords from the
        current image WCS.

        Currently does not support saving multi-HDU files.  (It will throw an
        exception if any of imagehdu, noisehdu, or flagshdu aren't 0.)

        """

        if ( imagepath is not None ) and ( path is not None ) and ( imagepath != path ):
            raise ValueError( "Only specify one of imagepath or path, they mean the same thing." )
        imagepath = imagepath if imagepath is not None else path

        saveim = ( which == 'data' ) or ( which == 'all' )
        saveno = ( which == 'noise' ) or ( which == 'all' )
        savefl = ( which == 'flags' ) or ( which == 'all' )

        imagehdu = imagehdu if imagehdu is not None else self.imagehdu
        noisehdu = noisehdu if noisehdu is not None else self.noisehdu
        flagshdu = flagshdu if flagshdu is not None else self.flagshdu

        if ( imagehdu != 0 ) or ( noisehdu != 0 ) or ( flagshdu != 0 ):
            raise NotImplementedError( "We need to implement saving to HDUs other than 0." )

        imagepath = imagepath if imagepath is not None else self.imagepath
        if saveim and ( imagepath is None ):
            raise RuntimeError( "Can't save data, no path." )
        noisepath = noisepath if noisepath is not None else self.noisepath
        if saveno and ( noisepath is None ):
            raise RuntimeError( "Can't save noise, no path." )
        flagspath = flagspath if flagspath is not None else self.flagspath
        if savefl and ( flagspath is None ):
            raise RuntimeError( "Can't save flags, no path." )

        if not all( ( p is None ) or ( p.name[-5:] == '.fits' ) for p in [ imagepath, noisepath, flagspath ] ):
            raise NotImplementedError( "I don't know how to save compressed files, only files "
                                       "whose names end in .fits" )

        if not overwrite:
            if ( imagepath.exists() or
                 ( noisepath is not None and noisepath.exists() ) or
                 ( flagspath is not None and flagspath.exists() ) ):
                raise RuntimeError( "FITSImage.save: overwrite is False, but image file(s) already exist" )
        else:
            if imagepath.is_file():
                imagepath.unlink()
            if ( noisepath is not None ) and ( noisepath.is_file() ):
                noisepath.unlink()
            if ( flagspath is not None ) and ( flagspath.is_file() ):
                flagspath.unlink()

        # Make sure header is loaded
        self.get_fits_header()
        try:
            apwcs = self.get_wcs().get_astropy_wcs( readonly=True )
            wcshdr = apwcs.to_header()
            self._strip_wcs_header_keywords()
            self._header.extend( wcshdr )
        except Exception:
            wcshdr = None

        with fitsio.FITS( imagepath, 'rw' ) as f:
            f.write( self.data, header=FITSImage._astropy_header_to_fitsio_header( self._header ) )
        if ( noisepath is not None ) and ( self.noise is not None ):
            with fitsio.FITS( noisepath, 'rw' ) as f:
                f.write( self.noise, header=FITSImage._astropy_header_to_fitsio_header( wcshdr ) )
        if ( self.flagspath is not None ) and ( self.flags is not None ):
            with fitsio.FITS( flagspath, 'rw' ) as f:
                f.write( self.flags, header=FITSImage._astropy_header_to_fitsio_header( wcshdr ) )


# ======================================================================
# FITSImageStdHeaders
#
# A FITSImage that knows it has information in header keywords
#   that can be configurated at instantiation time.

class FITSImageStdHeaders( FITSImage ):
    """A FITS Image that has standardized header keywords corresponding to the properties defined in Image.

    Setting a property also updates the internally stored header.

    """
    def __init__( self, *args,
                  header_kws = {
                      'pointing': "POINTING",
                      'sca': "SCA",
                      'ra': "RA",
                      'dec': "DEC",
                      'band': "BAND",
                      'mjd': "MJD",
                      'position_angle': "POSANG",
                      'exptime': "EXPTIME",
                      'sky_level': "SKYLEVEL",
                      'zeropoint': "ZPT" },
                  **kwargs ):
        self._declare_consumed_kwargs( { 'header_kws' } )
        super().__init__( *args, **kwargs )
        self._header_kws = header_kws



    def get_fits_header( self ):
        """This particular subclass will return an empty header if it can't read it for the image."""
        if self._header is None:
            try:
                self._header = FITSImage.get_fits_header( self )
            except Exception:
                self._header = fits.header.Header()
        return self._header


    # We're going to override many the property access methods so that
    #   we can update the header in the setters.
    # Sadly, it seems that in python if you want to override either
    #   the property or the setter, you have to override both, you
    #   can't take the parent class implementation for just one.

    def _get_pointing( self ):
        hdr = self.get_fits_header()
        self._pointing = hdr[ self._header_kws['pointing'] ]

    @property
    def pointing( self ):
        if self._pointing is None:
            self._get_pointing()
        return self._pointing

    @pointing.setter
    def pointing( self, val ):
        self._pointing = val
        hdr = self.get_fits_header()
        hdr[ self._header_kws['pointing'] ] = self._pointing

    def _get_sca( self ):
        hdr = self.get_fits_header()
        self._sca = int( hdr[ self._header_kws['sca'] ] )

    @property
    def sca( self ):
        if self._sca is None:
            self._get_sca()
        return self._sca

    @sca.setter
    def sca( self, val ):
        self._sca = int( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['sca'] ] = self._sca

    def _get_ra_dec( self ):
        hdr = self.get_fits_header()
        self._ra = float( hdr[ self._header_kws['ra'] ] )
        self._dec = float( hdr[ self._header_kws['dec'] ] )

    @property
    def ra( self ):
        if self._ra is None:
            self._get_ra_dec()
        return self._ra

    @ra.setter
    def ra( self, val ):
        self._ra = float( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['ra'] ] = self._ra

    @property
    def dec( self ):
        if self._dec is None:
            self._get_ra_dec()
        return self._dec

    @dec.setter
    def dec( self, val ):
        self._dec = float( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['dec'] ] = self._dec


    def _get_band( self ):
        hdr = self.get_fits_header()
        self._band = str( hdr[ self._header_kws['band'] ] )

    @property
    def band( self ):
        if self._band is None:
            self._get_band()
        return self._band

    @band.setter
    def band( self, val ):
        self._band = str( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['band'] ] = self._band


    def _get_mjd( self ):
        hdr = self.get_fits_header()
        self._mjd = float( hdr[ self._header_kws['mjd'] ] )

    @property
    def mjd( self ):
        if self._mjd is None:
            self._get_mjd()
        return self._mjd

    @mjd.setter
    def mjd( self, val ):
        self._mjd = float( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['mjd'] ] = self._mjd

    def _get_position_angle( self ):
        hdr = self.get_fits_header()
        if self._hdr_kws['position_angle'] in hdr:
            self._position_angle = float( hdr[ self._header_kws['positon_angle'] ] )
        else:
            super()._get_position_angle()

        return self._position_angle

    @property
    def position_angle( self ):
        if self._position_angle is None:
            self._get_position_angle()
        return self._position_angle

    @position_angle.setter
    def position_angle( self, val ):
        self._position_angle = float( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['position_angle'] ] = self._position_angle

    def _get_exptime( self ):
        hdr = self.get_fits_header()
        self._exptime = float( hdr[ self._header_kws['exptime'] ] )

    @property
    def exptime( self ):
        if self._exptime is None:
            self._get_exptime()
        return self._exptime

    @exptime.setter
    def exptime( self, val ):
        self._exptime = float( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['exptime'] ] = self._exptime

    def _get_sky_level( self ):
        hdr = set.get_fits_header()
        self._sky_level = float( hdr[ self._header_kws['sky_level'] ] )

    @property
    def sky_level( self ):
        if self._sky_level is None:
            self._get_sky_level()
        return self._sky_level

    @sky_level.setter
    def sky_level( self, val ):
        self._sky_level = float( val ) if val is not None else None
        hdr = self.get_fits_header()
        hdr[ self._header_kws['sky_level'] ] = self._sky_level

    def _get_zeropoint( self ):
        hdr = self.get_fits_header()
        self._zeropoint = float( hdr[ self._header_kws['zeropoint'] ] )

    @property
    def zeropoint( self ):
        if self._zeropoint is None:
            self._get_zeropoint()
        return self._zeropoint

    @zeropoint.setter
    def zeropoint( self, val ):
        self._zeropoint = float( val ) if val is not None else None



# =====================================================================
# A FITS Image that might be compressed (.gz or .bz2, not supporting fpack).

class CompressedFITSImage( FITSImage ):
    """An Image which is may correspond to a compressed file on disk (gz or bz2, not yet supporting fpack).

    It *should* be safe to use this anywhere you use a FITSImage.
    What's different about this is that it has the function
    ``uncompressed_version()`` that will create a file in some temp
    directory somewhere that is uncompressed (in case the file needs to
    be passed to something that can't handle compressed images.

    If you don't need to do that, it turns out that FITSImage supports any
    compressed image format that fitsio supports, so just use that class
    instead of this one.

    """

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )


    def uncompressed_version( self, include=[ 'data', 'noise', 'flags' ], temp_dir=None ):
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

          temp_dir : pathlib.Path, default None
            The path to write the files.  Defaults to the config value system.temp_dir

        Returns
        -------
          FITSImageOnDisk
            The path, noisepath, and flagspath properties will be set
            with the random filenames to which the FITS files were written.

        """
        if all( [ ( ( self.imagepath is None ) or ( self.imagepath.name[-5:] == '.fits' ) ),
                  ( ( self.noisepath is None ) or ( self.noisepath.name[-5:] == '.fits' ) ),
                  ( ( self.flagspath is None ) or ( self.flagspath.name[-5:] == '.fits' ) ) ] ):
            return self

        temp_dir = pathlib.Path( temp_dir if temp_dir is not None
                                 else Config.get().value( 'system.temp_dir' ) )
        barf = "".join( random.choices( '0123456789abcdef', k=10 ) )
        impath = None
        noisepath = None
        flagspath = None
        header = self.get_fits_header()

        if 'data' in include:
            hdul = fits.HDUList( [ fits.PrimaryHDU( data=self.data, header=header ) ] )
            impath = ( temp_dir / f"{barf}_image.fits" ).resolve()
            hdul.writeto( impath  )

        if 'noise' in include:
            hdul = fits.HDUList( [ fits.PrimaryHDU( data=self.noise, header=fits.header.Header() ) ] )
            noisepath = ( temp_dir / f"{barf}_noise.fits" ).resolve()
            hdul.writeto( noisepath )

        if 'flags' in include:
            hdul = fits.HDUList( [ fits.PrimaryHDU( data=self.flags, header=fits.header.Header() ) ] )
            flagspath = ( temp_dir / f"{barf}_flags.fits" ).resolve()
            hdul.writeto( flagspath )

        return CompressedFITSImage( no_base_dir=True, full_filepath=impath, noisepath=noisepath, flagspath=flagspath )


# ======================================================================
# This was the previous name for CompressedFITSImage.
# It was a terrible name.  It's here for backwards compatibilty.
#

class FITSImageOnDisk( CompressedFITSImage ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )


# ======================================================================
# OpenUniverse 2024 Images are gzipped FITS files
#  HDU 0 : (something, no data)
#  HDU 1 : SCI (32-bit float)
#  HDU 2 : ERR (32-bit float)
#  HDU 3 : DQ (32-bit integer)

class OpenUniverse2024FITSImage( CompressedFITSImage ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, imagehdu=1, noisehdu=2, flagshdu=3, **kwargs )

    _image_class_base_path_config_item = 'system.ou24.images'

    _filenamere = re.compile( r'^Roman_TDS_simple_model_(?P<band>[^_]+)_(?P<pointing>\d+)_(?P<sca>\d+).fits' )

    @property
    def truthpath( self ):
        """Path to truth catalog.  WARNING: this is OpenUniverse2024FITSImage-specific, use with care."""
        tds_base = pathlib.Path( Config.get().value( 'system.ou24.tds_base' ) )
        return ( tds_base / f'truth/{self.band}/{self.pointing}/'
                 f'Roman_TDS_index_{self.band}_{self.pointing}_{self.sca}.txt' )


    def _get_image_shape( self ):
        header = self.get_fits_header()
        self._width = int( header['NAXIS1'] )
        self._height = int( header['NAXIS2'] )

    def _get_pointing( self ):
        # Irritatingly, the pointing is not in the header.  So, we have to
        #   parse the filename to get the pointing.
        mat = self._filenamere.search( self.filepath.name )
        if mat is None:
            raise ValueError( f"Failed to parse {self.filepath.name} for pointing" )
        self._pointing = int( mat.group( 'pointing' ) )

    def _get_sca( self ):
        header = self.get_fits_header()
        self._sca = int( header['SCA_NUM'] )

    def _get_ra_dec( self ):
        header = self.get_fits_header()
        self._ra = float( header['RA_TARG'] )
        self._dec = float( header['DEC_TARG'] )

    def _get_corners( self ):
        ny, nx = self.image_shape
        wcs = self.get_wcs()
        self._ra_corner_00, self._dec_corner_00 = wcs.pixel_to_world( 0, 0 )
        self._ra_corner_01, self._dec_corner_01 = wcs.pixel_to_world( 0, ny-1 )
        self._ra_corner_10, self._dec_corner_10 = wcs.pixel_to_world( nx-1, 0 )
        self._ra_corner_11, self._dec_corner_11 = wcs.pixel_to_world( nx-1, ny-1 )

    def _get_band( self ):
        header = self.get_fits_header()
        self._band = header['FILTER'].strip()

    def _get_mjd( self ):
        header = self.get_fits_header()
        self._mjd =  float( header['MJD-OBS'] )

    def _get_exptime( self ):
        header = self.get_fits_header()
        if 'EXPTIME' in header:
            self._exptime = float( header['EXPTIME'] )
        else:
            exptimes = {'F184': 901.175,
                        'J129': 302.275,
                        'H158': 302.275,
                        'K213': 901.175,
                        'R062': 161.025,
                        'Y106': 302.275,
                        'Z087': 101.7 }
            if self.band not in exptimes:
                raise ValueError( f"Can't find exptime for band {self.band}" )
            self._exptime = exptimes[ self.band ]

    def _get_sky_level( self ):
        header = self.get_fits_header()
        self._sky_level = header['SKY_MEAN']

    def _get_zeropoint( self ):
        header = self.get_fits_header()
        self._zeropoint = galsim.roman.getBandpasses()[self.band].zeropoint + header['ZPTMAG']

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

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self._dm = None


    # TODO : many of the _get_* functions still need to be implemented for RomanDatamodelImage !

    def _get_sca( self ):
        match = self._detectormatch.search( self.dm.meta.instrument.detector )
        if match is None:
            raise ValueError( f'Failed to parse self._dm.meta.instrument.detector= '
                              f'"{self._dm.meta.instrument.detector} for "WFInn"' )
        self._sca = int( match.group(1) )


    def _get_image_shape( self ):
        # TODO : this must be in the header / meta information somewhere
        self._height, self._width = self.data.shape

    def _get_band( self ):
        self._band = self.dm.meta.instrument.optical_element

    def _get_mjd( self ):
        self._mjd = self.dm.meta.exposure.mid_time.mjd

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

        # We really want to open the image readonly, because otherwise normal use of
        #   this class will modify the image on disk.  We really don't want to modify
        #   our input data, and want to be explicit about saving like we are used
        #   to with FITS files.
        if self._dm is None:
            self._dm = rdm.open( self.full_filepath, mode='r' )
        return self._dm

    def get_wcs( self, wcsclass=None ):
        wcsclass = "GWCS" if wcsclass is None else wcsclass
        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "GWCS":
                self._wcs = GWCS( gwcs=self.dm.meta.wcs )
            else:
                raise NotImplementedError( "RomanDataModelImage can't (yet?) get a WCS of type {wcsclass}" )
        return self._wcs


# ======================================================================
# This dictionary defines the format field in the database.  The key is the format
#   integer, the value gives the image class, the base path config value, and eventually
#    maybe other information

Image._format_def = { -1 : { 'description': "Not a database image",
                             'image_class': None,
                             'base_path_config': None
                            },
                      0 : { 'description': "Unknown",
                            'image_class': Image,
                            'base_path_config': None
                           },
                      1 : { 'description': "OU2024 FITS Image in standard database location",
                            'image_class': OpenUniverse2024FITSImage,
                            'base_path_config': 'system.paths.images'
                           },
                      2: { 'description': "OU2024 FITS Image at the native OU2024 location",
                           'image_class': OpenUniverse2024FITSImage,
                           'base_path_config': 'system.ou24.images'
                          },
                      100: { 'description': "Basic Roman Data Model Image at standard database location",
                             'image_class': RomanDatamodelImage,
                             'base_path_config': 'system.paths.images'
                            },
                     }
