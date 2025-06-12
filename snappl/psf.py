# python standard library imports
import base64
import numbers
import pathlib

# common library imports
import numpy as np
import yaml

# astro library imports
import galsim
from roman_imsim.utils import roman_utils

# roman snpit library imports
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


    def get_stamp( self, x, y, x0=None, y0=None, flux=1. ):
        """Return a 2d numpy image of the PSF at the image resolution.

        (Aside: for all of this docstring, read "stamp", "clip", and
        "thumbnail" as synonyms.)

        INDEXING IMAGES
        ---------------

        For discussion of pixel positions below, remember the
        conventions for astronomical arrays.  Consider four points:

        First, in python, numpy arrays are 0-indexed.  That is, if you
        have a 3-element numpy array named arr, the first element of the
        array is arr[0], the second arr[1], and the last arr[2].  Some
        other languages (e.g. FORTRAN) assume 1-indexed arrays.  That
        is, the first element of FORTRAN array A is A[1], not A[0].
        This matters for us because we are using some astronomical
        formats that have been around since everybody spoke Latin and
        everybody programmed in FORTRAN, so there are some legacy
        conventions left over.  Some libraries (e.g. galsim) at least
        sometimes require you to specify array indexes (such as pixel
        positions) assuming 1-indexed arrays.  Be very careful and read
        lots of documentation!  If we've done it right, everything in
        snpit_utils and snappl uses standard python numpy 0-based array
        indexes, so you will hopefully not become confused.  What's more
        more, the astropy.wcs.WCS class also uses the convention of
        0-based arrays.  (However, be careful, because astropy.wcs has
        an alternate interface that uses the other convention.)

        Another place you will find 1-indexed arrays are in the WCSes
        defined in FITS headers, and in at least some FITS image display
        programs.  If you use ds9 (the standard FITS image display
        program), and hover your pointer over the center of the
        lower-left pixel, you will notice that it tells you it's at
        (1.0,1.0).  This means that if you're reading positions off of
        ds9, you always have to be careful to mentally convert when
        comparing to positions in your code!  Likewise, if you try to
        manually apply the WCS transformation from a FITS header (doing
        the matrix multiplication yourself, rather than relying on a
        snappl or astropy library), you have to make sure you're using
        1-offset pixel coordinates.  Generally, you will not have to
        worry about this; the WCS classes in snappl (just as in astropy)
        will internally take care of all these off-by-1 errors.  As
        stated above, all snappl classes assume 0-based array indexing.

        **If you find yourself manually correcting for 1-offset pixel
        positions in your code, there's a good chance you're doing it
        wrong.**

        Second, following how numpy arrays are indexed, the lower-left
        pixel of an astronomical image is at x=0, y=0.  Furthermore, by
        convention, the *center* of the lower-left pixel is at x=0.0,
        y=0.0.  That means that for a 512×512 image, the whole array
        spans (-0.5,-0.5) to (511.5,511.5); the lower-left corner of the
        array, which is the lower-left corner of the lower-left pixel,
        is at (-0.5,-0.5).

        Third, because numpy arrays are (by default) stored in "row
        major" format, their indexing is *backwards* from what we might
        expect.  That is, to get to pixel (x,y) on a numpy array image,
        you'd do image[y,x].

        Fourth, it follows that a pixel position whose fractional part
        is *exactly* 0.5 is right on the edge between two pixels.  For
        example, the position x=0.5, y=0.5 is the corner between the
        four lower-left-most pixels on the image.  If you want to ask
        for "the closest pixel center" in this case, there is an
        ambiguity, so we have to pick a convention; that convention is
        described below.

        PSF CENTERING FOR get_stamp
        ---------------------------

        If (x0, y0) are not given, the PSF will be centered as best
        possible on the stamp*.  So, if x ends in 0.8, it will be left
        of center, and if x ends in 0.2, it will be right of center.  If
        the fractional part of x or y is exactly 0.5, there's an
        ambituity as to where on the image you should place the stamp of
        the PSF.  The position of the PSF on the returned stamp will
        always round *down* in this case.  (The pixel on the image that
        corresponds to the center pixel on the clip is at
        floor(x+0.5),floor(y+0.5), *not* round(x+0.5),round(y+0.5).
        Those two things are different, and round is not consistent.
        round(i.5) will round up if i is odd, but down if i is even.
        This makes it very difficult to understand where your PSF is; by
        using floor(x+0.5), we get consistent results regardless of
        whether the integer part of x is even or odd.)

        For further discusison of centering, see the discusison of the
        (x0, y0) parameters below.

        * "The PSF will be centered as best possible on the stamp": this
          is only true if the PSF itself is intrinsically centered.  See
          OversampledImagePSF.create for a discussion of
          non-intrinsically-centered PSFs.

        Parameters
        ----------
          x, y: floats
            Position on the image of the center of the psf.  If not
            given, defaults to something sensible that was defined when
            the object was constructed.  If you want to do sub-pixel
            shifts, then the fractional part of x will (usually) not be
            0.

          x0, y0: int, default None
            The pixel position on the image corresponding to the center
            pixel of the returned PSF.  If either is None, they default
            to x0=floor(x+0.5) and y0=floor(y+0.5).  (See above for why
            we don't use round().)

            For example: if you call psfobj.get_stamp(111., 113.), and
            if the PSF object as a clip_size of 5, then you will get
            back an image that looks something like:

                   -----------
                   | | | | | |
                   -----------
                   | |.|o|.| |
                   -----------
                   | |o|O|o| |
                   -----------
                   | |.|o|.| |
                   -----------
                   | | | | | |
                   -----------

             the PSF is centered on the center pixel of the clip
             (i.e. 2,2), and that pixel should get placed on pixel
             (x,y)=(111,113) of the image for which you're rendering a
             PSF.  (Suppose you wanted to add this as an injected source
             to the image; in that case, you'd add the returned PSF clip
             to image[111:116,109:114] (remembering that numpy arrays of
             astronomical images using all the defaults that we use in
             this software are indexed [y,x]).)

             If you want an offset PSF, then you would use a different
             x0, y0.  So, if you call psfobj.get_stamp(111., 113.,
             x0=112, y0=114), you'd get back:

                   -----------
                   | | | | | |
                   -----------
                   | | | | | |
                   -----------
                   |.|o|.| | |
                   -----------
                   |o|O|o| | |
                   -----------
                   |.|o|.| | |
                   -----------

             In this case, center pixel of the returned stamp
             corresponds to pixel (x,y)=(112,114) on the image, but the
             PSF is supposed to be centered at (x,y)=(111,113).  So, the
             PSF is one pixel down and to the left of the center of the
             returned stamp.  If you wanted to add this as an injected
             source on to the image, you'd add the PSF clip to
             image[112:117,110:116] (again, remembering that numpy
             arrays are indexed [y,x]).

             If you call psfobj.get_stamp(111.5,113.5), then you'd get
             back something like:

                   -----------
                   | | | | | |
                   -----------
                   | |.|.| | |
                   -----------
                   |.|o|o|.| |
                   -----------
                   |.|o|o|.| |
                   -----------
                   | |.|.| | |
                   -----------

            Because your pixel position ended in (0.5, 0.5), the PSF is
            centered on the corner of the pixel.  The center of the clip
            (x,y)=(2,2) corresponds to (floor(111.5+0.5), floor(113.5+0.5))
            on the image, or (x,y)=(112,114).

            If you call psfobj.get_stamp(111.5, 113.5, x0=111, y0=113)
            then you'd get back a clip:

                   -----------
                   | | |.|.| |
                   -----------
                   | |.|o|o|.|
                   -----------
                   | |.|o|o|.|
                   -----------
                   | | |.|.| |
                   -----------
                   | | | | | |
                   -----------

           Finally, to belabor the point, a couple of more examples.  If
           you call psfobj.get_stamp(111.25, 113.0), you'd get back a
           clip with the peak of the psf at (x,y)=(2.25,2.0) on the
           thumbnail image, with the center pixel corresponding to
           (x,y)=(floor(111.25+0.5), floor(113.+0.5)), or (111,113).
           You would add it to image[111:116,109:114], and the stamp
           would look like:

                   -----------
                   | | | | | |
                   -----------
                   | | |o|.| |
                   -----------
                   | |.|O|o|.|
                   -----------
                   | | |o|.| |
                   -----------
                   | | | | | |
                   -----------

            If you call psfobj.get_stamp(111.25, 113.0, x0=110, y0=114),
            then you'd get a PSF back with the peak of the PSF on the
            clip at (x,y)=(3.5,1.0), the center pixel corresponding to
            (x,y)=(110,114) on the image, and a clip that looks like:

                   -----------
                   | | | | | |
                   -----------
                   | | | | | |
                   -----------
                   | | | |o|.|
                   -----------
                   | | |.|O|o|
                   -----------
                   | | | |o|.|
                   -----------


          flux: float, default 1.
             The sum of the PSF before it's rendered into the clip.  For
             some PSF subclasses, this is basically the same as saying
             "the sum of the returned clip is this".  However, if you
             have a non-zero (x0,y0) such that the natural size of the
             PSF slops off of the edge of the returned clip, those two
             things could easily be different.

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

        if psfclass == "A25ePSF":
            return A25ePSF( **kwargs )

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
        self._oversamp = None

    def get_stamp( self, x=None, y=None, x0=None, y0=None, flux=1. ):
        # (x, y) is the position on the image for which we want to render the PSF.
        x = float(x) if x is not None else self._x
        y = float(y) if y is not None else self._y

        # (x0, y0) is the position on the image that corresponds to the center of the clip
        #
        # For the defaults, round() isn't the right thing to use here,
        #   because it will behave differently when x - round(x) = 0.5
        #   based on whether floor(x) is even or odd.  What we *want* is
        #   for the psf to be as close to the center of the clip as
        #   possible (when x0 and y0 are None).  In the case where the
        #   fractional part of x is exactly 0.5, it's ambiguous what
        #   that means-- there are four places you could stick the PSF
        #   to statisfy that criterion.  By using floor(x+0.5), we will
        #   consistently have the psf leaning down and to the left when
        #   the fractional part of x (and y) is exactly 0.5, whereas
        #   using round would give different results based on the
        #   integer part of x (and y).
        x0 = int( np.floor(x + 0.5) ) if x0 is None else x0
        y0 = int( np.floor(y + 0.5) ) if y0 is None else y0

        if ( not isinstance( x0, numbers.Integral ) ) or ( not isinstance( y0, numbers.Integral ) ):
            raise TypeError( f"x0 and y0 must be integers; got x0 as a {type(x0)} and y0 as a {type(y0)}" )

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
        xmin = x0 - stampwid // 2
        xmax = x0 + stampwid // 2 + 1
        ymin = y0 - stampwid // 2
        ymax = y0 + stampwid // 2 + 1

        psfsamp = 1. / self._oversamp
        xs = np.arange( xmin, xmax )
        ys = np.arange( ymin, ymax )
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

        # Because the internally stored PSF sums to 1 (assuming
        # normlization), we need to rescale by self.oversample_factor
        # squared
        clip *= flux / ( self.oversampled_data.sum() / ( self.oversample_factor **2 ) )

        return clip


class YamlSerialized_OversampledImagePSF( OversampledImagePSF ):

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

    def read( self, filepath ):
        y = yaml.safe_load( open( filepath ) )
        self._x = y['x0']
        self._y = y['y0']
        self._oversamp = y['oversamp']
        self._data = np.frombuffer( base64.b64decode( y['data'] ), dtype=y['dtype'] )
        self._data = self._data.reshape( ( y['shape0'], y['shape1'] ) )

    def write( self, filepath ):
        out = { 'x0': float( self._x ),
                'y0': float( self._y ),
                'oversamp': self._oversamp,
                'shape0': self._data.shape[0],
                'shape1': self._data.shape[1],
                'dtype': str( self._data.dtype ),
                # TODO : make this right, think about endian-ness, etc.
                'data': base64.b64encode( self._data.tobytes() ).decode( 'utf-8' ) }
        # TODO : check overwriting etc.
        yaml.dump( out, open( filepath, 'w' ) )


class A25ePSF( YamlSerialized_OversampledImagePSF ):

    def __init__( self, band, sca, x, y, *args, **kwargs ):

        super().__init__( *args, **kwargs )

        cfg = Config.get()
        basepath = pathlib.Path( cfg.value( 'photometry.snappl.A25ePSF_path' ) )

        """
        The array size is the size of one image (nx, ny).
        The grid size is the number of times we divide that image
        into smaller parts for the purposes of assigning the
        correct ePSF (8 x 8 = 64 ePSFs).

        4088 px/8 = 511 px. So, int(arr_size/gridsize) is just a type
        conversion. In the future, we may have a class where these things
        are variable, but for now, we are using only the 8 x 8 grid of
        ePSFs from Aldoroty et al. 2025a. So, it's hardcoded.

        """
        arr_size = 4088
        gridsize = 8
        cutoutsize = int(arr_size/gridsize)
        grid_centers = np.linspace(0.5 * cutoutsize, arr_size - 0.5 * cutoutsize, gridsize)

        dist_x = np.abs(grid_centers - x)
        dist_y = np.abs(grid_centers - y)

        x_idx = np.argmin(dist_x)
        y_idx = np.argmin(dist_y)

        x_cen = grid_centers[x_idx]
        y_cen = grid_centers[y_idx]

        min_mag = 19.0
        max_mag = 21.5
        psfpath = ( basepath / band / str(sca) /
                    f'{cutoutsize}_{x_cen:.1f}_{y_cen:.1f}_-_{min_mag}_{max_mag}_-_{band}_{sca}.psf' )

        self.read(psfpath)


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


    def get_stamp( self, x, y, x0=None, y0=None, flux=1., seed=None ):
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

        xc = int( np.floor( x + 0.5 ) )
        yc = int( np.floor( y + 0.5 ) )
        x0 = xc if x0 is None else x0
        y0 = yc if y0 is None else y0
        if ( not isinstance( x0, numbers.Integral ) ) or ( not isinstance( y0, numbers.Integral ) ):
            raise TypeError( f"x0 and y0 must be integers; got x0 as a {type(x0)} and y0 as a {type(y0)}" )
        dx = xc - x0
        dy = yc - y0

        if ( dx > self.size ) or ( dy > self.size ):
            raise RuntimeError( "Can't offset PSF from the center by more than the stamp size." )
        
        if (x, y, dx, dy) not in self._stamps:
            # We want to get a psf size big enough that the subimage we're going
            #   to pull off will be completed in the rendered image.
            psfimsize = self.size + max( abs(dx), abs(dy) )
            psfimsize += 1 if psfimsize % 2 == 0 else 0

            rmutils = roman_utils( self.config_file, self.pointing, self.sca )
            if seed is not None:
                rmutils.rng = galsim.BaseDeviate( seed )

                # VERIFY THIS -- roman_imsim positions are 1-indexed, hence the +1 below
                psfim = rmutils.getPSF_Image( psfimsize, x+1, y+1,
                                              include_photonOps=self.include_photonOps ).array
                psfim *= flux / psfim.sum()

            if ( dx == 0 ) and ( dy == 0 ):
                self._stamps[(x, y, dx, dy)] = psfim
            else:
                xlow = psfimsize // 2 + dx - self.size // 2
                xhigh = x0 + self.size
                ylow = psfimsize // 2 + dy - self.size // 2
                yhigh = y0 + self.size
                self._stamps[(x, y, dx, dy)] = psfim[ ylow:yhigh, xlow:xhigh ]
                
        return self._stamps[(x, y)]
