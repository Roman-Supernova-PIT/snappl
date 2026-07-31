import numbers

from snappl.dbclient import SNPITDBClient
from snappl.image import Image
from snappl.provenance import Provenance
from snappl.logger import SNLogger
from snappl.utils import asUUID


class Zeropoint:
    """A class encapsulating a zeropoint.

    So that we are very clear what we mean by zeropoint, this is the definition.

    First, imagine that you have an Image (i.e., an object of the class
    defined in image.py).  That image's data property is a
    two-dimensional array of floats.  Define "DAV" (for "data array
    value") as the units of that two dimensional array.  To highlight
    this:

       THE DAV IS THE UNIT OF THE NUMBERS WE GET IN THE DATA ARRAY

    Whatever that actually is.  Importantly, this definition is agnostic
    as to whether the data array represents something like "counts" or
    "counts per second" or whatever else.  It is just "what we get in
    the data array".  All of the definitions below are based on this.

    Second, imagine that we have a series of astronomical sources
    (stars, to make it concrete), and we have images of those stars
    taken by the telescope.  Although this is not definitional, we are
    going to assume that the number of DAVs in the Image.data array is
    proportional to the number of photons that entered the telescope's
    aperture.  (Let's assume that our thought-experiment stars are not
    at all variable, so it doesn't matter if we're talking about the
    number of photons that entered the aperture during the time of the
    exposure, or per second.)  In reality, diffraction and electronic
    effects will mean that some of the light energy that entered the
    telescope aperture will miss the detector, but for now, let's assume
    that that is negligible.  Also, for definitional purposes, assume
    that there are absolutely no astronomical sources contributing to
    the light of hitting the detector than the star we're currently
    pointing at.

    For purposes of definition, at the moment assume that the starlight
    is 100% monochromatic.  We'll relax this later (see COLOR TERMS
    below), but for right now, that assumption lets us not worry about
    whehter we're talking about energy or photons, as it's just a single
    constant factor of hc/λ that converts between the two.

    Third, when we divide the image into pixels, we want the gain of
    every pixel to be exactly the same.  Again, this sounds like a
    simple thing to say, but reality makes it more complicated.  So, to
    start, let's assume that each pixel on the detector has exactly the
    same area A_pix.  Let's assume that there are no electronic effects
    that cause photoelectrons to redirect to different neighboring
    pixels based on how full pixel wells currently are.  Let's assume
    that every pixel has exactly the same quantum efficiency.  To the
    extent that these assumptions are not true, see CORRECTING FOR PIXEL
    RESPONSE below.

    Fourth, let's assume that all backgrounds (i.e., light from anything
    other than the one star we're looking at) has been subtracted from
    the image.

    Under these assumptions, we define the zeropoint zp to be::

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
    preprocessing has been done to the image by the time we receive it.
    Neglecting all issues of pixel area, that means pixel-to-pixel gain
    variables have been corrected by flatfielding, so the same zeropoint
    applies to every pixel on the image.

    PIXEL AREA ISSUE

    Ideally, differences in pixel area would have been corrected before
    we receive the images.  Alas, it sounds like this will not be the
    case for the L2 images we will get from the SOC.  This is going to
    make everything more complicated.

    Because we cannot assume that each pixel maps to exactly the same
    angular area on the sky, and because the SOC's L2 processing is
    leaveing things in units of "per steradian" rather than correcting
    that out (i.e. they are giving us surface brightness, not
    brightness, which is maybe more like what you'd want for doing
    galaxy morphology stuff, but not what you want for measuing point
    sources), everything is going to be more complicated.

    Practically speaking, we're going to HOPE that pixel area as a
    function of positoin on the detector is a smooth function.  We can
    then replace zp with zp(x,y), where x,y is a pixel position on the
    detector, and it will be preceise enough as long as we get x, y
    wihin ± a few.

    This is just purgely optical/geometric effects.  For electronic
    effects, espeically ones that depend on how full the well is, we
    cannot provide a class that gives you the zeropoint as a property of
    image and position on image.  Something further has to be done to
    the image, or to measurements on the image, to take those effects
    out.  (Thushara, save us!)

    ACTUAL PHOTOMETRY

    Importantly, the zeropoint we've defined here DOES NOT take into
    account any aperture size, nor does it take into account any
    particular realization of a PSF.  It is a property *of the image*,
    not of the method used to extract photometry.  That means to use
    this zeropoint:

       * Aperture photometry values must be properly "aperture
         corrected" before the DAVs are fed into the zeropoint formula.
         Ideally, when things aren't too complicated, this correction is
         just a single factor that multiplies the number of DAVs in the
         aperture to give an effective "infinite aperture" number of
         DAVs.  This factor will, of course, be different for apertures
         of different sizes (and shapes), and will also in principle be
         different at different positions on a detector array.  (For
         small apertures, it's also very difficult to do right.)

       * PSF (or PRF) photometry must use PSFs (or PRFs) that are
         properly normalized to fit the defintion here.  The PSFs
         derived from psf.py::PSF are *supposed to be* normalized this
         way.  What this means is that in practice, if you call the
         get_stamp method of a PSF object, and the PSF object is
         instantiated so that the stamp size is infinite, the sum of the
         values in the stamp is 1.  In reality, of course you can't get
         back an infite 2d array, so the sum of the values in the stamp
         will be something less than 1, though for a big enough stamp
         very close to 1.

         IT IS POSSIBLE that some further calibration post-processing of
         photometry after the zeropoint is applied may be entirely
         convolved with the definition of the PSF.  At the moment,
         snappl's class structure does not support this, but we will
         adapt if necessary.  However, we should ONLY adapt if it really
         is necessary! If it's just a matter of normalizing your PSFs
         differently, then just normalize them differently to fit our
         definitions!

    COLOR TERMS

    In reality, astronomical sources are not monochromatic.  The
    defintion of AB magnitude provides us with a reference spectral
    energy defintion, i.e., one with a constant f_ν (in units of Energy
    per Time per Frequency Binwidth per Collecting Area).

    The detector is going to have some spectral response D(ν), which we
    will define "the number of DAVs detected per frequency bin for
    light of frequency ν for a source with f(ν)=3631 Jy".  [ASIDE: I say
    "detector response", but really I mean "detector + filter response",
    or, really really, "system response".]  This means that D(ν) has
    units of s (or, more clearly, Hz⁻¹) (or, maybe, if you don't think
    of DAVs as dimensionless, units of DAV/Hz).  The actual light
    source is going to have some SED S(ν) (in units of Energy/Time/Flux
    Binwidth/Area).

    The total number of DAVs detected, therefore, is::

        DAVs = ∫ S(ν) D(ν) / (3631Jy) dν

    (Presumably D(ν) goes to zero outside some finite range of ν so we
    don't have to think about infinite numbers.)

    Under this definition, the zeropoint is defined as::

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

    Where it gets painful is when S(ν) is not constant with ν.  In this
    case, the magnitude you will calculate from the zeropoint would be::

      m_calc = -2.5 log10( DAVs ) + zp
             = -2.5 log10( ∫ S(ν) D(ν) / (3631Jy) dν ) + 2.5 log10( ∫ D(ν) dν )

    but the true AB magnitude is ill-defined, because it's different for
    every ν!  So, for a given filter, we have to define a fiducial
    frequency ν₀ (which corresponds to a fiducial wavelength λ₀ by the
    usual ν₀=hc/λ₀).  We could then define the "true" magnitude of the object with SED S(ν) as::

      m = -2.5 log10( S(ν₀) / 3631 Jy )

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

    Every object will need to calculate its own cor_sed once it has an
    estimate of the shape of its SED to get its "true" magnitude... with
    the understanding that this "true" magnitude is defined for ν₀.
    (Note that you don't need to know S(ν), you only need to know
    S(ν)/S(ν₀), which is why I say you need to estimate the "shape of
    its SED", not "its SED".  But, you *also* need to know the detector
    (plus filter) response D(ν) to calculate these.  Probably we should
    come up with low-order approximations so that we can iteratively use
    our actual measurements in place of theoretical knowledge of S(ν).)

    I think all the Roman filters have a defined fiducial wavelength, so
    we should just use that for ν₀, but we need to document it somewhere
    if we ever start tabulating these color terms.

    HOW THIS CLASS WORKS

    The class is instantiated with an Image, and the value of the
    zeropoint and uncertainly on the zeropoint *at the center of the
    image*.  (That is, if the image is nx×ny, the zeropoint is at pixel
    position ((nx-1)/2., (ny-1)/2.), assuming 0-center-indexed pixels.)

    However, usually, you don't want to instantiate the class directly!
    Instead, you want to call the get_zeropoint() class method.  That
    will give you an object of the right subtype, assuming you pass the
    right things to it.

    To get a zeropoint, you call the method zp(x, y) (and maybe dzp(x,
    y)), where you give the pixel position (x, y) on the image where you
    want the zeropoint.

    Color corrections are *not* stored here, because the Zeropoint is a
    property of the just image, whereas the color correction is a
    property of the object and the detector, filter, telescope.  In
    terms of the definitions about, color correction depends on D(ν) and
    S(ν), whereas zeropoint only depends on D(ν).  (Actually, color
    correction is a property of object observed, detector, filter,
    telescope, object being observed, *and image*, because D(ν) probably
    changes over time!)

    """

    @classmethod
    def get_zeropoint( cls, image=None, provenance=None, provenance_tag=None, process=None,
                      zp=None, dzp=None, meta=None, subclass=None, id=None ):
        """Get a Zeropoint object (or an object of a Zeropoint subclass).

        Must specify one of:
           id
           image, provenance
           image, provenance_tag, process
           image, params
           image, zp, dzp
           image, zp, dzp, meta, subclass

        Parameters
        ----------
          image : UUID or Image (or Image subclass) or None
            The Image that this is the zeropoint for.  If this is a UUID, it's assumed that this
            is an Image that can be pulled from the database l2image table.

            If you specify image without either provenance or
            provenance_tag, then this class assumes you are creating a
            new zeropoint that won't be saved in the databse.  In this
            case, you need to specify at least zp and dzp, and almost
            certainly want to specify at least meta and subclass.  And
            you have to do it rgith.

            You almost never want this to be None, but it's here to
            support edge cases that want to make a zeropoint object for
            some reason without being explicit about the image.

          provenance : Provenance or UUID or None
            The zeropoint provenance, or the id of the zeropoint
            provenance that can be pulled from the database.  Cannot be
            specified together with either provenance_tag or process.

          provenance_tag : str or None
            The provenance tag of the provenance in the database for
            this zeropoint.  You must also specify process; the two together
            are used to find the provenance in the database.

          process : str or None
            The process to go along with provenance_tag for finding the
            zeropoint provenance in the database.

          zp : float or None
            The zeropoint at the center of the image.  If this is None,
            then the assumption is that the zeropoint needs to be loaded
            frome the database.

          dzp : float or None
            Uncertainty (1σ) on zp.  Should be None if zp is None, or
            not None if zp is not None.

          meta : dict or None
            If you specify zp and dzp, then you might want to specify
            this as well, and what you give should be what the subclass
            specified by subclass expects.  You have to know what you're
            doing.

          subclass : str, default None
            The name of the subclass of the type of zeropoint you want.
            Usually you don't specify this, but let this function figure
            out the right subclass from the database.  If you want the
            object to just encapsulate a single, non-spatially-variable
            zeropoint, then leave this at None.

          id : UUID or None
            If you specify this, it means load the zeropoint from the
            database.  In this case, you must leave off ALL of the other
            parameters.

        """

        # Short-circuit : if given an id, then just load the damn thing from the database
        if id is not None:
            if any( i is not None for i in ( image, provenance, provenance_tag, process,
                                             zp, dzp, meta, subclass ) ):
                raise ValueError( "If you pass an id, you can't pass anything else." )
            return cls.get_by_id( id )

        # First, the image.  If we didn't get one, then we're trying to do a raw zeropoint.
        # If we got one, it's either an Image or an id; in the latter case, get the Image from the database.
        if image is None:
            if any ( i is not None for i in ( provenance, provenance_tag, process ) ):
                raise ValueError( "Can't pass a provenance when image is None." )
            if ( zp is None ) or ( dzp is None ):
                raise ValueError( "When image is None, must specify both zp and dzp." )
        elif not isinstance( image, Image ):
            image = Image.get_image( image )

        # Figure out the provenance
        if not isinstance( provenance, Provenance ):
            if provenance is not None:
                if ( provenance_tag is not None ) or ( process is not None ):
                    raise ValueError( "Cannot give provenance_tag/process if you give provenance" )
                provenance = Provenance.get_by_id( asUUID(provenance) )
            else:
                if ( provenance_tag is None ) != ( process is None ):
                    raise ValueError( "Must specify either both or neither or provenance_tag and process" )
                provenance = Provenance.get_provs_for_tag( provenance_tag, process )

            if ( not isinstance( provenance.params, dict ) ) or ( 'subclass' not in provenance.params ):
                raise ValueError( "Invalid zeropoint provenance, it doesn't include subclass in params" )

        else:
            # Provenance is None
            if ( zp is None ) or ( dzp is None ):
                raise ValueError( "When provenance not given, must specify both zp and dzp" )

        # Figure out the subclass
        if subclass is None:
            subclass = "Zeropoint" if provenance is None else provenance.params[ "subclass" ]
        else:
            if ( provenance is not None ) and ( subclass != provenance.params[ "subclass" ] ):
                raise ValueError( f"subclass mismatch; you asked for {subclass}, but the provenance "
                                  f"has subclass {provenance.params['subclass']}" )

        subclasses = { "Zeropoint": Zeropoint,
                       "RomanL2Zeropoint": RomanL2Zeropoint }
        if subclass not in subclasses:
            raise ValueError( f"Unknown zeropoint subclass {subclass}" )
        subclass = subclasses[ subclass ]

        # Make sure either both or neither of zp and zp are given, and that if so they're floats
        if ( zp is None ) != ( dzp is None ):
            raise ValueError( "Must specify both or neither of zp and dzp, can't give both." )
        if zp is not None:
            if not all( isinstance( i, numbers.Real ) for i in ( zp, dzp ) ):
                raise TypeError( f"zp and dzp must be floats, got {type(zp)} for zp an {type(dzp)} for dzp" )

        if zp is not None:
            # If zp and dzp were given, then just instantiate the object.
            # If it turns out to be inconsistent with what's in the
            # database, things will happen when somebody tries to save it.
            # (I.e. consistency is saving's problem, and if the user creates
            # an inconsistent one and uses it, that's on them.)
            return subclass( zp, dzp,
                             image_id=None if image is None else image.id,
                             provenance_id=None if provenance is None else provenance.id,
                             meta=meta,
                             _allowed_to_call=True )
        else:
            # If zp is not given, then try to load it from the database
            return Zeropoint.get_for_image( image.id, provenance.id )


    def __init__( self, zp, dzp, image_id=None, provenance_id=None, meta={}, id=None, _allowed_to_call=False ):
        """Instantiate a Zeropoint.

        Parameter definitions are the same as in
        Zeropoint.get_zeropoint.  (Don't use _allowed_to_call, that's
        only used internally.)

        The base Zeropoint class assumes a non-spatially varaible zeropoint.

        """

        if not _allowed_to_call:
            raise RuntimeError( "Don't instantiate a Zeropoint directly, call Zeropoint.get_zeropoint" )

        self.id = id
        self._zp = zp
        self._dzp = dzp
        self.image_id = image_id
        self.provenance_id = provenance_id
        self.meta = meta if meta is not None else {}

        # Each subclass should valid the meta field; put this in the __init__ for each subclass
        # Here is the validation for objects that aren't instances of a subclass
        if self.__class__ == Zeropoint:
            if self._meta != {}:
                raise ValueError( "For the base Zeropoint class, meta must be {}" )

    @property
    def id( self ):
        return self._id

    @id.setter
    def id( self, val ):
        self._id = None if val is None else asUUID( val )

    @property
    def image_id( self ):
        return self._image_id

    @image_id.setter
    def image_id( self, val ):
        self._image_id = None if val is None else asUUID( val )

    @property
    def provenance_id( self ):
        return self._provenance_id

    @provenance_id.setter
    def provenance_id( self, val ):
        self._provenance_id = None if val is None else asUUID( val )

    @property
    def meta( self ):
        return self._meta

    @meta.setter
    def meta( self, val ):
        if not isinstance( val, dict ):
            raise TypeError( f"meta must be a dict, not a {type(val)}" )
        self._meta = val

    def zp( self, x, y, dzp=False ):
        """Return the zeropoint.

        This is the zp that you can stuff into::

           m = -2.5 log10( dav ) + zp

        where dav ("data array values") is the *complete* sum of of data
        values from the Image.data array for the object in question
        (i.e., aperture corrections have been applied, or PSFs used were
        properly normalized).  m is an AB magnitude.

        Parameters
        ----------
          x, y : float
             Pixel position on the image.

          dzp : bool, default False
              See Returns below.

        Returns
        -------
          float, or ( float, float )

            if dzp is False, then returns a single float, the zeropoint.
            If dzp is true, then returns a 2-element tuple, the
            zeropoint and the uncertainty on the zeropoint.

        """

        # Default zeropoint class doesn't handle spatial variation
        return ( self._zp, self._dzp ) if dzp else self._zp


    def get_image( self, dbclient=None ):
        """Return the Image object associated with this zeropoint."""

        if self.image_id is None:
            raise RuntimeError( "No image associated with this zeropoint." )

        return Image.get_image( self.image_id, dbclient=dbclient )


    def save( self, overwrite=False, dbclient=None ):
        """Save the zeropoint if it doesn't already exist.

        Will fill in the id field if it's not yet set.

        Assumes that the provenance already exists in the database.

        If an entry already exists for this iamge and provenance, and
        dzp and zp are within 0.1*dzp of the saved values, this will be
        assumed to be consistent (i.e., the "same" zeropoint).

        WARNING: If it does already exist in the database, zp and dzp
        will be updated to match what's in the database.

        """

        if self.image_id is None:
            raise RuntimeError( "Can't save zeropoint to database, no image_id." )
        if self.provenance_id is None:
            raise RuntimeError( "Can't save zeropoint, no provenance_id." )

        data = { 'image_id': None if self.image_id is None else str(self.image_id),
                 'provenance_id': None if self.provenance_id is None else str(self.provenance_id),
                 'zp': self._zp, 'dzp': self._dzp,
                 'meta': self._meta }
        if self._id is not None:
            # Don't even include the id key if it's not known; that's what the server expects
            data['id'] = str(self._id)

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        result = dbclient.send( "/savezp", json=data )
        self.id = result['id']
        self._zp = result['zp']
        self._dzp = result['dzp']
        self.meta = result['meta']


    @classmethod
    def get_for_image( cls, image_id, zp_prov_id=None, zp_prov_tag=None, zp_process=None, dbclient=None ):
        if zp_prov_id is None:
            if ( zp_prov_tag is None ) or ( zp_process is None ):
                raise ValueError( "Must give either zp_prov_id or both of zp_prov_tag and process" )
        else:
            if ( zp_prov_tag is not None ) or ( zp_process is not None ):
                SNLogger.warning( "zp_prov_id given, ignoring zp_prov_tag and zp_process" )
                zp_prov_tag = None
                zp_process = None
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        result = dbclient.send( "/getzpforimage", json={ 'image_id': str(image_id),
                                                         'provid': str(zp_prov_id) if zp_prov_id is not None else None,
                                                         'provtag': zp_prov_tag,
                                                         'process': zp_process } )
        return Zeropoint( result['zp'], result['dzp'],
                          image_id=result['image_id'],
                          provenance_id=result['provenance_id'],
                          meta=result['meta'],
                          id=result['id'],
                          _allowed_to_call=True )


    @classmethod
    def get_by_id( cls, zpid, dbclient=None ):
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        result = dbclient.send( f"/getzp/{zpid}" )
        if ( "error" in result ):
            raise RuntimeError( f"Error response from Zeropoint.get_by_id: {result['error']}" )

        return Zeropoint( result['zp'], result['dzp'],
                          image_id=result['image_id'],
                          provenance_id=result['provenance_id'],
                          meta=result['meta'],
                          id=result['id'],
                          _allowed_to_call=True )


# ======================================================================

class RomanL2Zeropoint( Zeropoint ):
    """Encapsulates a zeropoint for a Roman L2 image, where the pixels give us surface brightness.

    That is, DAV are something per steradian rather than something.  If
    it varies between pixels, then this has to be normalized out.

    This class will use the pixel area files grabbed
    from... somewhere... to normalize this out, and, hopefully, define
    it all so that the _zp and _dzp values it stores are consistent with
    all that.

    Not implemented yet.

    """

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

        # Validate self._meta... once we know how
        raise NotImplementedError( "RomanL2Zeropoint isn't implemented yet." )


    def zp( self, x, y, dzp=False ):
        raise NotImplementedError( "RomanL2Zeropoint isn't implemented yet." )
