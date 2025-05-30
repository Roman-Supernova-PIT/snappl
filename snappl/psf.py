import yaml
import base64

import numpy as np

from roman_imsim.utils import roman_utils
import galsim

from snpit_utils.config import Config
from snpit_utils.logger import SNLogger


class PSF:
    # Thought required: how to deal with oversampling.

    def __init__( self, *args, **kwargs ):
        pass

    # This is here for backwards compatibility
    @property
    def clip_size( self ):
        return self.stamp_size

    @property
    def stamp_size( self ):
        """The size of the one side of a PSF image stamp at image resolution.  Is always odd."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement stamp_size." )


    def get_stamp( self, x, y, flux=1. ):
        """Return a 2d numpy image of the PSF at the image resolution.

        The PSF will be centered as best possible on the stamp*.  So, if
        x ends in 0.8, it will be left of center, and if x ends in 0.2,
        it will be right of center.  If the fractional part of x or y is
        exactly 0.5, there's an ambituity as to where on the image you
        should place the stamp of the PSF.  The position of the PSF on
        the returned stamp will always round *down* in this case.  (The
        pixel on the image that corresponds to the center pixel on the
        clip is at floor(x+0.5),floor(y+0.5), *not*
        round(x+0.5),round(y+0.5).  Those two things are different, and
        round is not consistent; see the comment in
        OversampledImagePSF.get_stamp for more if you care.)

        So, for example, assuming the PSF is intrinsically centered*,
        if the stamp size is 5×5 and you ask for the PSF at x=1023,
        y=1023, then you're going to want to put the stamp on to the
        image at image[1021:1026,1021:1026].  However, if you ask for
        the PSF at x=1023.5,y=1023., you'll want to put the stamp on the
        image at image[1021:1026,1022:1027].  (Remember that default
        numpy arrays of astronomy images are indexed [y,x].)

        * "The PSF will be centered as best possible on the stamp": this
          is only true if the PSF itself is intrinsically centered.  See
          OversampledImagePSF.create for a discussion of
          non-intrinsically-centered PSFs.

        Parameters
        ----------
          x: float
            Position on the image of the center of the psf.  If not
            given, defaults to something sensible that was defined when
            the object was constructed.  If you want to do sub-pixel
            shifts, then the fractional part of x will (usually) not be
            0.

          y: float
            Position on the image of the center of the psf.  Same kind
            of default as x.

          flux: float, default 1.
             Make the sum of the clip this.  If None, just let the clip
             be scaled however it's naturally scaled.  Fo rsome
             subclasses, that may be what you actually want.

        Returns
        -------
          2d numpy array

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_stamp" )

    @classmethod
    def get_psf_object( cls, psfclass, **kwargs ):
        """Return a PSF object whose type is specified by psfclass.

        Parameters
        ----------
          psfclass : str
             The name of the class of the PSF to instantiate.

          **kwargs : further keyword arguments
             TODO : we need to standardize on these so that things can
             just call PSF.get_psf_object() without having to have their
             own if statements on the type to figure out what kwargs to
             pass!

        """
        if psfclass == "OversampledImagePSF":
            return OversampledImagePSF.create( **kwargs )

        if psfclass == "YamlSerialized_OversampledImagePSF":
            return YamlSerialized_OversampledImagePSF( **kwargs )

        if psfclass == "ou24PSF":
            return ou24PSF( **kwargs )

        raise ValueError( f"Unknown PSF class {psfclass}" )


