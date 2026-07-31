from snappl.dbclient import SNPITDBClient
from snappl.image import Image
from snappl.logger import SNLogger
from snappl.utils import asUUID


class Zeropoint:
    """A class encapsulating a zeropoint.

    So that we are very clear what we mean by zeropoint, this is the definition.

    First, imagine that you have an Image (i.e., an object of the class
    defined in image.py).  That image's data property is a
    two-dimensional array of floats.  Define "kaglorkys" as the units of
    that two dimensional array.  I wanted to use counts, or DN, but it
    was impossible to ever have a conversation on Slack that used this
    word without getting a long lecture from Stefano, so we're going to
    use the kaglorky as the unit of whatever it is that we get in our
    data rrays.  Kaglorkys is NOT necessarily a number of photons, or a
    number of photoelectrons.  Indeed, it's entirely possible that the
    underlying physical units of the pixel values of the image is
    something proportional to number of photoelectrons per second,
    rather than just number of electrons.  However, *however* they came
    to be, "kaglorkys" is what this class defines as the units of that
    two dimensional array.  For purposes of discussion, we do not have
    to know if this is a rate or not; it just is whatever the units of
    the data array is.

    Second, imagine that we have a series of astronomical sources
    (stars, to make it concrete), and we have images of those stars
    taken by the telescope.  Although this is not definitional, we are
    going to assume that the number of kaglorkys in the Image.data array is
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

       m = -2.5 * log10( kaglorkys ) + zp

    where kaglorkys is the sum of the whole data array, and m is an AB
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

    When it comes to pixel area issues, it also assumes that
    preprocessing has corrected for this.  For purely geometric area
    (or, really, angular area projected through the optical system on to
    the geometric position of the pixel on the detector), no correction
    needs to be done for our definition here; however, it does mean that
    actual photometry would have to correct for it.  (That is, a PSF (or
    PRF) used in PSF photometry would have to be spatially-dependent and
    take that into account, and an aperture correction for aperture
    phtometry would have to be spatially dependent and take that into
    account.)  For electronic effects, espeically ones that depend on
    how full the well is, it means that *something* has to be done to
    the image to take those effects out.  (Thushara, save us!)

    ACTUAL PHOTOMETRY

    Importantly, the zeropoint we've defined here DOES NOT take into
    account any aperture size, nor does it take into account any
    particular realization of a PSF.  It is a property *of the image*,
    not of the method used to extract photometry.  That means to use
    this zeropoint:

       * Aperture photometry values must be properly "aperture
         corrected" before the kaglorkys are fed into the zeropoint
         formula.  Ideally, when things aren't too complicated, this
         correction is just a single factor that multiplies the number
         of kaglorkys in the aperture to give an effective "infinite
         aperture" number of kaglorkys.  This factor will, of course, be
         different for apertures of different sizes (and shapes), and
         will also in principle be different at different positions on a
         detector array.

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
    will define "the number of kaglorkys detected per frequency bin for
    light of frequency ν for a source with f(ν)=3631 Jy".  [ASIDE: I say
    "detector response", but really I mean "detector + filter response",
    or, really really, "system response".]  This means that D(ν) has
    units of s (or, more clearly, Hz⁻¹) (or, maybe, if you don't think
    of kaglorkys as dimensionless, units of kaglorky/Hz).  The actual light
    source is going to have some SED S(ν) (in units of Energy/Time/Flux
    Binwidth/Area).

    The total number of kaglorkys detected, therefore, is::

        kaglorkys = ∫ S(ν) D(ν) / (3631Jy) dν

    (Presumably D(ν) goes to zero outside some finite range of ν so we
    don't have to think about infinite numbers.)

    Under this definition, the zeropoint is defined as::

        zp = 2.5 log10( ∫ D(ν) dν )

    (To see this: consider S(ν) = 3631 Jy for all ν, which is the definition of a m_AB=0 source.  In this case::

       0  = -2.5 log10(kaglorkys) + zp
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

    The number of kaglorkys from such a source would be::

       kaglorkys = ∫ S₀ D(ν) / (3631Jy) dν = S₀ / 3631Jy * ∫ D(ν) dν

    or::

       kaglorkys / ( ∫ D(ν) dν ) = S₀ / 3631Jy

    Taking logs of both sides::

       -2.5 log10( kaglorkys ) + 2.5 log10( ∫ D(ν) dν ) = -2.5 log10( S₀/Jy ) + 2.5 log10( 3631 )
       -2.5 log10( kaglorkys ) + zp = -2.5 log10( S₀ ) + 8.900 = m_AB

    Where it gets painful is when S(ν) is not constant with ν.  In this
    case, the magnitude you will calculate from the zeropoint would be::

      m_calc = -2.5 log10( kaglorkys ) + zp
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

       m = -2.5 log10( kaglorkys ) + zp + cor_sed

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

    WHAT AN OBJECT OF THIS CLASS STORES

    It's going to be a letdown, because after all of that, this is just
    a class to store two numbers, plus an id, an image id, and a
    provenance id.

    Color corrections are *not* stored here, because the ZeroPoint is a
    property of the just image, whereas the color correction is a
    property of the object and the detector, filter, telescope.  In
    terms of the definitions about, color correction depends on D(ν) and
    S(ν), whereas zeropoint only depends on D(ν).  (Actually, color
    correction is a property of object observed, detector, filter,
    telescope, object being observed, *and image*, because D(ν) probably
    changes over time!)

    """

    def __init__( self, zp, dzp, image_id=None, provenance_id=None, id=None ):
        """Instantiate a Zeropoint."""

        self._id = None if id is None else asUUID(id)
        self._zp = zp
        self._dzp = zp
        self._image_id = None if image_id is None else asUUID( image_id )
        self._provenance_id = None if provenance_id is None else asUUID( provenance_id )

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
    def zp( self ):
        return self._zp

    @zp.setter
    def zp( self, val ):
        # Type checking?
        self._zp = val

    @property
    def dzp( self ):
        return self._dzp

    @dzp.setter
    def dzp( self, val ):
        # Type checking?
        self._dzp = val

    def get_image( self, dbclient=None ):
        """Return the L2 Image object associated with this zeropoint."""

        if self.image_id is None:
            raise RuntimeError( "No image associated with this zeropoint." )

        return Image.get_image( self.image_id, dbclient=dbclient )

    def save( self, overwrite=False, dbclient=None ):
        """Save the zeropoint if it doesn't already exist.

        Will fill in the id field if it's not yet set.

        If dzp and zp are within 0.1*dzp of the saved values, this will
        be assumed to be consistent (i.e., the "same" zeropoint).

        WARNING: If it does already exist in the database, zp and dzp
        will be updated to match what's in the database.

        """

        if self.image_id is None:
            raise RuntimeError( "Can't save zeropoint to database, no image_id." )
        if self.provenance_id is None:
            raise RuntimeError( "Can't save zeropoint, no provenance_id." )

        data = { 'image_id': str(self.image_id),
                 'provenance_id': str(self.provenance_id),
                 'zp': self._zp, 'dzp': self._dzp }
        if self._id is not None:
            data['id'] = str(self._id)

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        result = dbclient.send( "/savezp", json=data )
        self.id = result['id']
        self.zp = result['zp']
        self.dzp = result['dzp']


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
                          id=result['id'] )


    @classmethod
    def get_by_id( cls, zpid, dbclient=None ):
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        result = dbclient.send( f"/getzp/{zpid}" )
        if ( "error" in result ):
            raise RuntimeError( f"Error response from Zeropoint.get_by_id: {result['error']}" )

        return Zeropoint( result['zp'], result['dzp'],
                          image_id=result['image_id'],
                          provenance_id=result['provenance_id'],
                          id=result['id'] )
