# python standard library imports
import base64
import numbers
import pathlib

# common library imports
import numpy as np
import yaml

# astro library imports
import photutils.psf
import galsim
from roman_imsim.utils import roman_utils

# roman snpit library imports
from snpit_utils.config import Config
from snpit_utils.logger import SNLogger


class PSF:
    """Wraps a PSF.  All roman snpit photometry code will ideally only use PSF methods defined in this base class.

    This is an abstract base class; it can do almost nothing itself.  In
    practice, you need to instantiate a subclass.  Do that by calling
    the class method PSF.get_psf_object.

    """

    # Thought required: how to deal with oversampling.  Right now, the
    # OversampledImagePSF and photutilsImagePSF subclasses provide a
    # property or method to access the single internally stored
    # oversampled image.  Should there be a general interface for
    # getting access to oversampled PSFs?

    def __init__( self, called_from_get_psf_object=False, *args, **kwargs ):
        """Don't call this or the constructor of a subclass directly, call PSF.get_psf_object().

        See documentation on the various subclass constructors for the
        arguments to apss to get_psf_object and what they all mean.
        Different types of PSF need different arguments, and sometimes
        the same argument names will mean different things for different
        subclasses!

        """
        self._consumed_args = set()
        if not called_from_get_psf_object:
            raise RuntimeError( f"Don't instantiate a {self.__class__.__name__} directly, call PSF.get_psf_object" )
        self._consumed_args.add( 'called_from_get_psf_object' )

    def _warn_unknown_kwargs( self, kwargs ):
        if any( k not in self._consumed_args for k in kwargs ):
            SNLogger.warning( f"Unused arguments to {self.__class__.__name__}.__init__: "
                              f"{[k for k in kwargs if k not in self._consumed_args]}" )

    # This is here for backwards compatibility
    @property
    def clip_size( self ):
        return self.stamp_size

    @property
    def stamp_size( self ):
        """The size of the one side of a PSF image stamp at image resolution.  Is always odd."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement stamp_size." )


    def get_stamp( self, x=None, y=None, x0=None, y0=None, flux=1. ):
        """Return a 2d numpy image of the PSF at the image resolution.

        There are a distressing number of subtleties here, warranting an
        extended discussion.

        INDEXING IMAGES
        ---------------

        For discussion of pixel positions below, remember the
        conventions for astronomical arrays.  Consider four things:

        First thing to consider: in python, numpy arrays are 0-indexed.
        That is, if you have a 3-element numpy array named arr, the
        first element of the array is arr[0], the second arr[1], and the
        last arr[2].  Some other languages (e.g. FORTRAN) assume
        1-indexed arrays.  That is, the first element of FORTRAN array A
        is A[1], not A[0].  This matters for us because we are using
        some astronomical formats that have been around since everybody
        spoke Latin and everybody programmed in FORTRAN, so there are
        some legacy conventions left over.  Some libraries (e.g. galsim)
        at least sometimes require you to specify array indexes (such as
        pixel positions) assuming 1-indexed arrays.  Be very careful and
        read lots of documentation!  If we've done it right, everything
        in snpit_utils and snappl uses standard python numpy 0-based
        array indexes, so you will hopefully not become confused.
        What's more more, the astropy.wcs.WCS class also uses the
        convention of 0-based arrays.  (However, be careful, because
        astropy.wcs has an alternate interface that uses the other
        convention.)

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
        wrong.  snappl is supposed to take care of all of that.**

        Second thing to consider: following how numpy arrays are
        indexed, the lower-left pixel of an astronomical image is at
        x=0, y=0.  Furthermore, by convention, the *center* of the
        lower-left pixel is at x=0.0, y=0.0.  That means that for a
        512×512 image, the whole array spans (-0.5,-0.5) to
        (511.5,511.5); the lower-left corner of the array, which is the
        lower-left corner of the lower-left pixel, is at (-0.5,-0.5).

        Third thing to consider: because numpy arrays are (by default)
        stored in "row major" format, their indexing is *backwards* from
        what we might expect.  That is, to get to pixel (x,y) on a numpy
        array image, you'd do image[y,x].

        Fourth thing to consider: it follows that a pixel position whose
        fractional part is *exactly* 0.5 is right on the edge between
        two pixels.  For example, the position x=0.5, y=0.5 is the
        corner between the four lower-left-most pixels on the image.  If
        you want to ask for "the closest pixel center" in this case,
        there is an ambiguity, so we have to pick a convention; that
        convention is described below.

        PSF CENTERING FOR get_stamp
        ---------------------------

        If (x0, y0) are not given, the PSF will be centered as best
        possible on the stamp*†.  So, if x ends in 0.8, it will be left
        of center, and if x ends in 0.2, it will be right of center.  If
        the fractional part of x or y is exactly 0.5, there's an
        ambituity as to where on the image you should place the stamp of
        the PSF.  The position of the PSF on the returned stamp will
        always round *down* in this case.  (The pixel on the image that
        corresponds to the center pixel on the stamp is at
        floor(x+0.5),floor(y+0.5), *not* round(x+0.5),round(y+0.5).
        Those two things are different, and round is not consistent.
        round(i.5) will round up if i is odd, but down if i is even.
        This makes it very difficult to understand where your PSF is; by
        using floor(x+0.5), we get consistent results regardless of
        whether the integer part of x is even or odd.)

        For further discusison of centering, see the discusison of the
        (x0, y0) parameters below.

        * "The PSF will be centered as best possible on the stamp": this
          is only true if the PSF itself is intrinsically centered.
          It's possible that some subclasses will have
          non-intrinsically-centered PSFs.  See the documentation on the
          __init__ and get_stamp methods of those subclasses
          (e.g. OversampledImagePSF and photutilsImagePSF) to make sure
          you understand how each subclass handles those cases.  In all
          cases, get_stamp should return stamps that are consistent with
          the description in this docstring.  If a subclass does
          something different, that subclass is broken.

        † "Centered" is obvious when a PSF is perfectly radially
          symmetric: the center of the PSF is its peak, or mode.  If the
          PSF is not radially symmetric, then this becomes potentially
          ambiguous.  The "center" of the PSF really becomes a "fiducial
          point", and cannot be assumed to be the centroid or mode of
          the PSF (and the centroid and mode may well be different in
          this case).  Hopefully it's somewhere close.  If you use
          consistent PSFs, then *relative* positions should be
          realiable.  That is, if you do a PSF fit to an image to find
          positions of stars, and use the PSF positions of those stars
          with a WCS to find ra and dec, this will only work if you used
          the *same* PSFs to find the standard stars you used to solve
          for the WCS!  For most of this discussion, for simplicitly,
          we'll be assuming a radially symmetric PSF so that "peak" and
          "center" and "fiducial point" all mean the same thing.

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
            we don't use round().)  The peak* of the PSF on the returned
            stamp will be at (x-x0,y-y0) relative to the center pixel of
            the returned stamp.

               * "peak" assumes the PSF is radially symmetric.  If it's
                 not, by "peak" read "center" or "fiducial point".

            For example: if you call psfobj.get_stamp(111., 113.), and
            if the PSF object as a stamp_size of 5, then you will get
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

             the PSF is centered on the center pixel of the stamp
             (i.e. 2,2), and that pixel should get placed on pixel
             (x,y)=(111,113) of the image for which you're rendering a
             PSF.  (Suppose you wanted to add this as an injected source
             to the image; in that case, you'd add the returned PSF stamp
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
             returned stamp.  The peak of the PSF is at pixel
             (x-x0,y-y0)=(-1,-1) relative to the center of the stamp.
             If you wanted to add this as an injected source on to the
             image, you'd add the PSF stamp to image[112:117,110:116]
             (again, remembering that numpy arrays are indexed [y,x]).

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
            centered on the corner of the pixel.  The center of the stamp
            (x,y)=(2,2) corresponds to (floor(111.5+0.5), floor(113.5+0.5))
            on the image, or (x,y)=(112,114).

            If you call psfobj.get_stamp(111.5, 113.5, x0=111, y0=113)
            then you'd get back a stamp:

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
           stamp with the peak of the psf at (x,y)=(2.25,2.0) on the
           stamp image, with the center pixel corresponding to
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
            stamp at (x,y)=(3.5,1.0), the center pixel corresponding to
            (x,y)=(110,114) on the image, and a stamp that looks like:

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

            The peak of the PSF is at (x-x0,y-y0)=(1.25,-1.0) relative
            to the center of the returned stamp.

          flux: float, default 1.
             Ideally, the full flux of the PSF.  If your stamp is big
             enough, and the PSF is centered, then this will be the sum
             of the returned stamp image.  However, if some of the wings
             of the PSF are not captured by the boundaries of the PSF,
             then the sum of the returned stamp image will be less than
             this value.

        Returns
        -------
          2d numpy array

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_stamp" )

    @classmethod
    def get_psf_object( cls, psfclass, **kwargs ):
        """Return a PSF object whose type is specified by psfclass.

        SADNESS ALERT : currently the arguments you need to pass are
        different for different types of PSFs.  There may be no way
        around this, because they just all need different data.  To
        figure out what kwargs you need to pass to this function, look
        at the __init__ docstring for the class corresponding to the
        psfclass you're passing.

        Parameters
        ----------
          psfclass : str
             The name of the class of the PSF to instantiate.

          **kwargs : further keyword arguments passed to object constructor

        """
        if psfclass == "photutilsImagePSF":
            return photutilsImagePSF( called_from_get_psf_object=True, **kwargs )

        if psfclass == "OversampledImagePSF":
            return OversampledImagePSF( called_from_get_psf_object=True, **kwargs )

        if psfclass == "YamlSerialized_OversampledImagePSF":
            return YamlSerialized_OversampledImagePSF( called_from_get_psf_object=True, **kwargs )

        if psfclass == "A25ePSF":
            return A25ePSF( called_from_get_psf_object=True, **kwargs )

        if psfclass == "ou24PSF_slow":
            return ou24PSF_slow( called_from_get_psf_object=True, **kwargs )

        if psfclass == "ou24PSF":
            return ou24PSF( called_from_get_psf_object=True, **kwargs )

        raise ValueError( f"Unknown PSF class {psfclass}" )


class photutilsImagePSF( PSF ):
    def __init__( self, x=None, y=None, peakx=None, peaky=None,
                  oversample_factor=1, data=None, enforce_odd=True, normalize=False,
                  *args, **kwargs ):
        """Create a photutilsImagePSF.  WARNING: x and y have a different meaning from OversampledImagePSF constructor!

        Parmaeters
        ----------
          data : 2d numpy array
            The oversampled PSF.  data.sum() should be equal to the
            fraction of the PSF flux captured within the boundarys of
            the data array.  (However, see "normalize" below.)  The data
            array must be square, and (unless enforced_odd is false)
            must have an odd side length.

            The peak* of the PSF in the passed data array must be at
            position (peakx,peaky) in pixel coordinates of the passed
            data array.  If you leave those at default (None), then the
            PSF must be perfectly centered on the passed data array.
            (For an odd side-length, which is normal, that means the
            center of the PSF is at the center of the center pixel.)

               * For "peak" vs. "center" vs. "fiducial point", see the
                 caveats in the PSF.get_stamp docstring.

          oversample_factor: integer
            Must be an integer for photutilsImagePSF.  There are this
            many pixels along one axis in the past data array in one
            pixel on the original image that the PSF is for.

          peakx, peaky: float, float
            The position *in oversampled pixel coordinates* on the data
            array where the peak is found.  If these values are not,
            then we assume the peak is at (data.shape[1]//2,
            data.shape[0]//2) (i.e. the center of the center pixel).
            (If you pass an even-length data array, and there is no
            "center pixel", then expect everything to go wrong and the
            world to end.)  See (x, y) below for some examples of
            passing peakx and peaky.

            The safest thing to do is to leave peakx and peaky at their
            defaults of None and make sure that the PSF is centered on
            the passed data array.

          x, y : float, float
            Position on the original source image (i.e. the astronomical
            image for which this object is the PSF) that corresponds to
            the center of the data array.  WARNING: this is not the same
            as the x and y parameters given to the OversampledImagePSF
            constructor!  *If* the PSF is centered, and x and y have a
            zero fractional part, then the numbers will be the same for
            both classes.  But, for an off-center PSF, the numbers will
            be different in the two cases!  Use intrinsically off-center
            PSFs at your own peril.  (Note that you can always *render*
            stamps with off-centered PSFs in get_stamp(), regardless of
            whether the PSF itself is intrinsically centered or not.)

            Usually you want x and y to have no fractional part, you
            want peakx and peaky to be None, and you want the
            oversampled PSF to be centered on the passed data array.

            data must be consistent with these numbers.  Supposed you
            have an 11×11 PSF oversampled by a factor of 3 that is
            centered on the original image at 1023, 511.  In this case,
            the data array should be 33×33 in size (11 times 3).  If the
            PSF is centered on the data array (i.e. on the center of
            pixel (16,16)), then you would pass x=1023, y=511.

            If your PSF is centered on the original image at 1023.5,
            511.5, but you pass x=1023, y=511, that means that the PSF
            needs to be shifted half a pixel to the right and up on the
            (non-oversampled) stamp, or 1.5 pixels right and up on the
            oversampled data array.  The peak of the PSF on the passed
            data array should be at (17.5,17.5), and you must pass
            peakx=17.5 and peaky=17.5

            If your PSF is centered on the original image at 1023.,
            511., but for some reason you pass x=1020, y=512, that means
            that the center of the data array is three (non-oversampled)
            pixels to the left and one (non-oversampled) pixel above the
            peak of the PSF, or 9 oversampled left and 3 oversampled
            above.  In this case, the passed data array should have its
            peak (assuming a symmetric PSF) at the center of pixel
            (13,17), and you must pass peakx=13 and peaky=17.

            CHECK THESE NUMBERS IN THESE EXAMPLES TO VERIFY I DID IT RIGHT.

          enforce_odd: bool, default True
            Scream and yell if data doesn't have odd side-lengths.  You
            probably do not want to set this to False.

          normalize: bool, default False
            If this is True, then the constructor will divide data by
            data.sum() (WARNING: which modifies the passed array!).  Do
            this if you are very confident that, for your purposes,
            close enough to 100% of the PSF flux falls within the
            boundaries of the passed data array.  Better, ensure that
            the sum of the passed data array equals the fraction of the
            PSF flux that falls within its boundaries, and leave
            normalize to False.

        """
        super().__init__( *args, **kwargs )
        self._consumed_args.update( [ 'x', 'y', 'peakx', 'peaky', 'oversample_factor', 'data',
                                      'enforce_odd', 'normalize' ] )
        self._warn_unknown_kwargs( kwargs )

        self._x = x
        self._y = y

        # # If self._x or self._y aren't integers, then photutils is going
        # # to say that that is the coordinate that maps to the center of
        # # the center pixel of the ovsampled array.  That's different
        # # from our OversampledImagePSF convention, where the center of the center
        # # pixel of a image-scale sampled array is treated as
        # # ( int(floor(x+0.5)), int(floor(y+0.5)) ).  So, tell photutilsImagePSF
        # # that that is the reference point of the PSF, and I *think*
        # # it will all work out.
        # pux0 = np.floor( x + 0.5 )
        # puy0 = np.floor( y + 0.5 )

        if oversample_factor != int( oversample_factor ):
            raise ValueError( "For photUtilsImagePSF, oversample_factor must be an integer." )
        self._oversamp = int( oversample_factor )

        if data is None:
            raise ValueError( "Must pass data to construct a photutilsImagePSF" )
        if not isinstance( data, np.ndarray ) or ( len(data.shape) != 2 ) or ( data.shape[0] != data.shape[1] ):
            raise TypeError( "data must be a square 2d numpy array" )
        if enforce_odd and ( data.shape[0] % 2 != 1 ):
            raise ValueError( "The length of each axis of data must be odd" )

        if ( peakx is not None ) or ( peaky is not None ):
            # Actually, it *might* be implemented, but we need to write tests to
            #   make sure we did it right, so don't use it until we do that.
            raise NotImplementedError( "Non-default peakx/peaky not currently supported." )

        # If data.shape[1] is odd, then the center is data.shape[1] // 2   (if side is 5, center is at pixel 2.0)
        # If data.shape[1] is even, then the center is data.shape[1] / 2. - 0.5  (side 4, center at pixel 1.5 )
        # Both of these are equal to data.shape[1] / 2. - 0.5
        self._peakx = data.shape[1] / 2. - 0.5 if peakx is None else peakx
        self._peaky = data.shape[0] / 2. - 0.5 if peaky is None else peaky

        if normalize:
            data /= data.sum()

        self._data = data
        self._pupsf = photutils.psf.ImagePSF( data, flux=1, x_0=x, y_0=y, oversampling=self._oversamp )

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
        """The size of the PSF image stamp at image resolution.  Is always odd."""
        sz = int( np.floor( self.oversampled_data.shape[0] / self._oversamp ) )
        sz += 1 if sz % 2 == 0 else 0
        return sz

    def get_stamp( self, x=None, y=None, x0=None, y0=None, flux=1. ):
        """See PSF.get_stamp for documentation.

        --> CURRENTLY BROKEN FOR UNDERSAMPLED PSFs.  See Issue #30.

        Everything below is implementation notes, which can be ignored
        by people just using the class, but which will be useful for
        people reading the source code.

        photutils has a somewhat different way of thinking about PSF
        positioning on stamps than we do in OversampledImagePSF.  When
        you make an OversampledImagePSF, you give it the x and y on the
        original image where you evaluated the original PSF, and you
        give it an image with the PSF centered on the passed data array
        (or, within 0.5*oversampling_factor pixels of the center of the
        passed data array if the fractional parts of x and/or y are not
        0).

        In contrast, when you make a photutils ImagePSF, you pass it the
        x and y that correspond to the center pixel of the passed array.

        IF x and y have no fraction part, AND the PSF is centered on the
        passed data array, then you would pass the same values of x and
        y when constructing an OversampledImagePSF and a
        photutilsImagePSF.  Hopefully, this is the most common case, so
        confusion will be kept to a minimim.

        However, when that's not true, we have to make sure we interpret
        all the variables right when rendering a photUtilsImagePSF.

        According to the PSF.get_stamp documentation, if x0 and y0 are
        None, then you will always get a stamp with a PSF centered
        within 0.5 pixels of the center of the stamp; it will be offset
        from the center of the stamp by the fractional part of x and y.
        This means we can't just blithely pass the x and y passed to
        get_stamp on to the photutils.ImagePSF evaluator to get the PSF
        stamp, but have to do some arithmetic on it to make sure we'll
        get back what PSF.get_stamp promises.

        If x0 and y0 are passed to get_stamp here, then that is the
        position on the center of the original array that corresponds to
        the center of the returned stamp.  The peak of the PSF on the
        returned stamp needs to be at (x-x0,y-y0).



        """
        x = float(x) if x is not None else self._x
        y = float(y) if y is not None else self._y
        xc = int( np.floor( x + 0.5 ) )
        yc = int( np.floor( y + 0.5 ) )
        xfrac = x - xc
        yfrac = y - yc
        # ...gotta offset this if on a half-pixel because otherwise we're doing the floor twice
        xfrac -= 1. if xfrac == 0.5 else 0.
        yfrac -= 1. if yfrac == 0.5 else 0.

        # x0, y0 is position of the center pixel of the stamp.
        # If they're not passed, then we know we want the peak of the
        #   psf within 0.5 pixels of the center of the stamp,
        #   so adjust x and y to make that happen
        if x0 is None:
            x0 = int( np.floor( self._x + 0.5 ) )
            x = x0 + xfrac
        if y0 is None:
            y0 = int( np.floor( self._y + 0.5 ) )
            y = y0 + yfrac
        if ( not isinstance( x0, numbers.Integral ) ) or ( not isinstance( y0, numbers.Integral ) ):
            raise TypeError( f"x0 and y0 must be integers; got x0 as a {type(x0)} and y0 as a {type(y0)}" )

        # We want the peak of the PSF to be at (x-x0,y-y0) on the
        # returned stamp.  Our photutils.ImagePSF in self._pupsf thinks
        # that the center of self._data is at (self._x, self._y).  On the oversampled image,
        # the peak of the PSF is at (self._peakx, self._peaky).
        #
        # So.  Consider just the x axis.
        #
        # The pixel position of the center pixel of the returned array
        # we have to pass to photutils.ImagePSF.call() needs to be the
        # position of the peak minus (x-x0).  That will then put the
        # peak at (x-x0).  The position of the peak is self._x +
        # (self._peakx - (self._data.shape[1]/2 - 0.5))/oversample_factor.

        sz = self.stamp_size
        # // is scary.  -15 // 2 is 8, but -(15 // 2) is 7.  - here is not the same as * -1 !!!!!
        xvals = ( np.arange( -(sz // 2), sz // 2 + 1 )
                  + self._x + ( self._peakx - ( self._data.shape[1] / 2. - 0.5 ) ) / self.oversample_factor
                  - ( x - x0 ) )
        yvals = ( np.arange( -(sz // 2), sz // 2 + 1 )
                  + self._y + ( self._peaky - ( self._data.shape[0] / 2. - 0.5 ) ) / self.oversample_factor
                  - ( y - y0 ) )
        xvals, yvals = np.meshgrid( xvals, yvals )

        return self._pupsf( xvals, yvals ) * ( self.oversample_factor ** 2 )


class OversampledImagePSF( PSF ):
    """A PSF stored internally in an image which is (possibly) oversampled.

    get_stamp will then interpolate the internally stored oversampled
    image to get an source-image-scale sampled PSF using an
    interpolation algorithm that's close to what PSFex uses.

    BIG PROBLEM : the interpolation used does a very bad job when the
    PSF is intrnsically undersampled, that is, on the original image the
    FWHM is not at least a couple of pixels.  (TODO: explore how the
    algorithm does with PSFex-extracted PSFs on undersampled data, since
    the algorithm here was written for and tested with PSFex PSFs.)  See Issue #30.

    """

    def __init__( self, x=None, y=None, oversample_factor=1., data=None, enforce_odd=True, normalize=False,
                  *args, **kwargs ):
        """Make an OversampledImagePSF.

        Parameters
        ----------
          data: 2d numpy array or None
            The image data of the oversampled PSF.  If None, then this
            needs, somehow, to be set later.  (Usually that will be
            handled by something in a subclass of OversampledImagePSF;
            if you're setting it manually, you're probably doing
            something wrong.)  data.sum() should be equal to the
            fraction of the PSF flux captured within the boundaries of
            the data array.  (However, see "normalize" below.)  The
            array must be square, and unless enforce_odd is false, the
            length of one side must be an odd number.  Usually the peak
            of the PSF (assuming a symmetric PSF-- if not, replace
            "peak" with "center" or "fiducial point" or however you
            think about it) will be centered on the center pixel fo the
            array.  ALWAYS the peak of the PSF must be centered within
            0.5 *non-oversampled* pixels of the center of the array.
            (That is, if the oversampling factor is 3, the peak of the
            PSF will be centered within 1.5 pixels of the center of the
            passed array.)  See (x,y) below for discussion of
            positioning the PSF on the passed data array.  WARNING : if
            you set normalize to True, the passed array will be
            modified!

          oversample_factor: float, default 1.
            There are this many pixels along one axis in data for one
            pixel in the original image.  Doesn't have to be an integer
            (e.g. if you used PSFex to find the PSF, it usually won't
            be— though if you used PSFex to find the PSF, really we
            should be writing a subclass to handle that!).

          x, y: float
            Required.  Position on the source image where this PSF is
            evaluated.  Most of the time, but not always, you probably
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

            Note that for off-centered PSFs (meaning the PSF is not
            centered on the passed data array), the meaning of (x, y) in
            this constructor is *different* from the meaning of (x, y)
            in the photutilsImagePSF constructor.  Use intrinsically
            off-center PSFs at your own peril.  (Note that you can
            always *render* stamps with off-centered PSFs in
            get_stamp(), regardless of whether the PSF itself is
            intrinsically centered or not.)

          enforce_odd: bool, default True
            Enforce the requirement that the data array have an odd length along each axis.

          normalize: bool, default False
            Ignored if data is not None.  If True, then this constructor
            will make sure that data sums to 1 (modifying the passed
            data array in so doing!).  If you think that the data array
            is big enough that you're effectively capturing 100% of the
            PSF flux, then you should set normalize to True.  If not,
            then you should make sure that the data array you pass sums
            to the fraction of the PSF flux that you're passing, and set
            normalize to False.  Usually you don't want to change this,
            and you want to trust subclases to do the Right Thing.

        Returns
        -------
          object of type cls

        """

        super().__init__( *args, **kwargs )
        self._consumed_args.update( [ 'x', 'y', 'oversample_factor', 'data', 'enforce_odd', 'normalize' ] )
        self._warn_unknown_kwargs( kwargs )

        # TODO : implement enforce_odd
        # TODO : enforce square

        self._data = None
        if data is not None:
            if not isinstance( data, np.ndarray ) or ( len(data.shape) != 2 ) or ( data.shape[0] != data.shape[1] ):
                raise TypeError( "data must be a square 2d numpy array" )
            if enforce_odd and ( data.shape[0] % 2 != 1 ):
                raise ValueError( "The length of each axis of data must be odd" )
            if normalize:
                data /= data.sum()
            self._data = data

        if ( x is None ) or ( y is None ):
            raise ValueError( "Must supply both x and y" )
        self._x = float( x )
        self._y = float( y )

        self._oversamp = oversample_factor


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
        """The size of the PSF image stamp at image resolution.  Is always odd."""
        sz = int( np.floor( self.oversampled_data.shape[0] / self._oversamp ) )
        sz += 1 if sz % 2 == 0 else 0
        return sz


    def get_stamp( self, x=None, y=None, x0=None, y0=None, flux=1. ):
        """See PSF.get_stamp for documentation

        --> CURRENTLY BROKEN FOR UNDERSAMPLED PSFs.  See Issue #30.

        """
        # (x, y) is the position on the image for which we want to render the PSF.
        x = float(x) if x is not None else self._x
        y = float(y) if y is not None else self._y

        # (x0, y0) is the position on the image that corresponds to the center of the stamp
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

        # Interpolate the PSF using Lanczos resampling:
        #     https://en.wikipedia.org/wiki/Lanczos_resampling
        #
        # We use this because it's what PSFex uses; see Chapter 5, "How
        #   PSFEx Works", of the PSFEx manual
        #     https://psfex.readthedocs.io/en/latest/Working.html
        # That's also where the factor a=4 comes from
        a = 4

        psfwid = self.oversampled_data.shape[0]
        stampwid = self.stamp_size

        psfdex1d = np.arange( -( psfwid//2), psfwid//2+1, dtype=int )

        # If the returned stamp is to be added to the image, it should
        #   be added to image[ymin:ymax, xmin:xmax].
        xmin = x0 - stampwid // 2
        xmax = x0 + stampwid // 2 + 1
        ymin = y0 - stampwid // 2
        ymax = y0 + stampwid // 2 + 1

        psfsamp = 1. / self._oversamp
        xs = np.arange( xmin, xmax )
        ys = np.arange( ymin, ymax )
        xsincarg = psfdex1d[:, np.newaxis] - ( xs - natxfrac - x ) / psfsamp
        xsincvals = np.sinc( xsincarg ) * np.sinc( xsincarg/a )
        xsincvals[ ( xsincarg > a ) | ( xsincarg < -a ) ] = 0.
        ysincarg = psfdex1d[:, np.newaxis] - ( ys - natyfrac - y ) / psfsamp
        ysincvals = np.sinc( ysincarg ) * np.sinc( ysincarg/a )
        ysincvals[ ( ysincarg > a ) | ( ysincarg < -a ) ] = 0.
        tenpro = np.tensordot( ysincvals[:, :, np.newaxis], xsincvals[:, :, np.newaxis], axes=0 )[ :, :, 0, :, :, 0 ]
        clip = ( self.oversampled_data[:, np.newaxis, :, np.newaxis ] * tenpro ).sum( axis=0 ).sum( axis=1 )

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

        # We're assuming that the stored PSF data is properly
        # normalized, i.e. its sum is equal to the fraction of the PSF
        # flux captured by the boundaries of self.oversampled_data.  (The
        # documentation of the create method tells you to do things this
        # way.)  For a large enough size of self.oversampled_data, this means we
        # expect its sum to be 1.
        #
        # We do need to multiply by the oversampling factor squared to get it right.
        # (We store the oversampled PSF image normalized, i.e. if all the PSF
        # flux is included then the oversampled PSF image sums to 1.)
        clip *= flux * ( self.oversample_factor ** 2 )

        return clip


class YamlSerialized_OversampledImagePSF( OversampledImagePSF ):
    """An OversampledImagePSF with a definfed serialization format.

    Call read() to load and write() to save.

    The format is a yaml file.  At the base of the yaml is a dictionary with six keys:

    x0 : float.  The x position on the array where the psf was
         evaluated.  This should probably have been called "x" not "x0",
         because it matches the "x" parameters, not the "x0" parameter,
         to get_stamp, but oh well.

    y0 : float.  The y position on the array where the psf was
         evaluated.  Likewise, would be better called "y", but oh well.

    shape0 : int.  The shape of the array to read is (shape0, shape1),
             so shape0 is the y-size of the oversampled psf thumbnail,
             and shape1 is the x-size.  Probably shape0 and shape1
             should be the same, as there is probably code elsewhere
             that assumes square thumbnails!

    shape1 : int.  See above.

    dtype : str.  The numpy datatype of the data array.  WORRY ABOUT ENDIANNESS.

    data : str.  Base-64 encoded flattend data array.  (Because yaml is
           a text format, not a binary format, we take the 25% size hit
           here to make sure it's all ASCII and won't cause everybody to
           get all confused and start running around screaming and
           waving their hands over their heads.)

    """

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )
        self._warn_unknown_kwargs( kwargs )

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
                'shape0': self.oversampled_data.shape[0],
                'shape1': self.oversampled_data.shape[1],
                'dtype': str( self.oversampled_data.dtype ),
                # TODO : make this right, think about endian-ness, etc.
                'data': base64.b64encode( self.oversampled_data.tobytes() ).decode( 'utf-8' ) }
        # TODO : check overwriting etc.
        yaml.dump( out, open( filepath, 'w' ) )


class A25ePSF( YamlSerialized_OversampledImagePSF ):
    """A YamlSerialaled_OversampledImagePSF using the Aldoroty 2025 paper PSF.

    This is just a wrapper aorund YamlSerializd_OversarmpledPSF that knows how to
    find the right PSFs for a given band and sca.

    """

    def __init__( self, band, sca, x, y, *args, **kwargs ):
        super().__init__( x=x, y=y, *args, **kwargs )
        self._consumed_args.update( [ 'band', 'sca', 'x',' y' ] )
        self._warn_unknown_kwargs( kwargs )

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


class ou24PSF_slow( PSF ):
    """Wrap the roman_imsim PSFs.

    Each time you call get_stamp it will render a new one, with all the
    photon ops and so forth.  This is why it's called "_slow".  Look at
    ou24PSF for something that only does the photonops stuff once.

    (An object of this class will cache, so if you call get_stamp with
    identical arguments it will return the cached version).

    Currently, does not support any oversampling, because SFFT doesn't #
    TODO: support oversampling!

    """

    def __init__( self, pointing=None, sca=None, sed=None, config_file=None,
                  size=201, include_photonOps=True, n_photons=1000000, **kwargs
                 ):
        super().__init__( **kwargs )
        self._consumed_args.update( [ 'pointing', 'sca', 'sed', 'config_file',
                                      'size', 'include_photonOps', 'n_photons' ] )
        self._warn_unknown_kwargs( kwargs )

        if ( pointing is None ) or ( sca is None ):
            raise ValueError( "Need a pointing and an sca to make an ou24PSF_slow" )
        if ( size % 2 == 0 ) or ( int(size) != size ):
            raise ValueError( "Size must be an odd integer." )
        size = int( size )

        if sed is None:
            SNLogger.warning( "No sed passed to ou24PSF_slow, using a flat SED between 0.1μm and 2.6μm" )
            self.sed = galsim.SED( galsim.LookupTable( [1000, 26000], [1, 1], interpolant='linear' ),
                              wave_type='Angstrom', flux_type='fphotons' )
        elif not isinstance( sed, galsim.SED ):
            raise TypeError( f"sed must be a galsim.SED, not a {type(sed)}" )
        else:
            self.sed = sed

        if config_file is None:
            config_file = Config.get().value( 'ou24psf.config_file' )
        self.config_file = config_file
        self.pointing = pointing
        self.sca = sca
        self.size = size
        self.sca_size = 4088
        self.include_photonOps = include_photonOps
        self.n_photons = n_photons
        self._stamps = {}


    @property
    def stamp_size( self ):
        return self.size


    def get_stamp( self, x=None, y=None, x0=None, y0=None, flux=1., seed=None ):
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

        # If a position is not given, assume the middle of the SCA
        #   (within 1/2 pixel; by default, we want to make x and y
        #   centered on a pixel).
        x = x if x is not None else float( self.sca_size // 2 )
        y = y if y is not None else float( self.sca_size // 2 )

        xc = int( np.floor( x + 0.5 ) )
        yc = int( np.floor( y + 0.5 ) )
        x0 = xc if x0 is None else x0
        y0 = yc if y0 is None else y0
        if ( not isinstance( x0, numbers.Integral ) ) or ( not isinstance( y0, numbers.Integral ) ):
            raise TypeError( f"x0 and y0 must be integers; got x0 as a {type(x0)} and y0 as a {type(y0)}" )
        stampx = self.stamp_size // 2 + ( x - x0 )
        stampy = self.stamp_size // 2 + ( y - y0 )

        if ( ( stampx < -self.stamp_size ) or ( stampx > 2.*self.stamp_size ) or
             ( stampy < -self.stamp_size ) or ( stampy > 2.*self.stamp_size ) ):
            raise ValueError( f"PSF would be rendered at ({stampx},{stampy}), which is too far off of the "
                              f"edge of a {self.stamp_size}-pixel stamp." )

        if (x, y, stampx, stampy) not in self._stamps:
            rmutils = roman_utils( self.config_file, self.pointing, self.sca )
            if seed is not None:
                rmutils.rng = galsim.BaseDeviate( seed )

            # It seems that galsim.ChromaticObject.drawImage won't function without stamp having
            # a wcs.  Without a WCS, the stamp was coming out all zeros.
            # TODO : does rmutils.getLocalWCS want 1-indexed or 0-indexed coordinates???
            wcs = rmutils.getLocalWCS( x+1, y+1 )
            stamp = galsim.Image( self.stamp_size, self.stamp_size, wcs=wcs )
            point = ( galsim.DeltaFunction() * self.sed ).withFlux( flux, rmutils.bpass )
            # TODO : make sure that rmutils.getPSF wants 1-indexed positions (which we assume here).
            # (This is not that big a deal, because the PSF is not going to vary significantly
            # over 1 pixel.)
            photon_ops = [ rmutils.getPSF( x+1, y+1, pupil_bin=8 ) ]
            if self.include_photonOps:
                photon_ops += rmutils.photon_ops

            # Note the +1s in galsim.PositionD below; galsim uses 1-indexed pixel positions,
            # whereas snappl uses 0-indexed pixel positions
            center = galsim.PositionD(stampx+1, stampy+1)
            # Note: self.include_photonOps is a bool that states whether we are
            #  shooting photons or not, photon_ops is the actual map (not sure
            #  if that's the correct word) that describes where the photons 
            # should be shot, with some randomness.
            if self.include_photonOps:
                point.drawImage( rmutils.bpass, method='phot', rng=rmutils.rng, photon_ops=photon_ops,
                              n_photons=self.n_photons, maxN=self.n_photons, poisson_flux=False,
                              center=center, use_true_center=True, image=stamp )

            else:
                psf = galsim.Convolve(point, photon_ops[0])
                psf.drawImage(rmutils.bpass, method="no_pixel", center=center,  
                              use_true_center=True, image=stamp, wcs=wcs)
                
            self._stamps[(x, y, stampx, stampy)] = stamp.array

        return self._stamps[(x, y, stampx, stampy)]


# TODO : make a ou24PSF that makes an image and caches... when things are working better
class ou24PSF( ou24PSF_slow ):
    pass

# class ou24PSF( OversampledImagePSF ):
#     """An OversampledImagePSF that renders its internally stored image from a galsim roman_imsim PSF.

#     Use this just like you use an OversampledImagePSF.  However, to construct one, you need to give
#     it a pointing and an SCA from the OpenUniverse2024 sims.  It will only work if all that OU2024
#     data is available on disk.

#     """

#     def __init__( self, x=2044., y=2044., oversample_factor=5, oversampled_size=201,
#                   pointing=None, sca=None, sed=None, config_file=None,
#                   include_photonOps=True, n_photons=1000000, seed=None,
#                   **kwargs ):
#         """Construct an ou24PSF.

#         Will render an image oversampled by oversample_factor and save
#         it internally.  Thereafter, get_stamp will just interpolate and
#         resample this image.  This should be faster than re-rendering a
#         galsim PSF every time.

#         Parameters
#         ----------
#           x, y : float
#             Position on the SCA where to evalute the PSF.  Will use (2044, 2044) if not passed.

#           oversample_factor: int (or float?), default 5
#             The once-generated, interally-stored PSF image will be
#             oversampled by this factor.  You probably want this to be an
#             odd integer so that the center of the PSF is not ambiguous.
#             TODO: experiment with different oversample_factors to figure
#             out what the smallest oversampling we can get away with is.

#           oversampled_size: int, default 201
#             The size of a stamp in image pixels on the image for which
#             this is the PSF.  Must be an odd integer.  The stamp you get
#             from get_stamp will have size
#             floor(oversampled_size/oversample_factor), though the size
#             will be increated by one if it would come out to an even
#             number.  (So get_stamp will always return a stamp with an
#             odd side length.)

#             The default of oversampled_size=201 and oversample_factor=5
#             will yield a 41-pixel stamp from get_stamp (since 201/5 =
#             40.2, the floor of which is 40, which is even, so 1 is added
#             to make it an odd 41).

#             (You can read a psf object's stamp_size property to figure
#             out what size of a stamp you'll get when you run
#             get_stamp().)

#           pointing: int
#             Required.  The OpenUniverse2024 pointing.

#           sca: int
#             Required.  The SCA.

#           sed: galsim.SED
#             The SED to render the PSF for.  If not given, will use a flat SED.

#           config_file: str or Path
#             The OU2024 config file that tells it where to find all of
#             its images and so forth.  Usually you don't want to pass
#             this, in which case it will use the ou24psf.config_file
#             config value.

#           include_photonOps: bool, default True
#             TODO

#           n_photons: int, default 1000000
#             Number of photons with photon ops

#           seed: int, default None
#             If given, use this random seed when generating the
#             internally stored oversampled psf image.  Usually you
#             probably want this to be None (and if you don't leave it at
#             None, you may be repeating an error that was made in the
#             OU2024 simulations...), but pass an integer for tests if you
#             need precise reproducibility.

#         """
#         super().__init__( x=x, y=y, oversample_factor=oversample_factor, **kwargs )
#         self._warn_unknown_kwargs( kwargs )

#         if self._data is not None:
#             raise ValueError( "Error, do not pass data when constructing an ou24PSF" )

#         if ( pointing is None ) or ( sca is None ):
#             raise ValueError( "Need a pointing and an sca to make an ou24PSF" )
#         if ( oversampled_size % 2 == 0 ) or ( int(oversampled_size) != oversampled_size ):
#             raise ValueError( "Size must be an odd integer." )
#         oversampled_size = int( oversampled_size )

#         if sed is None:
#             SNLogger.warning( "No sed passed to ou24PSF, using a flat SED between 0.1μm and 2.6μm" )
#             self.sed = galsim.SED( galsim.LookupTable( [1000, 26000], [1, 1], interpolant='linear' ),
#                               wave_type='Angstrom', flux_type='fphotons' )
#         elif not isinstance( sed, galsim.SED ):
#             raise TypeError( f"sed must be a galsim.SED, not a {type(sed)}" )
#         else:
#             self.sed = sed

#         if config_file is None:
#             config_file = Config.get().value( 'ou24psf.config_file' )
#         self.config_file = config_file
#         self.pointing = pointing
#         self.sca = sca
#         self.oversampled_size = oversampled_size
#         self.sca_size = 4088
#         self.include_photonOps = include_photonOps
#         self.n_photons = n_photons
#         self.seed = seed

#     @property
#     def oversampled_data( self ):
#         if self._data is None:
#             # Render the oversampled PSF
#             x = self._x
#             y = self._y
#             stampx = self.oversampled_size // 2
#             stampy = self.oversampled_size // 2

#             rmutils = roman_utils( self.config_file, self.pointing, self.sca )
#             if self.seed is not None:
#                 rmutils.rng = galsim.BaseDeviate( self.seed )
#             wcs = rmutils.getLocalWCS( x+1, y+1 )
#             wcs = galsim.JacobianWCS(dudx=wcs.dudx / self.oversample_factor,
#                                      dudy=wcs.dudy / self.oversample_factor,
#                                      dvdx=wcs.dvdx / self.oversample_factor,
#                                      dvdy=wcs.dvdy / self.oversample_factor)
#             stamp = galsim.Image( self.oversampled_size, self.oversampled_size, wcs=wcs )
#             point = ( galsim.DeltaFunction() * self.sed ).withFlux( 1., rmutils.bpass )
#             photon_ops = [ rmutils.getPSF( x+1, y+1, pupil_bin=8 ) ]
#             if self.include_photonOps:
#                 photon_ops += rmutils.photon_ops

#             point.drawImage( rmutils.bpass, method='phot', rng=rmutils.rng, photon_ops=photon_ops,
#                              n_photons=self.n_photons, maxN=self.n_photons, poisson_flux=False,
#                              center=galsim.PositionD( stampx+1, stampy+1 ), use_true_center=True,
#                              image=stamp )
#             self._data = stamp.array

#         return self._data