class OversampledImagePSF( PSF ):
    @classmethod
    def create( cls, data=None, x=None, y=None, oversample_factor=1., enforce_odd=True, normalize=True, **kwargs ):

        """Parameters
        ----------
          data: 2d numpy array
            The image data of the oversampled PSF.  Required.

          x, y: float
            Position on the source image where this PSF is evaluated.
            Required.  Most of the time, but not always, you probably
            want x and y to be integer values.  (As in, not integer
            typed, but floats that satisfy x-floor(x)=0.)  These are
            also the defaults that get_stamp will use if x and y are not
            passed to get_stamp.

            If x and/or y have nonzero fractional parts, then the data
            array must be consistent.  First consider non-oversampled
            data.  Suppose you pass a 11×11 array with x=1022.5 and
            y=1023.25.  In this case, the peak of a perfectly symmetric
            PSF image on data would be at (4.5, 5.25).  (Not (5.5,
            5.25)!  If something's at *exactly* .5, always round down
            here regardless of wheter the integer part is even or odd.)
            The center pixel and the one to the right of it should have
            the same brightness, and the pixel just below center should
            be dimmer than the pixel just above center.

            For oversampled psfs, the data array must be properly
            shifted to account for non-integral x and y.  The shift will
            be as in non-oversampled data, only multiplied by the
            oversampling factor.  So, in the same example, if you
            specify a peak of (4.5, 5.25), and you have an oversampling
            factor of 3, you should pass a 33×33 array with the peak of
            the PSF (assuming a symmetric PSF) at (14.5, 16.75).

          oversample_factor: float, default 1.
            There are this many pixels along one axis in data for one pixel in the original image.

          enforce_odd: bool, default True
            Enforce x_edges and y_edges having an odd width.

          normalize: bool, default True
            Make sure internally stored PSF sums to 1 ; you usually don't want to change this.

        Returns
        -------
          object of type cls

        """

        if len(kwargs) > 0:
            SNLogger.warning( f"Unused arguments to OversampledImagePSF.create: {[k for k in kwargs]}" )

        # TODO : implement enforce_odd
        # TODO : enforce square

        if not isinstance( data, np.ndarray ) or ( len(data.shape) != 2 ):
            raise TypeError( "data must be a 2d numpy array" )

        x = float( x )
        y = float( y )

        psf = cls()
        psf._data = data
        if normalize:
            psf._data /= psf._data.sum()
        psf._x = x
        psf._y = y
        psf._oversamp = oversample_factor
        return psf

    @property
    def x( self ):
        return self._x

    @property
    def y( self ):
        return self._y

    @property
    def x0( self ):
        return self._x0

    @property
    def y0( self ):
        return self._x0

    @property
    def oversample_factor( self ):
        return self._oversamp

    @property
    def oversampled_data( self ):
        return self._data

    @property
    def stamp_size( self ):
        """The size of the PSF image clip at image resolution.  Is always odd."""
        sz = int( np.floor( self._data.shape[0] / self._oversamp ) )
        sz += 1 if sz % 2 == 0 else 0
        return sz


    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self._data = None
        self._x = None
        self._y = None
        self._x0 = None
        self._y0 = None
        self._oversamp = None

    def get_stamp( self, x=None, y=None, flux=1. ):
        # (x, y) is the position on the image for which we want to render the PSF.
        x = float(x) if x is not None else self._x
        y = float(y) if y is not None else self._y

        # (xc, yc) is the closest pixel center to (x, y) on the image--
        #
        # round() isn't the right thing to use here, because it will
        #   behave differently when x - round(x) = 0.5 based on whether
        #   floor(x) is even or odd.  What we *want* is for the psf to
        #   be as close to the center of the clip as possible.  In the
        #   case where the fractional part of x is exactly 0.5, it's
        #   ambiguous what that means-- there are four places you could
        #   stick the PSF to statisfy that criterion.  By using
        #   floor(x+0.5), we will consistently have the psf leaning down
        #   and to the left when the fractional part of x (and y) is
        #   exactly 0.5, whereas using round would give different
        #   results based on the integer part of x (and y).
        xc = int( np.floor( x + 0.5 ) )
        yc = int( np.floor( y + 0.5 ) )

        # (natx, naty) is the "natural position" on the image for the
        # psf.  This is simply (int(x), int(y)) if the fractional part
        # of x and y are zero.  Otherwise, it rounds to the closest
        # pixel... unless the fractional part is exactly 0.5, in which
        # case we do floor(x+0.5) instead of round(x) as described above.
        natx = int( np.floor( self._x + 0.5 ) )
        naty = int( np.floor( self._y + 0.5 ) )
        # natxfrac and natyfrac kinda the negative of the fractional
        #   part of natx and naty.  They will be in the range (-0.5,
        #   0.5]
        natxfrac = natx - self._x
        natyfrac = naty - self._y

        # See Chapter 5, "How PSFEx Works", of the PSFEx manual
        #     https://psfex.readthedocs.io/en/latest/Working.html
        # We're using this method for both image and psfex PSFs,
        #   as the interpolation is more general than PSFEx:
        #      https://en.wikipedia.org/wiki/Lanczos_resampling
        #   ...though of course, the choice of a=4 comes from PSFEx.


        psfwid = self._data.shape[0]
        stampwid = self.clip_size

        psfdex1d = np.arange( -( psfwid//2), psfwid//2+1, dtype=int )

        # If the returned clip is to be added to the image, it should
        #   be added to image[ymin:ymax, xmin:xmax].
        xmin = xc - stampwid // 2
        xmax = xc + stampwid // 2 + 1
        ymin = yc - stampwid // 2
        ymax = yc + stampwid // 2 + 1

        psfsamp = 1. / self._oversamp
        xs = np.array( np.arange( xmin, xmax ) )
        ys = np.array( np.arange( ymin, ymax ) )
        xsincarg = psfdex1d[:, np.newaxis] - ( xs - natxfrac - x ) / psfsamp
        xsincvals = np.sinc( xsincarg ) * np.sinc( xsincarg/4. )
        xsincvals[ ( xsincarg > 4 ) | ( xsincarg < -4 ) ] = 0.
        ysincarg = psfdex1d[:, np.newaxis] - ( ys - natyfrac - y ) / psfsamp
        ysincvals = np.sinc( ysincarg ) * np.sinc( ysincarg/4. )
        ysincvals[ ( ysincarg > 4 ) | ( ysincarg < -4 ) ] = 0.
        tenpro = np.tensordot( ysincvals[:, :, np.newaxis], xsincvals[:, :, np.newaxis], axes=0 )[ :, :, 0, :, :, 0 ]
        clip = ( self._data[:, np.newaxis, :, np.newaxis ] * tenpro ).sum( axis=0 ).sum( axis=1 )

        # Keeping the code below, because the code above is inpenetrable, and it's trying to
        #   do the same thing as the code below.
        # (I did emprically test it using the PSFs from the test_psf.py::test_psfex_rendering,
        #  and it worked.  In particular, there is not a transposition error in the "tenpro=" line;
        #  if you swap the order of yxincvals and xsincvals in the test, then the values of clip
        #  do not match the code below very well.  As is, they match to within a few times 1e-17,
        #  which is good enough as the minimum non-zero value in either one is of order 1e-12.)
        # clip = np.empty( ( stampwid, stampwid ), dtype=dtype )
        # for xi in range( xmin, xmax ):
        #     for yi in range( ymin, ymax ):
        #         xsincarg = psfdex1d - (xi-x) / psfsamp
        #         xsincvals = np.sinc( xsincarg ) * np.sinc( xsincarg/4. )
        #         xsincvals[ ( xsincarg > 4 ) | ( xsincarg < -4 ) ] = 0
        #         ysincarg = psfdex1d - (yi-y) / psfsamp
        #         ysincvals = np.sinc( ysincarg ) * np.sinc( ysincarg/4. )
        #         ysincvals[ ( ysincarg > 4 ) | ( ysincarg < -4 ) ] = 0
        #         clip[ yi-ymin, xi-xmin ] = ( xsincvals[np.newaxis, :]
        #                                      * ysincvals[:, np.newaxis]
        #                                      * psfbase ).sum()

        clip *= flux / clip.sum()

        return clip


class YamlSerialized_OversampledImagePSF( OversampledImagePSF ):

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

    def read( self, filepath ):
        y = yaml.safe_load( open( filepath ) )
        self._x = y['x']
        self._y = y['y']
        self._oversamp = y['oversamp']
        self._data = np.frombuffer( base64.b64decode( y['data'] ), dtype=y['dtype'] )
        self._data = self._data.reshape( ( y['shape0'], y['shape1'] ) )

    def write( self, filepath ):
        out = { 'x': float( self._x ),
                'y': float( self._y ),
                'oversamp': self._oversamp,
                'shape0': self._data.shape[0],
                'shape1': self._data.shape[1],
                'dtype': str( self._data.dtype ),
                # TODO : make this right, think about endian-ness, etc.
                'data': base64.b64encode( self._data.tobytes() ).decode( 'utf-8' ) }
        # TODO : check overwriting etc.
        yaml.dump( out, open( filepath, 'w' ) )


class ou24PSF( PSF ):
    # Currently, does not support any oversampling, because SFFT doesn't
    # TODO: support oversampling!

    def __init__( self, pointing=None, sca=None, config_file=None, size=201, include_photonOps=True, **kwargs ):
        if len(kwargs) > 0:
            SNLogger.warning( f"Unused arguments to ou24PSF.__init__: {[k for k in kwargs]}" )

        if ( pointing is None ) or ( sca is None ):
            raise ValueError( "Need a pointing and an sca to make an ou24PSF" )
        if ( size % 2 == 0 ) or ( int(size) != size ):
            raise ValueError( "Size must be an odd integer." )
        size = int( size )

        if config_file is None:
            config_file = Config.get().value( 'ou24psf.config_file' )
        self.config_file = config_file
        self.pointing = pointing
        self.sca = sca
        self.size = size
        self.include_photonOps = include_photonOps
        self._stamps = {}


    @property
    def stamp_size( self ):
        return self.size


    def get_stamp( self, x, y, flux=1., seed=None ):
        """Return a 2d numpy image of the PSF at the image resolution.

        Parameters are as in PSF.get_stamp, plus:

        Parameters
        ----------
          seed : int
            A random seed to pass to galsim.BaseDeviate for photonOps.
            NOTE: this is not part of the base PSF interface (at least,
            as of yet), so don't use it in production pipeline code.
            However, it will be useful in tests for purposes of testing
            reproducibility.

        """
        if (x, y) not in self._stamps:
            rmutils = roman_utils( self.config_file, self.pointing, self.sca )
            if seed is not None:
                rmutils.rng = galsim.BaseDeviate( seed )
            self._stamps[(x, y)] = rmutils.getPSF_Image( self.size, x, y,
                                                         include_photonOps=self.include_photonOps ).array
            self._stamps[(x, y)] *= flux / self._stamps[(x, y)].sum()
        return self._stamps[(x, y)]
