__all__ = [ 'Image', 'Numpy2DImage', 'FITSImage', 'FITSImageStdHeaders', 'CompressedFITSImage', 'FITSImageOnDisk',
            'OpenUniverse2024FITSImage', 'RomanDatamodelImage', 'RomanDatamodelImage_Needs_CRDS_GWCS' ]

import re
import pathlib
import random
import simplejson
from contextlib import contextmanager

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
import crds

from snappl.logger import SNLogger
from snappl.config import Config
from snappl.wcs import BaseWCS, AstropyWCS, GalsimWCS, RDM_GWCS, RDM_CRDS_GWCS
from snappl.utils import asUUID, SNPITJsonEncoder, isSequence
from snappl.provenance import Provenance
from snappl.dbclient import SNPITDBClient
from snappl.pathedobject import PathedObject


class _UnsetProperty:
    """Used internally, ignore."""
    pass


# ======================================================================
# The base class for all images.  This is not useful by itself, you need
#   to instantiate a subclass.  However, everything that you call on an
#   object you instantiate should have its interface defined in this
#   class.

class Image( PathedObject ):
    """Encapsulates a single 2d image.

    Properties inclue the following.  Some of these properties may not
    be defined for some subclasses of Image.

    DATA PROPERTIES

    * data : 2d numpy array; the data of this image
    * noise : 2d numpy array; a 1σ noise image (if defined)
    * flags : 2d numpy array of ints; a pixel flags image (if defined)

    For all implementations, the properties data, noise, and flags are
    lazy-loaded.  That is, they start as None, but when you access them,
    an internal buffer gets loaded with that data.  (Depending on the
    subclass, accessing any one of these properties may load others into
    memory.  For instance, using RomanDatamodelImage, the first time you
    access either .data or .noise, both get loaded into memory.)  This
    means it can be very easy for lots of memory to get used without
    your realizing it.  There are a couple of solutions.  The first, is
    to call Image.free() when you're sure you don't need the data any
    more, or if you know you want to get rid of it for a while and
    re-read it from disk later.  The second is just not to access the
    data, noise, and flags properties, instead use Image.get_data(), and
    manage the data object lifetime yourself.

    Image arrays are indexed by [y, x], with 0 being the center of the
    lower-left pixel.  That is, .data[0, 0] gives you the lower-left
    pixel.  .data[0, 1] gives you the pixel one to the right of the
    lower-left pixel.  .data[1, 0] gives you the pixel one above the
    lower-left pixel.  .data[height-1, width-1] gives you the
    upper-right pixel.  THESE POSITIONS ARE OFFSET BY 1 FROM WHAT YOU
    SEE IN DS9, so be careful.  They are also offset by 1 from a WCS in
    a FITS image header.  However, they ARE the coordinates you expect
    when using an astropy WCS class the right way, and, more
    importantly, are the coordiantes you expect when using a snappl WCS
    class.

    When considering positions on the image, as opposed to indexes in
    the array, the .0 position is the *center* of the pixel.  This is an
    unfortunate convention (talk to Rob if you want to know why it's
    unfortunate), but it's what astronomers have been using for decades,
    so we're stuck with it.  For a long discussion about indexing
    images, see the docstring on psf.py::PSF.get_stamp.

    UNITS OF THE DATA: we define the DAV "data array value" as the units
    of these arrays.  The literal definition of this is "the units of
    whatever it is you get when you access the .data property of a
    snappl.Image object".  However, there is a further definition for
    the Image class, and that is that DAV are NOT a surface brightness
    unit, but something (in the ideal case) proportional to the number
    of photons that came from the angular area on the sky subtended by
    the pixel during the exposure.  This is explored further in the
    zeropoint docstring below.  This means that a properly-implemented
    Image subclass may need to do a conversion to the actual data stored
    on disk in the file it refers to before giving you the .data and
    .noise properties (which the RomanDatamodelImage subclass does).  We
    use DAV because did not want to use DN or ADU or anything that had
    ever been used before; empirically, that caused discussion about DN
    vs. DN/sec, which got in the way of just trying to talk about the
    data array.

    IMMEDIATE IMAGE METADATA PROPERTIES

    * width : the width (horizontal size as viewed on ds9) of the image in pixels
    * height : the height (vertial size as viewed on ds9) of the image in pixels
    * image_shape : tuple of ints, giving (height, width)

    LESS IMMEDIATE IMAGE METADATA PROPERTIES

    coord_center : tuple of (ra, dec) [I THINK] : center of the image as calcualted from the WCS

    HEADER DATA PROPERTIES

    These are things that you would traditionally find in the "header" of an image.

    * observation_id : str; a unique identifier of the exposure associated with the image
    * sca : int (str?); the SCA of this image
    * ra: float; the nominal RA at the center of the image in decimal degrees, usu. from the header
    *            (so may be slightly different from what you get using coord_center)
    * dec: float; the nominal RA at the center of the image in decimal degrees, usu. from the header
                  (so may be slightly different from what you get using coord_center)
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
    * exptime : float; exposure time in seconds.  (But be careful;
                because of the ramp readout of Roman images, not all
                pixels will have used the full exptime.  Don't try to
                think about it too hard, and just use the .data and
                .noise arrays.)
    * sky_level : float; an estimate of the sky level (in DAV) if known, None otherwise

    PATH PROPERTIES

    If possible, avoid using all "path" properties, and instead use the
    other properties to get access to image data (i.e., .data, .noise).
    Trust snappl to read the files.  If you don't, the behavior may not
    be what you expect.  Note that "noisepath" and "flagspath" are not defined for all Image
    subclasses, and will only be defined sometimes for some subclasses
    (depending on how data is stored).

    * filepath : pathlib.Path ; path *relative to the base path* of the image file. This may just
                                have the image data itself, or it may be a *base* filepath, or it
                                may have everything, depending on the subclass.
                                If you can avoid using this property, do so.  Use .data, etc, instead.
    * filename : string ; just the name part of filepath (so if filepath is Path("/foo/bar"), name is "bar")
    * full_filepath : pathlib.Path ; absolute path to file on system.  (Same as base_path / filepath.)
    * base_path : base path for images; usually will be Config value system.paths.images
    * base_dir : synonym for base_path

    * path : pathlib.Path; absolute path to the image on disk, sort of, in a complicatd way.
             DO NOT USE.  HERE FOR BACKWARDS COMPATIBILITY ONLY
    * name : str; synonym for filename.  DO NOT USE.  HERE FOR BACKWARDS COMPATIBILITY ONLY.

    """

    # SEE THE VERY BOTTOM OF THIS FILE
    # There a class variable _format_def is defined that explains the "format" field
    #  in the l2images table in the database.  (It's defined at the bottom of the
    #  file so all the classes will be defined by the time we get there.)

    # How close in degrees should the right- and up- calculated position angles match?
    _close_enough_position_angle = 3

    # This is just a conveneince varaible used by the vearious get_data methods
    data_array_list = [ 'all', 'data', 'noise', 'flags' ]

    # These are the properties that have underscore names internally,
    # and that can be set in the constructor.  (Some of them are
    # potentially hazardous, e.g., if width and height are not consistent
    # with data, then things will break.)
    internal_properties = { 'width': int,
                            'height': int,
                            'observation_id': str,
                            'sca': int,
                            'ra': float,
                            'dec': float,
                            'band': str,
                            'mjd': float,
                            'position_angle': float,
                            'exptime': float,
                            'sky_level': float,
                            'ra_corner_00': float,
                            'ra_corner_01': float,
                            'ra_corner_10': float,
                            'ra_corner_11': float,
                            'dec_corner_00': float,
                            'dec_corner_01': float,
                            'dec_corner_10': float,
                            'dec_corner_11': float
                           }


    def __init__( self, full_filepath=None, filepath=None, base_path=None, base_dir=None,
                  path=None, no_base_path=False, id=None, provenance_id=None,
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

        Only instantiate an image directly if you're creating something
        yourself that you know you want to write in a specific format,
        or if you're trying to read a file that's not covered by an
        ImageCollection.  When you do this, talk to the photometry
        working group and find out if this image *should* be covered by
        an ImageCollection.  (Note that there is an
        ImageCollectionManualFITS collection for reading loose FITS
        files.)

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

          is_superclass: bool, default False
             Used internally, should ONLY ever be set in the
             super().__init__(...)  lines in subclass constructors.  All
             subclasses should set this to True when calling
             super().__init__(...).  If you aren't writing an Image
             subclass, ignore this.


          observation_id : str
          sca: int, default None
          ra: float, default None
          dec: float, default None
          band: str, default None
          mjd: float, default None
          position_angle: float, default None
          exptime: float, default None
          sky_level: float, default None
          (ra|dec)_corner_(00|01|10|11): float, default None
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
            SNLogger.warning( "path argument to Image construtors is deprecated; use full_filepath" )
            full_filepath = path

        # This has to be set before superclass init because the
        #   PathedObject init will (indirectly) use it (by calling
        #   _set_base_path).
        self._format = format

        super().__init__( filepath=filepath, base_path=base_path, base_dir=base_dir,
                          full_filepath=full_filepath, no_base_path=no_base_path )

        consumed_kwargs = { 'full_filepath', 'filepath', 'base_path', 'base_dir', 'path', 'no_base_path',
                            'id', 'provenance_id', 'format', 'is_superclass' }
        consumed_kwargs = consumed_kwargs.union( set(self.internal_properties.keys()) )
        self._declare_consumed_kwargs( consumed_kwargs )
        if not is_superclass:
            self._verify_all_consumed_kwargs( **kwargs )

        self._id = asUUID( id ) if id is not None else None
        self._provenance_id = asUUID( provenance_id ) if provenance_id is not None else None

        for prop in self.internal_properties:
            val = kwargs.get( prop, _UnsetProperty() )
            if ( val is not None ) and ( not isinstance( val, _UnsetProperty ) ):
                val = self.internal_properties[prop]( val )
            setattr( self, prop, val )

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
            # SNLogger.warning( f"{self.__class__.__name__} constructor didn't recognize "
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
        """2d numpy array: image data in DAV.  Maybe not the same as what's in the file!  See Image class docstring."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data" )

    @data.setter
    def data( self, new_value ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data setter" )

    @property
    def noise( self ):
        """2d numpy array: 1σ pixel noise.  Maybe not the same as what's in the file!  See Image class docstring."""
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
        if ( self._width is None ) or ( isinstance( self._width, _UnsetProperty ) ):
            self._get_image_shape()
        return self._width

    @property
    def height( self ):
        """Int: height (y-size, first index in numpy arrays) of the image"""
        if ( self._height is None ) or ( isinstance( self._height, _UnsetProperty ) ):
            self._get_image_shape()
        return self._height


    # WARNING TO SUBCLASS AUTHORS
    # The fact that Image uses __getattr__ and __setattr__ can create
    #   subtle things that will go wrong if you try to override
    #   getters/setters for any of the properties that are in the sets
    #   in the if statements in these methods.  Hopefully you can get by
    #   using the getter/setter pre/post hooks.
    # BUT STILL BE WARNED: if you use a post_hook, it's entirely possible
    #   that it will make your class not work at all.  This is really
    #   some messy stuff we're doing here.  For an example, see
    #   FITSImageStdHeaders (which is also the only class as of this
    #   writing that uses this).

    def __getattr__( self, prop ):
        if prop in self.internal_properties.keys():
            if isinstance( getattr( self, f'_{prop}' ), _UnsetProperty ):
                if prop in ( 'ra', 'dec' ):
                    self._get_ra_dec()
                elif prop == 'position_angle':
                    self._get_position_angle()
                elif ( prop[:9] == 'ra_corner' ) or ( prop[:10] == 'dec_corner' ):
                    self._get_corners()
                else:
                    self._get_internal_attribute( prop )

            return getattr( self, f"_{prop}" )
        else:
            # If the property was available in the class either as an
            #   attribute or as a defined getter, then this __getattr__
            #   should never have been called.  That means that if it
            #   was called with prop as something other than one of the
            #   things in the set in the if statement above, the caller
            #   was trying to access a property of the object that isn't
            #   supposed to exist.  That would probably raise an
            #   exception even without this else here.  But, I have an
            #   explict error here just in case I'm not fully grokking
            #   the subtleties of using __getattr__, which frankly gives
            #   me the willies, so that the exception will be here and I
            #   can find out if it wasn't something I expected to
            #   happen.
            raise AttributeError( f"{self.__class__.__name__} has no definition of {prop}" )

    def __setattr__( self, prop ,val ):
        if prop in self.internal_properties.keys():
            object.__setattr__( self, f"_{prop}", val )
            if hasattr( self, '_header_property_setter_post_hook' ):
                self._header_property_setter_post_hook( prop )
        else:
            object.__setattr__( self, prop, val )


    @property
    def zeropoint( self ):
        """Deprecated; use get_zeropoint."""
        raise RuntimeError( "Don't use the zeropoint property, call get_zeropoint()" )


    @zeropoint.setter
    def zeropoint( self, val ):
        raise RuntimeError( "Can't set a zeropoint" )
        # self._zeropoint = float( val ) if val is not None else None

    def get_zeropoint( self, x=None, y=None, sed=None ):
        """Return the Image zeropoint for AB magnitudes.

        By definition, the zeropoint returned by this image is a
        "infinite aperture" zeropoint, or one that may be used with a
        snappl.psf.PSF whose normalization is done right, i.e., if the
        clip size were infinte, the get_clip() method of the PSF object
        would return an infinitely-sized numpy 2d array whose sum was 1.
        (This is also the definition that STPSF uses when returning
        PSF/PRFs.)  See below for much more discussion.

        Parameters
        ----------
          x, y: integers (or, I guess, floats); optional.
            Pixel position on the image.  Ideally, given our definition
            of zeropoint, these aren't used, because the units of the
            .data array for a properly flatfielded and
            illumination-corrected image makes the the image zeropoint
            constant across the image.  The parameters are here to hedge
            our bets in case a future subclass needs it.  To be safe,
            always pass in the x, y of the position on the image where
            you need the zeropoint.  If you don't pass anything, and if
            it matters, a properly-implemented Image subclass will
            assume the center of the image.

       sed : DEFINITION STILL INCOMING; optional.
            DON'T USE THIS RIGHT NOW.  The interface may well change.
            It's here as a placeholder to remind us we need it, and also
            for the docstring below.

            The SED of the object for which you want a zeropoint.
            Exactly how we specify SEDs is not yet known, but hopefully
            it will be a subclass of something we define in
            snappl/sed.py.  If not given, different subclasses will make
            different (maybe implicit!) assumptions.  It's possible that
            the subclass will not be able to take an arbitrary SED.  We
            hope to use snappl.sed for this, but we're still thinking it
            through.  For now, this parameter is ignored, and you'll get
            *something* that's for *some* SED that may be not only
            subclass dependent, but dependent on execution details
            (like, for instance, some kind of weighted average of the
            real SEDs of the stars used to determine the image
            zeropoint)

        Returns
        -------
          zp: float
             Can be used in::

                m_AB = -2.5 log10(DAV) + zp

             for an object with psf-fit or aperture-corrected DAV, if
             that object has an SED consistent with the sed parameter
             you passed or that is assumed by the subclass.

        So that we are very clear what we mean by zeropoint as returned
        by the the get_zeropoint() method of a snappl.image.Image or a
        snappl.image.Image subclass, this is the definition.

        First, imagine that you have an Image (i.e., an object of the
        class defined in snappl/image.py).  That image's data property
        is a two-dimensional array of floats.  Define "DAV" (for "data
        array value") as the units of that two dimensional array.  To
        highlight this:

           THE DAV IS THE UNIT OF THE NUMBERS WE GET IN THE DATA ARRAY

        (This is also what we define in the docstring of the Image class
        itself.)

        Whatever that actually is.  Importantly, this definition is
        agnostic as to whether the data array represents something like
        "counts" or "counts per second".  However, it still does have
        opinions about the meaning of the numbers; read on.

        Second, imagine that we have an astronomical source (a star, to
        make it concrete), and we have an image of that star taken by
        the telescope.  (Let's assume that our thought-experiment stars
        are not at all variable, so it doesn't matter if we're talking
        about the number of photons that entered the aperture during the
        time of the exposure, or per second.)  For our zeropoint
        definition, we are going to assume that the number of DAVs in
        the Image.data array is proportional to the number of photons
        that entered the telescope's aperture.  [ASIDE 1: this
        implicitly assumes that something like bias subtraction has
        already been done, so there isn't a systematic offset from pure
        electronic effects.]  [ASIDE 2: this defintion means that DAV is
        NOT a surface-brightness unit!  A properly implemented Image
        subclass is promising to do a conversion when you access the
        .data and .noise arrays to make sure you aren't getting
        something in surface brightness units; see RomanDatamodel Image
        for example.]  In reality, diffraction, quantum efficiency, and
        electronic effects will mean that some of the light energy that
        entered the telescope aperture will miss the detector or
        otherwise not be reflected in the read-out data array, but for
        now, let's assume that that is negligible.  Also, for
        definitional purposes, assume that there are absolutely no
        astronomical sources contributing to the light of hitting the
        detector than the star we're currently pointing at.

        Third, the star's SED matters.  F_ν(ν), or "flux
        density", comes in dimensionality of enery/time/area/frequency.
        It is defined so that::

           dE = A F_ν(dν) dt dν

        is the amount of light energy coming from the star at frequency
        ν within dν that entered a telescope aperture of area A in time
        dt.  Right now, we're going to assume that the star has a flat
        spectrum, i.e., F_ν(ν) is constant for all ν.  (We will relax
        this later; see COLOR TERMS below.)

        Fourth, when we divide the image into pixels, we want the
        response of every pixel in the data array to be exacly the same;
        by "response", we mean the conversion from number of photons
        entering the telescope in the sky area subtended by the pixel to
        DAV of the pixel.  (See CORRECTING FOR PIXEL RESPONSE below.)
        (Also see PIXEL AREA ISSUE below.)

        Fifth, let's assume that all backgrounds (i.e., light from anything
        other than the one star we're looking at) has been subtracted from
        the image.

        Under all these assumptions, we can define the flat-spectrum
        zeropoint zp (which may not be exactly what get_zeropoint
        returns!) to be::

           m = -2.5 * log10( DAVs ) + zp

        where DAVs is the sum of the whole data array, and m is an AB
        magnitude.  An AB magnitude is defined by::

           m_AB = -2.5 log10( f_ν / (erg s⁻¹ Hz⁻¹ cm⁻¹) ) - 48.60

        (at least if Wikipedia can be trusted).  This means that a source
        with a flux density 3631×10⁻²³ erg s⁻¹ Hz⁻¹ cm⁻¹=3631 Jy has m_AB=0.
        (Closer to 3.63078054770099×10³ Jy assuming 48.60 is a definition
        (not a measurement with uncertainty), but 4 sig figs is plenty for a
        docstring.)

        CORRECTING FOR PIXEL RESPONSE

        For our definition to work, it means that we're assuming some
        preprocessing has been done to the image by the time we receive
        it.  Neglecting all issues of pixel area, that means
        pixel-to-pixel gain variables have been corrected by
        flatfielding, so the same zeropoint applies to every pixel on
        the image.  It also assumes that if there is any vignetting
        (e.g., if the "effective telescope aperture" is different for
        different pixels), an illumination correction has taken all of
        that out.

        PIXEL AREA ISSUE

        When we say "pixel area" in this context, we are NOT talking
        about the physical area of the pixel on the array, but rather
        than angular area subtended on the sky by a pixel.  (Yes, if
        we're going to be precise, the existence of diffraction (at the
        very least) means that there isn't a hard-edged area on the sky
        that corresponds exactly to what a given pixel absorbs, but
        that's one of the big reasons we talk about PSFs for space-based
        imaging (on the ground, the atmosphere is usually way more
        significant).  It is still meaningful, by putting in the right
        kind of delta function or whatever in place of the actual
        diffraction (and/or atmospheric blurring) function, to map the
        physical area of a pixel on the array through optics to an
        angular area on the sky.)  This pixel area can come in units
        like steradian or arcsec².

        In the Roman Space Telescope, the pixel area subtended on the
        sky can vary by ~±2% over a single SCA.  The L2 maps provided by
        the Roman SOC have array values in units of surface brightness,
        i.e., something like DN/sec/steradian.  However, we have defined
        DAV to be more like DN/sec (though, again, we are explicitly
        agnostic as to whether DAV is a rate or not).

        What this means is that at least for L2 Roman images, the
        Image.data array will do a pixel-area correction before
        returning the DAV values; see the docstring on the Image class
        and on the Image.data property.

        As a result of all , pixel area is *not* an issue for the
        definition of the zeropoint.

        However, that also means that this zeropoint is what you'd use
        for point-source photometry.  It is *not* the zeropoint you'd
        use to identify isophots in a galaxy.  (Also, Image.data isn't
        formally the right thing to use to identify isophots in a
        galaxy, unless the pixel area really is constant across the
        array!)

        Note that when Image.data corrects the data to give DAV as
        something proportional to photon counts, not surface brightness,
        it fixes just purgely optical/geometric effects.  For electronic
        effects, espeically ones that depend on how full the well is,
        futher corrections that cannot be encapsulated (at least
        currently) by the Image.get_zeropoint() method will be needed.
        (Thushara, save us!)

        ACTUAL PHOTOMETRY

        Importantly, the zeropoint we've defined here DOES NOT take into
        account any aperture size, nor does it take into account any
        particular realization of a PSF.  It is a property *of the image*,
        not of the method used to extract photometry.  That means to use
        this zeropoint:

           * Aperture photometry values must be properly "aperture
             corrected" before the DAVs are fed into the zeropoint
             formula.  Ideally, when things aren't too complicated, this
             correction is just a single factor that multiplies the
             number of DAVs in the aperture to give an effective
             "infinite aperture" number of DAVs.  This factor will, of
             course, be different for apertures of different sizes (and
             shapes), and will also in principle be different at
             different positions on a detector array.  (For small
             apertures, it's also very difficult to do right.)  For real
             images, it's very difficult to determine this by looking at
             stars on images; you find yourself stuck between needing a
             very big aperture to capture, within your precision, "all"
             the flux, and not wanting your aperture to be too big so
             that you can find enough isolated stars.  If you have a
             very good estimate of the PSF/PRF, you can determine an
             aperture correction by integrating that.

           * PSF (or PRF) photometry must use PSFs (or PRFs) that are
             properly normalized to fit the defintion here.  "Properly
             normalized" here means that if you had an infinitely-sized
             image-scale array of the PSF (really PRF), its sum would be
             1; in practice, because you can't get infinitely-sized data
             arrays, the sum of the array you get will be less than 1,
             though for a big enough stamp size it might be very close.
             The PSFs (really PRFs) returned by
             snappl.psf.PSF.get_stamp() (and other methods) are
             *supposed to be* normalized this way.  (Also, as I
             understand it, the PSFS you get from STPSF are also
             normalized this way.)

             IT IS POSSIBLE that some further calibration post-processing of
             photometry after the zeropoint is applied may be entirely
             convolved with the definition of the PSF.  At the moment,
             snappl's class structure does not support this, but we will
             adapt if necessary.  However, we should ONLY adapt if it really
             is necessary! If it's just a matter of normalizing your PSFs
             differently, then just normalize them differently to fit our
             definitions!

        FILTERS AND COLOR TERMS

        In reality, we never measure something proportional to F_ν(ν)
        directly.  (Spectroscopy gets a lot closer to this than
        photometry does.)  Rather, we're always measuring some integral
        of F_ν(ν).  There are two things we have to consider.

        First, detectors and filters (and the whole telescope system,
        for that matter) have a different response at different
        frequencies.  Filters, in particular, only transmit light within
        a finite range of ν, though real detectors are also not
        sensitive to all frequencies.  We will call the system response
        D(ν), which we will define "the number of DAVs that we get in
        our data array per frequency bin for light of frequency ν for a
        source with f(ν)=3631 Jy", i.e., if we're looking at that
        hypotetical f(ν)=3631 Jy star::

           DAVs = ∫ D(ν) dν

        This means that D(ν) has units of s (or, more clearly, Hz⁻¹)
        (or, maybe, if you don't think of DAVs as dimensionless, units
        of DAV/Hz).

        Second, astronomical sources do not have a flat F_ν(ν), as we
        assumed in our discussion above and in the definiton of the
        thing we called zp.  The actual light source is going to have
        some SED S(ν) (in units of Energy/Time/Flux Binwidth/Area).

        The total number of DAVs detected, therefore, is::

            DAVs = ∫ S(ν) D(ν) / (3631Jy) dν

        (Presumably D(ν) goes to zero outside some finite range of ν so we
        don't have to think about infinite numbers.)

        Given this, the flat-spectrum zeropoint (which is what we
        defiend as zp above) is defined as::

            zp = 2.5 log10( ∫ D(ν) dν )

        (To see this: consider S(ν) = 3631 Jy for all ν, which is the definition of a m_AB=0 source.  In this case::

           0  = -2.5 log10(DAVs) + zp
              = -2.5 log10( ∫ (3631Jy) D(ν) / (3631Jy) dν ) + zp
              = -2.5 log10( ∫ D(ν) dν ) + zp
           zp = 2.5 log10( ∫ D(ν) dν )

        )

        A flat-spectrum source with flux density S₀ at all ν has AB
        magnitude::

           m_AB = -2.5 log10( S₀ / 3631Jy ) = -2.5 log10( S₀/Jy ) + 8.900

        (Which is where "8.900 is the AB zeropoint" comes from.  You will
        sometimes see people using a zeropoint of 31.4; this is just the
        zeropoint where the flux density is in nJy rather than Jy, as
        2.5log10(10⁹)=22.5.)

        The number of DAVs from such a source would be::

           DAVs = ∫ S₀ D(ν) / (3631Jy) dν = S₀ / 3631Jy * ∫ D(ν) dν

        or::

           DAVs / ( ∫ D(ν) dν ) = S₀ / 3631Jy

        Taking logs of both sides::

           -2.5 log10( DAVs ) + 2.5 log10( ∫ D(ν) dν ) = -2.5 log10( S₀/Jy ) + 2.5 log10( 3631 )
           -2.5 log10( DAVs ) + zp = -2.5 log10( S₀ ) + 8.900 = m_AB

        Where it gets painful is when S(ν) is not constant with ν.  In
        this case, the magnitude you will calculate from the
        flat-spectrum zeropoint would be::

          m_calc = -2.5 log10( DAVs ) + zp
                 = -2.5 log10( ∫ S(ν) D(ν) / (3631Jy) dν ) + 2.5 log10( ∫ D(ν) dν )

        However, for a source that doesn't have a flat S(ν), the true AB
        magnitude is ill-defined, because it's different for every ν!
        So, for a given filter, we have to define a fiducial frequency
        ν₀ (which corresponds to a fiducial wavelength λ₀ by the usual
        ν₀=hc/λ₀).  We could then define the "true" apparent magnitude
        of the object with SED S(ν) as::

          m = -2.5 log10( S(ν₀) / 3631 Jy )

        I think all the Roman filters have a defined fiducial
        wavelength, so we should just use that (really, hc/that) for ν₀,
        but we may need to document this somewhere.

        We then have a SED correction::

          cor_sed ≡ m - m_calc
                  = -2.5 log10( S(ν₀) / 3631 Jy ) + 2.5 log10( ∫ S(ν) D(ν) / (3631Jy) dν ) - 2.5 log10( ∫ D(ν) dν )
                  = 2.5 log10( ∫ S(ν) D(ν) / S(ν₀) dν ) - 2.5 log10( ∫ D(ν) dν )

          cor_sed = 2.5 log10( ∫ S(ν) D(ν) / S(ν₀) dν ) - zp

        The magnitude of an object is then::

           m = -2.5 log10( DAVs ) + zp + cor_sed

        (Do not become confused by the fact that zp is in cor_sed; we're not
        subtracting out the zeropoint from the final magnitude formula,
        because it's added back, sorta, inside the integral in cor_sed, we
        just can't separate it out to another obvious +zp because it's
        inside the integral, and while I've known named-chair professors of
        physics (but not astronomy) to claim that we were all doing cosmology
        wrong and making it too complicated because he freely factored
        variable things out of integrals, you aren't really supposed to do
        that.)

        Notice that you don't need to know the absolute S(ν) to
        calculate cor_sed, only S(ν)/S(ν₀).  This is why we say the
        "shape" of the SED.  The thing passed to the sed parameter of
        get_zeropoint() is really a SED shape (though a cautiously
        implemented subclass will not assume that the user is passing in a
        properly normalized sed).

        What get_zeropoint() returns is::

           zp + cor_sed

        for the sed specified by the sed parameter (with an implicitly
        assumed ν₀), or for some default sed if you don't specify one.
        IMPORTANT, don't assume this is a flat spectrum, because in
        practice that may be difficult or impossible to determine.  Each
        subclass may assume a different cor_sed (at least for now).

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_zeropoint" )

    def _get_image_shape( self ):
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_image_shape" )

    def _get_ra_dec( self ):
        """Used internally by subclasses.

        Subclass authors: this method must set both self._ra and
        self._dec.  when setting self._ra and self._dec, only set each
        if it is not currently None.  (This method won't be called under
        normal usage if both are already non-None.)

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_ra_dec" )

    def _get_corners( self ):
        """Used internally by subclasses.

        Subclass authors: this method must set all of
        (ra|dec)_corner_(00|01|10|11).  However, if any one is already
        non-None, then don't set it.  (This method won't be called
        uneder normal usage if all are already non-None.)

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_corners" )


    def _get_position_angle( self ):
        """Position angle in degrees north of east"""
        try:
            wcs = self.get_wcs()
        except Exception as ex:
            # Failed to get a wcs from the header.  This may be normal.  However, this also
            # means we cannot figure out a position angle, so mark it as explicitly unset.
            if not isinstance( self._position_angle, _UnsetProperty ):
                self._position_angle = _UnsetProperty()
            SNLogger.debug( f"Got exception {ex} trying to get a position angle; that *might* be normal." )
        else:
            ny, nx = self.image_shape
            midra, middec = wcs.pixel_to_world( nx/2., ny/2. )
            cosdec = np.cos( middec * np.pi / 180. )
            leftra, leftdec = wcs.pixel_to_world( nx/2.-1, ny/2. )
            dleftra = ( leftra - midra ) * cosdec
            dleftdec = leftdec - middec
            upra, updec = wcs.pixel_to_world( nx/2., ny/2.+1 )
            dupra = ( upra - midra ) * cosdec
            dupdec = updec - middec

            # Need to figure out if there's a mirroring.  If there is no
            # mirroring, then the cross product of up and left will have a
            # positive z component.... though we need to do a left-handed
            # cross product because RA/Dec is a left-handed coordinate system!
            # (Increasing RA is to the left, increasing Dec is up.)
            cross_z = - ( dupra * dleftdec - dupdec * dleftra )
            if cross_z > 0:
                leftang = np.arctan2( dleftdec, dleftra ) * 180. / np.pi
                upang = np.arctan2( -dupra, dupdec ) * 180 / np.pi
            else:
                leftang = np.arctan2( dleftdec, -dleftra ) * 180. / np.pi
                upang = np.arctan2( dupra, dupdec ) * 180. / np.pi

            # Have to deal with the edge case where they are around ±180.
            if ( ( ( leftang > 0 ) != ( upang > 0 ) )
                 and
                 ( np.fabs( np.fabs(leftang) - 180. ) <= self._close_enough_position_angle )
                 and
                 ( np.fabs( np.fabs(upang) - 180. ) <= self._close_enough_position_angle )
                ):
                if leftang < 0:
                    leftang += 360.
                if upang < 0:
                    upang += 360.

            if np.abs( leftang - upang ) > self._close_enough_position_angle:
                raise ValueError( f"Calculated position angle of {leftang:.2f}° looking to the left "
                                  f"and {upang:.2f}° looking up; these are inconsistent!" )
            self._position_angle = ( leftang + upang ) / 2.

            # Leftover from dealing with the RA~±180 edge case
            if self._position_angle > 180.:
                self._position_angle -= 360.

        return self._position_angle


    def _get_internal_attribute( self, prop ):
        """Used internally by subclasses.

        Subclass authors: must set self._{prop}

        Must be implemented for some, but not, all of the things in
        Image.internal_properties.  Things that should not be
        implemented (and which will be ignored if they are) are width,
        height, ra, dec, *_corner_*, position_angle.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_internal_attribute" )


    def fraction_masked( self ):
        """Fraction of pixels that are masked."""
        raise NotImplementedError( "Do.")


    def get_data( self, which='all', always_reload=False, cache=False ):
        """Read the data from disk and return one or more 2d numpy arrays of data.

        These will return the same things you'd get if you access the
        .data, .noise, and .flags properties of the object.  See the
        Image docstring for the defintion of the units of the .data and
        .noise arrays.

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
            properties.  (You often, but not always, want to set this to
            True!).

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


    def save_to_db( self, dbclient=None ):
        """Write this image record to the database.

        USE THIS WITH CARE.  All fields must be properly set.  In
        particular, the filepath and provenance_id must both be
        right for the database.  Don't use this if you don't really know
        what you're doing.

        This does not actually write any files; it just writes a
        database row.  Make sure files are where they need to be before
        calling this.

        """

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        props = [ 'id', 'provenance_id', 'filepath', 'width', 'height', 'observation_id', 'sca',
                  'ra', 'dec', 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                  'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                  'band', 'mjd', 'position_angle', 'exptime' ]
        data = { p: getattr( self, p ) for p in props if getattr( self, p ) is not None }
        data['format'] = self._format
        # Deal with json serialization
        data['filepath'] = str( data['filepath'] )
        data['id'] = str( data['id'] )
        data['provenance_id'] = str( data['provenance_id'] )

        row = dbclient.send( "/savel2image", json=data )

        return row


    @classmethod
    def bulk_save_to_db( cls, images, dbclient=None ):
        """Don't use this if you don't really know what you're doing."""

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        props = [ 'id', 'provenance_id', 'filepath', 'width', 'height', 'observation_id', 'sca',
                  'ra', 'dec', 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                  'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                  'band', 'mjd', 'position_angle', 'exptime' ]
        data = { p: [ getattr(i, p) for i in images ] for p in props }
        data['format'] = [ i._format for i in images ]
        # Deal with json serialization
        data['filepath'] = [ str(f) for f in data['filepath'] ]
        data['id'] = [ str(i) for i in data['id'] ]
        data['provenance_id'] = [ str(p) for p in data['provenance_id'] ]

        dbclient.send( "/bulksavel2images", json=data )


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
                  bginner=15, bgouter=25, return_resid_image=False ):
        """Do psf photometry.

        Does local background subtraction.

        Parameters
        ----------
          init_params: something
             passed to the init_params of a call to a
             photutils.psf.PSFPHotometry object.  IMPORTANT : photutils
             will accept all kinds of crazy stuff to find the x and y
             positions of the fit.  For this function, you MUST use
             either (x_init, y_init) or (x, y).  (But not both!)

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

          return_resid_image: bool, default False
             If True, returns photutils.psf.PSFPhotometry.make_residual_image
             along with the photometry results.

        Returns
        -------
          TODO

        """

        if 'flux_init' not in init_params.colnames:
            raise Exception('Astropy table passed to kwarg init_params must contain column \"flux_init\".')

        x0 = init_params['x_init'] if 'x_init' in init_params else init_params['x']
        y0 = init_params['y_init'] if 'y_init' in init_params else init_params['y']
        xseq = isSequence( x0 )
        yseq = isSequence( y0 )
        if xseq != yseq:
            raise ValueError( f"You passed init_parms with intial x {x0} and inital {y0}; they most either both "
                              f"be floats, or both be lists/arrays, you can't mix." )
        if ( xseq ) and ( len(x0) != len(y0) ):
            raise ValueError( f"init_params has {len(xseq)} x values and {len(yseq)} y values, which don't match" )
        if ( xseq ) and ( len(x0) != 1 ):
            SNLogger.warning( "Image.psf_phot was given multiple x, y coordinates.  Depending on the PSF subclass "
                              "you're using, this might be fine.  However, for some subclasses, you will only get "
                              "one PSF that will be used at all positions, so if you have a spatially variable "
                              "PSF, it will do the wrong thing." )
            x0 = x0[0]
            y0 = y0[0]
        psfmod = psf.getPhotutilsPSF( x0, y0 )
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

            if return_resid_image:
                return psf_results, psfphot.make_residual_image(self.data)
            else:
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

        May have side-effects on the internal data structure (e.g., FITS
        subclasses modify the internally stored header).

        Parameters
        ----------
          which : str, default "all"
            One of 'data', 'noise', 'flags', or 'all'

          imagepath : str, default None
            Full Path to write the image to.  If not specified, will use
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
            'provenance_id', 'observation_id', 'sca', 'ra', 'dec', 'filepath',
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

    def __init__( self, *args, data=None, noise=None, flags=None, is_superclass=False, **kwargs ):
        self._declare_consumed_kwargs( { 'data', 'noise', 'flags' } )
        super().__init__( *args, is_superclass=True, **kwargs )
        if not is_superclass:
            self._verify_all_consumed_kwargs( **kwargs )

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
        the image data (e.g., in a header), so subclasses should do that.

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
                  std_imagenames=False, is_superclass=False, **kwargs ):
        self._declare_consumed_kwargs( { 'noisepath', 'flagspath', 'imagehdu', 'noisehdu', 'flagshdu',
                                         'header', 'wcs', 'std_imagenames' } )
        super().__init__( *args, is_superclass=True, **kwargs )
        if not is_superclass:
            self._verify_all_consumed_kwargs( **kwargs )

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
        snappl_cutout._data = astropy_cutout.data.copy()
        snappl_cutout._header = self.get_fits_header()
        snappl_cutout._wcs = None if wcs is None else AstropyWCS( astropy_cutout.wcs )
        snappl_cutout._noise = astropy_noise.data.copy()
        snappl_cutout._flags = astropy_flags.data.copy()
        snappl_cutout._is_cutout = True
        snappl_cutout._width = astropy_cutout.data.shape[1]
        snappl_cutout._height = astropy_cutout.data.shape[0]

        # TODO : fix _ra* and _dec* fields, they're all WRONG

        # WORRY : we need to have all attributes from all current and future subclasses... there
        #   must be a better way.  (But I'm afraid of doing ALL attributes.)
        for prop in [ '_observation_id', '_sca', '_band', '_mjd', '_position_angle', '_exptime',
                      '_sky_level', '_zeropoint', '_ra', '_dec',
                      '_ra_corner_00', '_ra_corner_01', '_ra_corner_10', '_ra_corner_11',
                      '_dec_corner_00', '_dec_corner_01', '_dec_corner_10', '_dec_corner_11' ]:
            if hasattr( self, prop ):
                setattr( snappl_cutout, prop, getattr( self, prop ) )

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

        imghdr = None if self._header is None else FITSImage._astropy_header_to_fitsio_header( self._header )
        justwcshdr = None if wcshdr is None else FITSImage._astropy_header_to_fitsio_header( self._header )
        with fitsio.FITS( imagepath, 'rw' ) as f:
            f.write( self.data, header=imghdr )
        if saveno:
            with fitsio.FITS( noisepath, 'rw' ) as f:
                f.write( self.noise, header=justwcshdr )
        if savefl:
            with fitsio.FITS( flagspath, 'rw' ) as f:
                f.write( self.flags, header=justwcshdr )


# ======================================================================
# FITSImageStdHeaders
#
# A FITSImage that knows it has information in header keywords
#   that can be configurated at instantiation time.

class FITSImageStdHeaders( FITSImage ):
    """A FITS Image that has standardized header keywords corresponding to the properties defined in Image.

    Setting a property also updates the internally stored header.  When
    you construct an object, there is an optional argument header_kws
    (that has some sane defaults).  The keys of this dictionary are
    (approximately) names of internal properties of the Image object.
    Allowed values include many of the arguments to Image.__init__.  If
    you look at that docstring, the allwowed

    WARNING: THIS CLASS (and subclasses) IS NOT THREAD SAFE.  If you are
    using multithreading or multiprocessing, make sure that the same
    object of this class is not accessed by more than one thread or
    process at a time.

    """
    def __init__( self, *args, zeropoint=None, is_superclass=False,
                  header_kws = {
                      'observation_id': "POINTING",
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
        """Construct a FITSImageStdHeaders model.

        As with all these constructors, only use this if you really know
        what you're doing.  If you're reading an image from the
        database, you will never use a Image constructor.  Even if
        you're not reading an image from the database, most of the time
        you're going to use an ImageCollection, and not use an Image
        directly.

        Parameters
        ----------
          header_kws: dict
             A dictionary of internal_property: header_keyword.

             internal_property is a standard internal property of Image.
             Those properties are mostly defined in the Image docstring.
             They are also many of the arguments to Image::__init__,
             starting with ``observation_id`` and going through
             ``sky_level``.  If a internal_property is not present in
             the header_kws dict, it implies that it can't be found in
             the header, which may or may not break things.  (Special
             case: there may also be a "zeropoint" entry in this
             dictionary, which isn't a standard Image internal property,
             but is handled specially in this class.)

             header_keyword is, of course, the FITS header keyword to
             find the property in the FITS header.  This means that it's
             no longer than 8 characters, must be ASCII (no é or ξ or
             💩) and is almost certainly ALL CAPS.

             HANDLING OF THIS IS SUBTLE; READ AND BE CAREFUL.  *If* you
             pass the property directly in the constructor (so, for
             instance, if you make an image with::

                im = FITSImageStdHeaders( full_filepath="/path/to/file.fits", ra=42. )

             then later when you access im.ra, you will get 42., NOT
             what was in the header.  However, if you access im.dec, you
             will get whatever was found in the header, or an exception
             if nothing was found in the header.  The standard headers,
             thus, really are a fallback, but when you're using this
             class, the fallback is probably what you're really after.

             Be careful: this class blindly sets object properties based
             on the keys of this dictionary.  If you pass the wrong
             things, you could break its functionality.

          zeropoint: float, default None
            Unlike most image classes (which explicitly make getting the
            zeropoint a function, because exactly how it's done will be
            different for different kinds of images, and because it will
            depend on sed and maybe position), this class lets you pass
            one at construction time.  The reason is because you might
            want to be setting the zeropoint in the header.  (However,
            you still can't set it after the object is constructed... if
            we need that functionality, we should add it, BUT we may
            have more complicated zeropoint handling anyway in the
            future.)

          **kwargs: Everything else is passed to parent class
            constructors (FITSImage and its parent(s)).

        """

        self._declare_consumed_kwargs( { 'header_kws', 'zeropoint' } )
        super().__init__( *args, is_superclass=True, **kwargs )
        if not is_superclass:
            self._verify_all_consumed_kwargs( **kwargs )

        self._zeropoint = zeropoint if zeropoint is not None else _UnsetProperty()
        self._header_kws = header_kws

        # We set the _header_property_setter_post_hook here, rather than
        # before calling super().__init__().  We wish we could set it
        # before calling super().__init__(), because super().__init__()
        # will be parsing kwargs to set some of the properties we want
        # to post-process.  However, our post-processor is going to
        # access object properties (e.g., data, needed to create a new
        # header) that the superclass can't access because they're
        # @properties, and those things don't seem to be available in a
        # super().__init__()... python is complicated.  So, set it here,
        # so we won't have problems.
        self._header_property_setter_post_hook = self._property_post_hook_set_fits_header

        # If there already is a header for one reason or another, then
        # we need to make sure to sync the properties that won't have
        # been synced yet because the hook wasn't set.
        if hasattr( self, '_header' ) and ( self._header is not None ):
            self._sync_object_to_fits_header()


    def _property_post_hook_set_fits_header( self, prop ):
        if prop in self._header_kws:
            if ( not hasattr( self, '_header' ) ) or ( self._header is None ):
                self.get_fits_header()
            if prop in ( 'width', 'height' ):
                # Width and height might fail if the data file doesn't exist.
                # In that case, just don't worry about it for now, leave those
                # header keywords unset
                try:
                    self._header[ self._header_kws[prop] ] = getattr( self, f"_{prop}" )
                except OSError:
                    pass
            self._header[ self._header_kws[prop] ] = getattr( self, f"_{prop}" )


    def _sync_object_to_fits_header( self ):
        for prop in self.internal_properties.keys():
            if not isinstance( getattr(self, prop), _UnsetProperty ):
                self._property_post_hook_set_fits_header( prop )
        if not isinstance( self._zeropoint, _UnsetProperty ):
            self._property_post_hook_set_fits_header( 'zeropoint' )


    def get_fits_header( self ):
        """This particular subclass will make a new header if it can't read it for the image.

        It will populate the header based on the header_kws value passed
        to the constructor, if the corresponding property in the object
        is not _UnsetProperty.  It will then update the header so that
        the header has all the things in object_properties that show up
        in the header_kws dictionary where the object property os not
        _UnsetProperty.

        """

        if ( not hasattr( self, '_header' ) ) or ( self._header is None ):
            try:
                self._header = FITSImage.get_fits_header( self )
            except Exception as e:
                self._header = fits.PrimaryHDU( data=self.data ).header
                SNLogger.debug(f"Failed to read header from {self.filepath}, creating blank header: {e}")

            # We're going to intialize the header based on two principles:
            #   * Things already in the object supersede things in the header
            #   * Things neither in the object nor in the header should remain not in either; no None defaults!
            # These conventions are necessary for creating an object of this class
            #   with a new empty header if we want everything to work right.
            propconvs = self.internal_properties.copy()
            # This particular class has a special case 'zeropoint' internal property
            propconvs[ 'zeropoint' ] = float
            for prop, converter in propconvs.items():
                uprop = f"_{prop}"
                if prop in self._header_kws.keys():
                    kw = self._header_kws[ prop ]
                    if not isinstance( getattr( self, uprop ), _UnsetProperty ):
                        # The property is set in the object, so update the header to match.
                        self._header[ kw ] = getattr( self, uprop )
                    else:
                        # The property is not in the object.  If it's in the header, then set
                        #   the object property to match the header, otherwise leave it
                        #   unset.
                        if kw in self._header:
                            if prop == 'zeropoint':
                                # special case handling for zeropoint, which isn't in Image.itnernal_properties
                                self._zeropoint = float( self._header[kw] )
                            else:
                                setattr( self, uprop, converter(self._header[kw]) )

        return self._header


    def get_zeropoint( self, x=None, y=None, sed=None ):
        if isinstance( self._zeropoint, _UnsetProperty ):
            if 'zeropoint' not in self._header_kws:
                raise RuntimeError( "Can't get zeropoint for FITSImageStdHeaders, wasn't given a header "
                                    "keyword for the zeropoint" )
            hdr = self.get_fits_header()
            self._zeropoint = float( hdr[ self._header_kws['zeropoint'] ] )
        return self._zeropoint

    def _get_internal_attribute( self, prop ):
        if self._header is None:
            self.get_fits_header()

    def _get_ra_dec( self ):
        if self._header is None:
            self.get_fits_header()

    def _get_corners( self ):
        if self._header is None:
            self.get_fits_header()

    def _get_position_angle( self ):
        hdr = self.get_fits_header()
        if self._header_kws['position_angle'] in hdr:
            self._position_angle = float( hdr[ self._header_kws['positon_angle'] ] )
        else:
            super()._get_position_angle()

        return self._position_angle


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
        # Didn't do the whole is_superclass rigamarole here because this class
        #   takes no special arguments of its own, so its superclass can pretend
        #   it's not a superclass for purposes of argument validation.
        super().__init__( *args, **kwargs )


    def uncompressed_version( self, include=[ 'data', 'noise', 'flags' ], temp_dir=None ):
        """Make sure to get a FITSImageOnDisk that's not compressed.

        will write out up to three single-HDU FITS files in
        temp_dir (which defaults to photometry.snappl.temp_dir from the
        config).

        Parameters
        ----------
          include : sequence of str
            Can include any of 'data', 'noise', 'flags'; which things to
            write.  Ignored if the current image isn't compressed.

          temp_dir : pathlib.Path, default None
            The path to write the files.  Defaults to the config value system.paths.temp_dir

        Returns
        -------
          FITSImageOnDisk
            The path, noisepath, and flagspath properties will be set
            with the random filenames to which the FITS files were written.

        """
        temp_dir = pathlib.Path( temp_dir if temp_dir is not None
                                 else Config.get().value( 'system.paths.temp_dir' ) )
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

        return CompressedFITSImage( full_filepath=impath, noisepath=noisepath, flagspath=flagspath )


# ======================================================================
# This was the previous name for CompressedFITSImage.
# It was a terrible name.  It's here for backwards compatibilty.
#

class FITSImageOnDisk( CompressedFITSImage ):
    def __init__( self, *args, **kwargs ):
        # Didn't do the whole is_superclass rigamarole here because this class
        #   takes no special arguments of its own, so its superclass can pretend
        #   it's not a superclass for purposes of argument validation.
        super().__init__( *args, **kwargs )


# ======================================================================
# OpenUniverse 2024 Images are gzipped FITS files
#  HDU 0 : (something, no data)
#  HDU 1 : SCI (32-bit float)
#  HDU 2 : ERR (32-bit float)
#  HDU 3 : DQ (32-bit integer)

class OpenUniverse2024FITSImage( CompressedFITSImage ):
    def __init__( self, *args, imagehdu=1, noisehdu=2, flagshdu=3, **kwargs ):
        super().__init__( *args, imagehdu=imagehdu, noisehdu=noisehdu, flagshdu=flagshdu, **kwargs )
        # Not doing the is_superclass thing here because parent class FITSImage consumes all the explicit
        #   keywords that we do, so it can go ahead and pretend to not be a superclass for purposes
        #   of kwargs validation

        self._zeropoint = None

    _image_class_base_path_config_item = 'system.ou24.images'

    _filenamere = re.compile( r'^Roman_TDS_simple_model_(?P<band>[^_]+)_(?P<pointing>\d+)_(?P<sca>\d+).fits' )

    @property
    def truthpath( self ):
        """Path to truth catalog.  WARNING: this is OpenUniverse2024FITSImage-specific, use with care."""
        tds_base = pathlib.Path( Config.get().value( 'system.ou24.tds_base' ) )
        return ( tds_base / f'truth/{self.band}/{self.observation_id}/'
                 f'Roman_TDS_index_{self.band}_{self.observation_id}_{self.sca}.txt' )

    def _get_internal_attribute( self, prop ):
        if prop == 'observation_id':
            mat = self._filenamere.search( self.filepath.name )
            if mat is None:
                raise ValueError( f"Failed to parse {self.filepath.name} for pointing" )
            self._observation_id = mat.group( 'pointing' )

        elif prop == 'exptime':
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

        else:
            kwmap = { 'sca': ( 'SCA_NUM', int ),
                      'band': ( 'FILTER', lambda x: str(x).strip() ),
                      'mjd': ( 'MJD-OBS', float ),
                      'sky_level': ( 'SKY_MEAN', float )
                     }
            if prop not in kwmap.keys():
                raise RuntimeError( f"Called OpenUniverse2024FITSImage._get_internal_attribute({prop}); "
                                    f"this should never bappen." )
            header = self.get_fits_header()
            setattr( self, f"_{prop}", kwmap[prop][1]( header[ kwmap[prop][0] ] ) )

    def _get_image_shape( self ):
        header = self.get_fits_header()
        self._width = int( header['NAXIS1'] )
        self._height = int( header['NAXIS2'] )

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

    def get_zeropoint( self, x=None, y=None ):
        if self._zeropoint is None:
            header = self.get_fits_header()
            self._zeropoint = galsim.roman.getBandpasses()[self.band].zeropoint + header['ZPTMAG']
        return self._zeropoint

    def _get_zeropoint_the_hard_way( self, psf, ap_r=9 ):
        """This is here hopefully as legacy code.

        If, however, it turns out that
        galsim.roman.getBandpasses()[self.band].zeropoint +
        header['ZPTMAG'] is not a good enough zeropoint, we may need to
        resort to this.

        """
        raise RuntimeError( "Not up to date." )

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
#   self._dm.err**2 == self._dm.var_poisson + self._dm.var_rnoise
#
# Potentially useful links:
#   https://roman-docs.stsci.edu/data-handbook/wfi-data-levels-and-products#DataLevelsandProducts-Level2
#   https://github.com/spacetelescope/rad
#   https://github.com/spacetelescope/rad/blob/main/src/rad/resources/schemas/exposure-1.3.0.yaml
#     (check that the version is current on this one!)


class RomanDatamodelImage( Image ):
    """An image read from a roman datamodel ASDF file.

    See Issue #46 for concerns about performance/memory and imlementation of this object.

    """
    _detectormatch = re.compile( "^WFI([0-9]{2})$" )

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        # Not doing is_superclass since we don't consume any custom keyword arguments
        self._dm = None
        self._dm_meta_cache = None
        self._data = None
        self._noise = None
        self._flags = None

    # TODO : many of the _get_* functions still need to be implemented for RomanDatamodelImage !

    # Yes, I know that you can do with rdm.open(), but I want to cache other stuff here too,
    #   in order to possibly save some gratuitous extra opens when pulling random information.
    #   Cache the shape and the metadata the first time we open the roman_datamodels file.
    @contextmanager
    def _with_dm( self ):
        dm = None
        try:
            dm = rdm.open( self.full_filepath, mode='r' )
            if self._dm_meta_cache is None:
                self._dm_meta_cache = dm.meta.copy()
            if ( self._width is None ) or ( isinstance( self._width, _UnsetProperty ) ):
                self._width = dm.shape[1]
            if ( self._height is None ) or ( isinstance( self._height, _UnsetProperty ) ):
                self._height = dm.shape[0]
            yield dm
        finally:
            if dm is not None:
                dm.close()

    @property
    def _dm_meta( self ):
        if self._dm_meta_cache is None:
            dm = rdm.open( self.full_filepath, mode='r' )
            self._dm_meta_cache = dm.meta.copy()
            dm.close()
        return self._dm_meta_cache

    def _get_image_shape( self ):
        with self._with_dm() as _dm:
            # ... what we had to do already happened in self._with_dm()
            pass

    def _get_ra_dec( self ):
        # TODO : see if there's something in the header that would work
        ny, nx = self.image_shape
        wcs = self.get_wcs()
        self._ra, self._dec = wcs.pixel_to_world( nx / 2., ny / 2. )

    def _get_corners( self ):
        ny, nx = self.image_shape
        wcs = self.get_wcs()
        self._ra_corner_00, self._dec_corner_00 = wcs.pixel_to_world( 0, 0 )
        self._ra_corner_01, self._dec_corner_01 = wcs.pixel_to_world( 0, ny-1 )
        self._ra_corner_10, self._dec_corner_10 = wcs.pixel_to_world( nx-1, 0 )
        self._ra_corner_11, self._dec_corner_11 = wcs.pixel_to_world( nx-1, ny-1 )

    def _get_internal_attribute( self, prop ):
        meta = self._dm_meta

        if prop == 'observation_id':
            self._observation_id = meta.observation.observation_id

        elif prop == 'sca':
            match = self._detectormatch.search( meta.instrument.detector )
            if match is None:
                raise ValueError( f'Failed to parse meta.instrument.detector='
                                  f'"{meta.instrument.detector} for "WFInn"' )
            self._sca = int( match.group(1) )

        elif prop == 'band':
            self._band = meta.instrument.optical_element

        elif prop == 'mjd':
            self._mjd = ( meta.exposure.start_time.mjd + meta.exposure.end_time.mjd ) / 2.

        elif prop == 'exptime':
            self._exptime = meta.exposure.exposure_time

        elif prop == 'sky_level':
            SNLogger.warning( "We need to find a better way to get the sky level of a RomanDatamodelImage" )
            self._sky_level = meta.statistics.image_median

        else:
            raise ValueError( f"Don't know how to get property {prop} of a {self.__class__.__name__}" )


    def get_zeropoint( self, x=None, y=None ):
        # photometry.conversion_megajanskys gives MJy per steradian that
        #   gives an instrumental count rate of 1 dn/second.  I'm
        #   assuming that's 1 dn/second per pixel, as it's not clear
        #   what this would mean otherwise.  (I guess it could be 1
        #   dn/s/sr?  But then why bother talking about surface
        #   brightness, if the sr is on both sides?)
        #
        # Next, I'm assuming that the pixel values in L2 images are
        #   in units of dn/s (*not* dn).
        #
        # photometry.pixel_area is the area of one pixel in ... well,
        #   it's not clear, because the comments in the schema say
        #   "in units of steradians", but then the "unit:" field says
        #   "uJy.arcsec**-2", so I really don't know what to make of that.
        #   I'm going to assume it's in steradians for now
        #
        # What we really want is the number of Jy (not Jy/sr or
        #   whatever) we get from a certain number of "counts in the
        #   image", summed over all the pixels where those counts were.
        #   (Thiking a PSF, hence surface brightness is not the right
        #   thing to think about.)  If we multiply
        #   conversion_megajanskys * pixel_area (define "cm_pa" to be
        #   that), we should get the number of MJy that correspond a
        #   total count rate summed over all the pixels that light from
        #   the object fell into of 1 dn/s
        #
        # Below, define dn_s to be the total dn_s (i.e., pixel values in
        #   the image) summed over all pixels that light from the object
        #   fell into (determined either from aperture photometry with
        #   an infinite aperture after background subtraction, or psf
        #   fitting).  Define f_Jy to be the flux in Jy from the star.
        #   Define m_ab to be the AB magnitude.  Define cm_ma as above:
        #   conversion_megajanskys * pixel_area
        #
        # f_Jy = cm_ma * 1e6 * dn_s         [1e6 is to get cm_ma in units of Jy/(dn/s)]
        # m_ab = -2.5*log10( f_Jy ) + 8.90  [This is just the standard definition of AB magnitude]
        #      = -2.5*log10( cm_ma * 1e6 * dn_s ) + 8.90
        #      = -2.5*log10( dn_s ) -2.5*log10( cm_ma ) - 15 + 8.90
        # m_ab = -2.5*log10( dn_s ) + zp    [This is the definition of zp]
        # zp = -2.5*log10( cm_ma ) - 6.1

        # ****************************************
        # NEXT BIT COMMENTED OUT
        # We decided that we were going to scale data (see the "data" and "noise" properties)
        #   instead of having a spatially variable zeropoint.
        # It's still here in case we reverse this decision
        #
        # x = int( np.floor( self.width / 2. + 0.5 ) ) if x is None else int( np.floor( x + 0.5 ) )
        # y = int( np.floor( self.height / 2. + 0.5 ) ) if y is None else int( np.floor( y + 0.5 ) )

        # if self._pixelareamap is None:
        #     pixelarea_name = crds.getreferences(
        #         self.dm.get_crds_parameters(),
        #         reftypes=["area"],
        #         observatory="roman",
        #     )["area"]

        #     ifp = rdm.open( pixelarea_name )
        #     self._pixelarea = np.array( ifp.data )
        #     ifp.close()

        # To go from surface brightness to something proportional to
        #   electrions, you multiply the image by self._pixelarea (which
        #   is unitless, relative to self.dm.photometry.pixel_area)
        #
        # So f = sb * self._pixelarea
        #
        # m = -2.5 log10( f ) + zp_f
        #   = -2.5 log10( sb * _pixelrea ) + zp_f
        #   = -2.5 log10(sb) - 2.5 log10(_pixelarea) + zp_f
        #
        # So zp_sb = zp_f - 2.5log10(_pixelarea)
        #
        # We need to return zp_sb because the image is in surface brightness units
        # ****************************************

        meta = self._dm_meta
        return -6.1 - 2.5 * np.log10( meta.photometry.conversion_megajanskys *
                                      meta.photometry.pixel_area
                                     )

                                     # * self._pixelarea[y, x] )

    @property
    def data( self ):
        if getattr( self, '_data', None ) is None:
            # When we load any of data, noise, or flags, we load all three.  Not
            # obvious that's the right thing to do.  Tradeoff of overhead
            # opening and reading files and pixel area files vs. memory usage.
            self.get_data( which='all', always_reload=True, cache=True )
        return self._data

    @property
    def noise( self ):
        if getattr( self, '_noise', None ) is None:
            # When we load any of data, noise, or flags, we load all three.  Not
            # obvious that's the right thing to do.  Tradeoff of overhead
            # opening and reading files and pixel area files vs. memory usage.
            self.get_data( which='all', always_reload=True, cache=True )
        return self._noise

    @property
    def flags( self ):
        # TODO : https://roman-pipeline.readthedocs.io/en/latest/roman/dq_init/reference_files.html#reference-files
        # We probably need to do some translation.  We have to think about what we are defining
        #   as a "bad" pixel.
        # Using the _flags property here is so that we can set the flags elsewhere. -CFM
        if getattr(self, '_flags', None) is None:
            # When we load any of data, noise, or flags, we load all three.  Not
            # obvious that's the right thing to do.  Tradeoff of overhead
            # opening and reading files and pixel area files vs. memory usage.
            self.get_data( which='all', always_reload=True, always_cache=True )
        return self._flags

    def _load_sb_data_and_sb_noise( self, always_reload=False ):
        if ( always_reload or
             ( getattr( self, '_sb_data', None ) is None ) or
             ( getattr( self, '_sb_noise', None ) is None )
            ):
            with self._with_dm() as dm:
                self._sb_data = np.array( dm.data )
                self._sb_noise = np.array( dm.err )


    @property
    def sb_data( self ):
        """NOT A STANDARD Image PROPERTY!  Surface-brightness units data array.

        This is the native data array straight out of the roman_datamodel L2 asdf files.

        """
        if getattr( self, '_sb_data', None ) is None:
            self._load_sb_data_and_sb_noise()
        return self._sb_data


    @property
    def sb_noise( self ):
        """NOT A STANDARD Image PROPERTY!  Surface-brightness units noise array.

        This is the native noise array straight out of the roman_datamodel L2 asdf files.

        """
        if getattr( self, '_sb_noise', None ) is None:
            self._load_sb_data_and_sb_noise()
        return self._sb_noise


    def get_data( self, which='all', always_reload=False, cache=False ):
        """Read the data from disk and return one or more 2d numpy arrays of data.

        See Image.get_data for definition of parameters.

        """
        if self._is_cutout:
            raise RuntimeError( f"{self.__class__.__name__} images don't know how to deal with being cutouts." )

        if which not in ( 'all', 'data', 'noise', 'flags' ):
            raise ValueError( f"Unknown value of which: {which}" )

        if ( always_reload or
             ( ( which == 'all' ) and any( i is None for i in [ self._data, self._noise, self._flags ] ) ) or
             ( ( which == 'data' ) and ( self._data is None ) ) or
             ( ( which == 'noise' ) and ( self._noise is None ) ) or
             ( ( which == 'flags' ) and ( self._flags is None ) )
            ):
            with self._with_dm() as dm:
                data = np.array( dm.data ) if which in ( 'data', 'all' ) else None
                noise = np.array( dm.err ) if which in ( 'noise', 'all' ) else None
                flags = np.array( dm.dq ) if which in ( 'flags', 'all' ) else None

                if ( data is not None ) or ( noise is not None ):
                    pixelarea_name = crds.getreferences(
                        dm.get_crds_parameters(),
                        reftypes=["area"],
                        observatory="roman",
                    )["area"]
                    with rdm.open( pixelarea_name ) as ifp:
                        pixelarea = np.array( ifp.data )
                    if data is not None:
                        data *= pixelarea
                    if noise is not None:
                        noise *= pixelarea

        else:
            data = self._data
            noise = self._noise
            flags = self._flags

        if which == 'all':
            if cache:
                self._data = data
                self._noise = noise
                self._flags = flags
            return [ data, noise, flags ]
        elif which == 'data':
            if cache:
                self._data = data
            return [ data ]
        elif which == 'noise':
            if cache:
                self._noise = noise
            return [ noise ]
        elif which == 'flags':
            if cache:
                self._flags = flags
            return [ flags ]
        else:
            raise RuntimeError( "This should never happen" )



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
        SNLogger.warning( "Only use the dm property of RomanDatamodelImage if you know what you're doing." )
        if self._dm is None:
            self._dm = rdm.open( self.full_filepath, mode='r' )
        return self._dm

    def get_wcs( self, wcsclass=None ):
        wcsclass = "RDM_GWCS" if wcsclass is None else wcsclass
        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "RDM_GWCS":
                self._wcs = RDM_GWCS( gwcs=self._dm_meta.wcs )
            else:
                raise NotImplementedError( "RomanDatamodelImage can't (yet?) get a WCS of type {wcsclass}" )
        return self._wcs

    def get_cutout(self, x, y, xsize, ysize=None, mode='strict', fill_value=np.nan, return_FITS=True ):
        """See Image.get_cutout
        The mode and fill_value parameters are passed directly to astropy.nddata.Cutout2D for FITSImage.

        Inputs
        -------
        return_FITS: bool, default True
            If True, the cutout will be returned as a snappl.image.FITSImage.
            If False, the cutout will be returned as a snappl.image.RomanDatamodelImage.

        Returns
        -------
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

        data, noise, flags = self.get_data( 'all' )

        wcs = self.get_wcs()
        if isinstance( wcs, RDM_GWCS ):
            wcs = wcs.get_astropy_wcs()
            # Here we convert the GWCS to an AstropyWCS, which is what Cutout2D needs.  This is a little
            # worrying because we are using a slightly different WCS to get the cutout, though I don't
            # think it hugely matters since it only needs to be accurate to the pixel level. However,
            # we should consider implementing a way to get the cutout without converting to an AstropyWCS.
            SNLogger.warning("This is turning a GWCS into an AstropyWCS to use with Cutout2D.  "
                "Is this a permanent solution?")

        else:
            raise NotImplementedError( "RomanDatamodelImage.get_cutout only works with GWCS wcses"
                                       f", not {wcs.__class__.__name__} wcses." )


        apwcs = None if wcs is None else wcs
        # This was wcs._wcs in the FITS version of this function. I
        # am unclear why I had to change it to be just wcs, i.e., not wcs._wcs

        # Remember that numpy arrays are indexed [y, x] (at least if they're read with astropy.io.fits)
        astropy_cutout = Cutout2D(data, (x, y), size=(ysize, xsize), wcs=apwcs, mode=mode, fill_value=fill_value)
        astropy_noise = Cutout2D(noise, (x, y), size=(ysize, xsize), wcs=apwcs, mode=mode, fill_value=fill_value)
        # Per the slack channel, it seems 1 will be used for bad pixels.
        # https://github.com/spacetelescope/roman_datamodels/blob/main/src/roman_datamodels/dqflags.py
        astropy_flags = Cutout2D(flags, (x, y), size=(ysize, xsize), wcs=apwcs, mode=mode, fill_value=1)

        if return_FITS:
            snappl_cutout = FITSImage(full_filepath=self.full_filepath, no_base_path=True, width=xsize, height=ysize)
            snappl_cutout._data = astropy_cutout.data.copy()
            snappl_cutout._noise = astropy_noise.data.copy()
        else:
            # WORRY.  We're creating a subclass that's going to point to the non-cutout file.
            # Look to see if rdm has a clean way of making cutouts itself, and just use that
            # if it exists!
            snappl_cutout = self.__class__(full_filepath=self.full_filepath, no_base_path=True,
                                           width=xsize, height=ysize)
            snappl_cutout.data = astropy_cutout.data.copy()
            snappl_cutout.noise = astropy_noise.data.copy()
        snappl_cutout._wcs = None if wcs is None else AstropyWCS( astropy_cutout.wcs )

        snappl_cutout._flags = astropy_flags.data.copy()
        snappl_cutout._is_cutout = True
        snappl_cutout._width = astropy_cutout.data.shape[1]
        snappl_cutout._height = astropy_cutout.data.shape[0]
        snappl_cutout.band = self.band

        # TODO : fix _ra* and _dec* fields, they're all WRONG

        # WORRY : we need to have all attributes from all current and future subclasses... there
        #   must be a better way.  (But I'm afraid of doing ALL attributes.)
        for prop in [ '_observation_id', '_sca', '_band', '_mjd', '_position_angle', '_exptime',
                      '_sky_level', '_zeropoint', '_ra', '_dec',
                      '_ra_corner_00', '_ra_corner_01', '_ra_corner_10', '_ra_corner_11',
                      '_dec_corner_00', '_dec_corner_01', '_dec_corner_10', '_dec_corner_11' ]:
            if hasattr( self, prop ):
                setattr( snappl_cutout, prop, getattr( self, prop ) )

        snappl_cutout.exptime = self.exptime
        return snappl_cutout

    def get_ra_dec_cutout(self, ra, dec, xsize, ysize=None, mode='strict', fill_value=np.nan):
        """See Image.get_ra_dec_cutout


        The mode and fill_value parameters are passed directly to astropy.nddata.Cutout2D for FITSImage.
        """

        wcs = self.get_wcs()
        x, y = wcs.world_to_pixel( ra, dec , with_bounding_box=False)
        x = int( np.floor( x + 0.5 ) )
        y = int( np.floor( y + 0.5 ) )
        return self.get_cutout( x, y, xsize, ysize, mode=mode, fill_value=fill_value )

    @data.setter
    def data(self, new_value):
        if (
            isinstance(new_value, np.ndarray)
            and np.issubdtype(new_value.dtype, np.floating)
            and len(new_value.shape) == 2
        ) or (new_value is None):
            self._data = new_value
        else:
            raise TypeError("Data must be a 2d numpy array of floats.")

    @noise.setter
    def noise(self, new_value):
        if (
            isinstance(new_value, np.ndarray)
            and np.issubdtype(new_value.dtype, np.floating)
            and len(new_value.shape) == 2
        ) or (new_value is None):
            self._noise = new_value
        else:
            raise TypeError("Noise must be a 2d numpy array of floats.")

    @flags.setter
    def flags(self, new_value):
        if (
            isinstance(new_value, np.ndarray)
            and np.issubdtype(new_value.dtype, np.integer)
            and len(new_value.shape) == 2
        ) or (new_value is None):
            self._flags = new_value
        else:
            raise TypeError("Flags must be a 2d numpy array of integers.")

    def free( self ):
        self._data = None
        self._noise = None
        self._flags = None


# ======================================================================

class RomanDatamodelImage_Needs_CRDS_GWCS( RomanDatamodelImage ):
    def get_wcs( self, wcsclass=None ):
        wcsclass = "RDM_CRDS_GWCS" if wcsclass is None else wcsclass
        if ( self._wcs is None ) or ( self._wcs.__class__.__name__ != wcsclass ):
            if wcsclass == "RDM_CRDS_GWCS":
                with self._with_dm() as dm:
                    self._wcs = RDM_CRDS_GWCS( gwcs=self._dm_meta.wcs, i_know_what_i_am_doing=True, parent_image=dm )
            else:
                raise NotImplementedError( "RomanDatamodelImage_Needs_CRDS_GWCS can't get a WCS of type {wcsclass}" )
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
                      101: { 'description': "RDM image from Rick Sims 2026-08 that need a CRDS WCScorrection",
                             'image_class': RomanDatamodelImage_Needs_CRDS_GWCS,
                             'base_path_config': 'system.paths.images'
                            },
                     }
