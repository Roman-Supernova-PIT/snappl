__all__ = [ 'BaseWCS', 'AstropyWCS', 'GalsimWCS', 'GWCS' ]

import os
import collections.abc

import numpy as np
import astropy.coordinates
import astropy.modeling.models
from astropy.coordinates import SkyCoord
import astropy.units as u
import astropy.wcs
import gwcs.geometry
import gwcs.wcs
import gwcs.coordinate_frames

import roman_datamodels as rdm

from snappl.logger import SNLogger

# ASTROPY NOTE:
#
# We have played with astropy, and using pixel_to_world DOES include
# both SIP and TPV transformations (we are pretty sure).  In any event,
# if you make a WCS that's the linear approximation, you get different
# answers, meaning that the full WCS isn't just using the linear
# approximation.
#
# Note that to write out a header that includes SIP coefficients, you
# have to do wcs.to_header( relax=True ) where wcs is an astropy.wcs.WCS
# object.


# ======================================================================

class BaseWCS:
    """The base class that defines the WCS interface that should be used elsewhere.

    Code outside this module should only call methods that are defined
    in this class.  This class doesn'ta ctually do antyhing, however; to
    actually get a working WCS, you need to instantiate a subclass.

    """

    def __init__( self ):
        self._wcs = None
        self._wcs_is_astropy = False
        pass

    def pixel_to_world( self, x, y ):
        """Go from (x, y) coordinates to ICRS (ra, dec)

        Parameters
        ----------
          x: float or sequence of float
             The x position on the image.  The center of the lower-left
             pixel is at x=0.0

          y: float or sequence of float
             The y position on the image.  The center of the lower-left
             pixle is y=0.0

        Returns
        -------
          ra, dec : floats or arrays of floats, decimal degrees

          You will get back two floats if x an y were floats.  If x and
          y were lists (or other sequences), you will get back two numpy
          arrays of floats.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement pixel_to_world" )

    def world_to_pixel( self, ra, dec ):
        """Go from (ra, dec) coordinates to (x, y)

        Parameters
        ----------
          ra: float or sequence of float
             RA in decimal degrees

          dec: float or sequence of float
             Dec in decimal degrees

        Returns
        -------
           x, y: floats or arrays of floats

           Pixel position on the image; the center of the lower-left pixel is (0.0, 0.0).

           If ra and dec were floats, x and y are floats.  If ra and dec
           were sequences of floats, x and y will be numpy arrays of floats.

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement world_to_pixel" )

    @classmethod
    def from_header( cls, header ):
        """Create an object from a FITS header.

        May not be implemented for all subclasses.

        Parameters
        ----------
          header : astropi.io.fits.Header or dict
             Something that an astropy WCS is able to create itself from.

        Returns
        -------
          An object of the class this class method was called on.

        """
        # This is a dubious function, since it will only work for WCSes based out of FITS, and
        #   won't work for all FITS subclasses.
        raise NotImplementedError( f"{cls.__name__} can't do from_header" )

    def get_galsim_wcs( self ):
        """Return a glasim.AstropyWCS object, if possible."""
        raise NotImplementedError( f"{self.__class__.__name__} can't return a galsim.AstropyWCS" )

    def get_astropy_wcs( self, readonly=True, degree=None ):
        """Return an astropy.wcs.WCS object, if possible.

        Parameters
        ----------
          readonly: bool, default True
            If True, you are promising not to modify the WCS you get back!  If you're going to
            modify it, set readonly to False.  (For some subclasses, this doesn't actually change
            behavior.)

          degree: int
            The degree of the astropy WCS used to approximate the WCS in the object.  The default
            is subclass-dependent.  Ignored by some subclasses.

        For some subclasses, this astropy.wcs.WCS may only be an
        approximation of the true WCS represented by the object.

        """
        raise NotImplementedError( f"{self.__class__.__name__} can't return an astropy.wcs.WCS" )

    def to_fits_header( self ):
        """Return an astropy.io.fits.Header object, if possible, with the WCS in it."""
        raise NotImplementedError( f"{self.__class__.__name__} can't save itself to a FITS header." )


# ======================================================================


class AstropyWCS(BaseWCS):
    """A WCS that is defined by an astropy.wcs.WCS."""

    def __init__( self, apwcs=None ):
        super().__init__()
        self._wcs = apwcs
        self._wcs_is_astropy = True

    @classmethod
    def _fix_wcs_tan_with_pv1_0( cls, header ):
        if header['CTYPE1'] == 'RA---TAN' and 'PV1_0' in header:
            _hdr = header.copy()
            _hdr['CTYPE1'] = 'RA---TPV'
            _hdr['CTYPE2'] = 'DEC--TPV'
            return _hdr
        else:
            return header

    @classmethod
    def from_header( cls, header ):
        """Create an AstropyWCS from a FITS header.

        NOTE: if the header claims that the transformation type is "TAN"
        (i.e. CTYPE1 is "RA---TAN"), but the header also has a "PV1_0"
        keyword, this function will assume that the transformation is
        actually TPV.

        See:
        https://github.com/thomasvrussell/sfft/blob/45efa77452f020b8832a14c8682b87c5ffee4a93/sfft/utils/ReadWCS.py

        Parameters
        ----------
          header: duckish astropy.io.fits.header.Header
            Something that behaves like a FITS header, in that it can be
            accessed as a dictionary, has the copy() method, and canbe
            fead to astropy.wcs.WCS().

        Returns
        -------
          AstropyWCS

        """
        wcs = AstropyWCS()
        wcs._wcs = astropy.wcs.WCS( cls._fix_wcs_tan_with_pv1_0( header ) )
        return wcs

    def to_fits_header( self ):
        return self._wcs.to_header( relax=True )

    def get_galsim_wcs( self ):
        import galsim
        return galsim.AstropyWCS( wcs=self._wcs )

    def get_astropy_wcs( self, readonly=True ):
        if readonly:
            return self._wcs
        else:
            return self._wcs.deepcopy()

    def pixel_to_world( self, x, y ):
        ra, dec = self._wcs.pixel_to_world_values( x, y )
        # I'm a little irritated that a non-single-value ndarray is not a collections.abc.Sequence
        if not ( isinstance( x, collections.abc.Sequence )
                 or ( isinstance( x, np.ndarray ) and x.size > 1 )
                ):
            ra = float( ra )
            dec = float( dec )
        return ra, dec

    def world_to_pixel( self, ra, dec):
        frame = self._wcs.wcs.radesys.lower()  # Needs to be lowercase for SkyCoord
        scs = SkyCoord( ra, dec, unit=(u.deg, u.deg), frame = frame)
        x, y = self._wcs.world_to_pixel( scs )
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y


# ======================================================================

class GalsimWCS(BaseWCS):
    """A WCS speicifc to Galsim."""

    def __init__( self, gsimwcs=None ):
        super().__init__()
        self._gsimwcs = gsimwcs

    @classmethod
    def from_header( cls, header ):
        """Create a GalsimWCS from a FITS header.

        Does TAN-TPV conversion the same as AstropyWCS.from_header.

        Parameters
        ----------
          header: astropy.io.fits.header.Header
            See AstropyWCS.from_header

        Returns
        -------
          GalsimWCS

        """
        import galsim
        wcs = GalsimWCS()
        wcs._gsimwcs = galsim.AstropyWCS( header=AstropyWCS._fix_wcs_tan_with_pv1_0( header ) )
        return wcs

    def to_fits_header( self ):
        return self._gsimwcs.wcs.to_header( relax=True )

    def get_galsim_wcs( self ):
        return self._gsimwcs

    def pixel_to_world( self, x, y ):
        if isinstance( x, collections.abc.Sequence ) and not isinstance( x, np.ndarray ):
            x = np.array( x )
            y = np.array( y )
        # Galsim WCSes are 1-indexed
        ra, dec = self._gsimwcs.toWorld( x+1, y+1, units='deg' )
        if not ( isinstance( x, collections.abc.Sequence )
                 or ( isinstance( x, np.ndarray ) and ra.size > 1 )
                ):
            ra = float( ra )
            dec = float( dec )
        return ra, dec

    def world_to_pixel( self, ra, dec ):
        if isinstance( ra, collections.abc.Sequence ) and not isinstance( ra, np.ndarray ):
            ra = np.array( ra )
            dec = np.array( dec )
        x, y = self._gsimwcs.toImage( ra, dec, units='deg' )
        # Convert from 1-indexed galsim pixel coordaintes to 0-indexed
        x -= 1
        y -= 1
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y


# ======================================================================

class GWCS(BaseWCS):
    """A "G" (Generalized?) WCS : https://gwcs.readthedocs.io/en/latest/

    In the current code, these are only read from roman datamodel ASDF files

    """

    def __init__( self, gwcs=None ):
        super().__init__()
        self._gwcs = gwcs

    @classmethod
    def from_adsf( cls, asdf_file ):
        """Load the WCS from the specified ASDF image file.  (Also see RomanDatamodelImage.get_wcs.)"""
        # read the ASDF file and get the WCS
        dm = rdm.open(asdf_file)
        wcs = GWCS()
        wcs._gwcs = dm.meta.wcs
        return wcs

    def pixel_to_world( self, x, y ):
        if not isinstance( self._gwcs.output_frame.reference_frame, astropy.coordinates.ICRS ):
            raise TypeError( f"Error, the gwcs output frame is of type {type(self._gwcs.output_frame)}, "
                             "but we need it to be ICRS." )
        if isinstance( x, collections.abc.Sequence ) and not isinstance( x, np.ndarray ):
            x = np.array( x )
            y = np.array( y )

        # ADSF WCSes are 0-indexed (lower-left pixel is (0.5,0.5)) like astropy WCS, so no need to convert
        SkyCoord = self._gwcs.pixel_to_world(x, y)
        ra, dec = SkyCoord.ra.deg, SkyCoord.dec.deg
        if not ( isinstance( x, collections.abc.Sequence )
                 or ( isinstance( x, np.ndarray ) and ra.size > 1 )
                ):
            ra = float( ra )
            dec = float( dec )
        return ra, dec

    def world_to_pixel( self, ra, dec ):
        if isinstance( ra, collections.abc.Sequence ) and not isinstance( ra, np.ndarray ):
            ra = np.array( ra )
            dec = np.array( dec )

        # ADSF WCSes are 0-indexed (lower-left pixel is (0.5,0.5)) like astropy WCS, so no need to convert
        skyCoord = SkyCoord( ra, dec, unit=(u.deg, u.deg), frame=self._gwcs.output_frame.reference_frame )
        x, y = self._gwcs.world_to_pixel(skyCoord)
        if not ( isinstance( ra, collections.abc.Sequence )
                 or ( isinstance( ra, np.ndarray ) and y.size > 1 )
                ):
            x = float( x )
            y = float( y )
        return x, y

    def get_astropy_wcs( self , readonly=True, degree=5 ):
        # ... I think there's a more direct way to do this other than writing a header?
        #  Ask Russel.  (He probably told me once and I forgot --Rob.)
        hdr = self._gwcs.to_fits(degree=degree)[0]
        return astropy.wcs.WCS( hdr )


# ======================================================================

class RDM_GWCS(GWCS):
    """A GWCS, specifically from a roman datamodel.

    Uses things that are defined for the Roman datamodel that we're not
    sure are defined for all GWCSes.

    TODO : find out if _gwcs.pixel_to_world(sc) is the same as _gwcs(x,
    y) (except for returning a SkyCoord rather than ra, dec).  If not,
    then have a whole lot of consternation about what the heck the
    defined pixel_to_world function is actually doing.  Likewise for
    _gwcs.world_to_pixel(sc) and _gwcs.invert(ra, dec).

    (In test_wcs.py, the corners and center of the test image we are
    using produce identical results, but it's not clear that the test
    image we're using has a realistic roman GWCS; it might have a
    simplified one.)

    """

    def __init__( self, gwcs=None ):
        super().__init__( gwcs=gwcs )

    def pixel_to_world(self, x, y, with_bounding_box=False):
        """ Inputs:
            - x: float or sequence of float
                The x position on the image.  The center of the lower-left
                pixel is at x=0.0

            - y: float or sequence of float
                The y position on the image.  The center of the lower-left
                pixel is y=0.0
            - with_bounding_box: bool, default False
                If True, then if the ra, dec calculated from the input x, y are outside the bounding
                box of the WCS, NaN is returned  If False, then it will just return whatever the WCS returns
                for those ra, dec, even if they are outside the bounding box. Campari, for instance,
                needs to be able to refer to locations outside of the stamp.
        """
        if not isinstance( self._gwcs.output_frame.reference_frame, astropy.coordinates.ICRS ):
            raise TypeError( f"Error, the gwcs output frame is of type {type(self._gwcs.output_frame)}, "
                             "but we need it to be ICRS." )

        if isinstance( x, collections.abc.Sequence ) and not isinstance( x, np.ndarray ):
            x = np.array( x )
            y = np.array( y )

        # ADSF WCSes are 0-indexed (lower-left pixel is (0.5,0.5)), so no need to convert
        return self._gwcs( x, y, with_bounding_box=with_bounding_box )

    def world_to_pixel( self, ra, dec, with_bounding_box=False ):
        """ Inputs:
            - with_bounding_box: bool, default False
                If True, then if the input ra, dec are outside the bounding box of the WCS,
                NaN is returned  If False, then it will just return whatever the WCS returns for those ra, dec,
                even if they are outside the bounding box. Campari, for instance,
                needs to be able to find locations outside of the stamp.
        """
        if not isinstance( self._gwcs.output_frame.reference_frame, astropy.coordinates.ICRS ):
            raise TypeError( "Error, the gwcs output frame is of type "
                             f"{type(self._gwcs.output_frame.reference_frame)}, but we need it to be ICRS." )

        if isinstance( dec, collections.abc.Sequence ) and not isinstance( dec, np.ndarray ):
            ra = np.array( ra )
            dec = np.array( dec )

        return self._gwcs.invert(ra, dec, with_bounding_box=with_bounding_box)


# ======================================================================

class RDM_CRDS_GWCS(RDM_GWCS):
    """A GWCS, specifically from a roman datamodel for Rick's Aug 2026 sims.

    This version of the class specifically uses the CRDS distortion correction,
    which is not included in the RDM_GWCS class. It is currently unclear if this
    correction will be needed for real data but in the meantime we need it for this set of simulations.
    Note, to function, you will need to have access to the CRDS database. Run the following:

    export CRDS_SERVER_URL=https://roman-crds.stsci.edu
    export CRDS_PATH=${HOME}/crds_cache

    """

    @classmethod
    def from_adsf( cls, asdf_file ):
        """Load the WCS from the specified ASDF image file.  (Also see RomanDatamodelImage.get_wcs.)"""
        # read the ASDF file and get the WCS
        dm = rdm.open(asdf_file)
        wcs = GWCS()
        wcs._gwcs = dm.meta.wcs
        wcs.fix_gwcs_for_rick_sims( dm )
        return wcs

    def __init__( self, gwcs=None, i_know_what_i_am_doing=False, parent_image=None ):
        if not i_know_what_i_am_doing:
            raise RuntimeError( "Initializing RDM_CRDS_GWCSes are hazardous.  Don't do it if you don't really "
                                "understand everything Rob and Cole talked about on August 6, 2026." )
        if parent_image is None:
            raise RuntimeError( "Can't make an RDM_CRDS_GWCS without the parent image" )
        super().__init__( gwcs=gwcs )
        self.fix_gwcs_for_rick_sims( parent_image )


    def fix_gwcs_for_rick_sims( self, dm ):
        # Lots of code stolen from:
        #   https://github.com/spacetelescope/romanisim/blob/44767fa3c9c14ebcfc9dbfcf62126354eba3ef1a/romanisim/models/wcs.py#L94
        # which is under a BSD license just like this, so it's all legit.
        # It is Copyright (C) 2022 Association of Universities for Research in Astronomy (AURA)

        import crds

        if type(dm) is not rdm.datamodels.ImageModel:
            raise RuntimeError( "Wrong time of image passed." )
        shape = dm.data.shape

        world_pos = astropy.coordinates.SkyCoord(
            dm.meta.wcsinfo.ra_ref * u.deg,
            dm.meta.wcsinfo.dec_ref * u.deg,
        )

        dist_name = crds.getreferences(
            dm.get_crds_parameters(),
            reftypes=["distortion"],
            observatory="roman",
        )["distortion"]
        dm.meta.ref_file["distortion"] = os.path.basename(dist_name)

        dist_model = rdm.datamodels.DistortionRefModel(dist_name)
        distortion = dist_model.coordinate_distortion_transform

        wcs = self.make_wcs(
            world_pos,
            distortion,
            v2_ref=dm.meta.wcsinfo.v2_ref,
            v3_ref=dm.meta.wcsinfo.v3_ref,
            roll_ref=dm.meta.wcsinfo.roll_ref,
            scale_factor=dm.meta.velocity_aberration.scale_factor,
        )
        wcs.bounding_box = ((-0.5, shape[-1] - 0.5), (-0.5, shape[-2] - 0.5))

        self._gwcs = wcs

    # Also copied and modified from https://github.com/spacetelescope/romanisim
    #  romanisim/models/wcs.py
    # The goal is so that this class will work even in an environment that doesn't
    #  import romanisim
    @classmethod
    def make_wcs(
            cls,
            targ_pos,
            distortion,
            roll_ref=0,
            v2_ref=0,
            v3_ref=0,
            wrap_v2_at=180,
            wrap_lon_at=360,
            scale_factor=1.0,
    ):
        """Create a gWCS from a target position, a roll, and a distortion map.

        Parameters
        ----------
        targ_pos : astropy.coordinates.SkyCoord
            The celestial coordinates of the boresight or science aperture.

        distortion : callable
            The distortion mapping pixel coordinates to V2/V3 coordinates for a
            detector.

        roll_ref : float
            The angle of the V3 axis relative to north, increasing from north to
            east, at the boresight or science aperture.
            Note that the V3 axis is rotated by +60 degree to the +Y axis.

        v2_ref : float
            The v2 coordinate (arcsec) corresponding to targ_pos

        v3_ref : float
            The v3 coordinate (arcsec) corresponding to targ_pos

        scale_factor : float
            The scale factor induced by velocity aberration

        Returns
        -------
        gwcs.wcs object representing WCS for observation
        """

        # it seems to me like the distortion mappings have v2_ref = v3_ref = 0,
        # which is easiest, so let me just keep those for now?
        # eventually to have greater ~realism, we'd want to set v2_ref and v3_ref
        # to whatever they'll end up being, different for each SCA.
        # We'd still need to get the ra_ref and dec_ref for each SCA using
        # this routine, though, with v2_ref = v3_ref = 0.  I need to think
        # a bit harder about whether we will also need to compute a separate
        # roll_ref for each SCA, and how that would best be done; if nothing else,
        # we do some finite differences to get the direction +V3 on the sky and
        # compute an angle wrt north.
        ra_ref = targ_pos.ra.to(u.deg).value
        dec_ref = targ_pos.dec.to(u.deg).value

        # v2_ref, v3_ref are in arcsec, but RotationSequence3D wants degrees,
        # so start by scaling by 3600.
        rot = astropy.modeling.models.RotationSequence3D(
            [v2_ref / 3600, -v3_ref / 3600, roll_ref, dec_ref, -ra_ref], "zyxyz"
        )

        # V2V3 are in arcseconds, while SphericalToCartesian expects degrees,
        # so again start by scaling by 3600
        tel2sky = (
            (astropy.modeling.models.Scale(1 / 3600) & astropy.modeling.models.Scale(1 / 3600))
            | gwcs.geometry.SphericalToCartesian(wrap_lon_at=wrap_v2_at)
            | rot
            | gwcs.geometry.CartesianToSpherical(wrap_lon_at=wrap_lon_at)
        )
        tel2sky.name = "v23tosky"

        detector = gwcs.coordinate_frames.Frame2D(
            name="detector", axes_order=(0, 1), unit=(u.pix, u.pix)
        )
        v2v3 = gwcs.coordinate_frames.Frame2D(
            name="v2v3",
            axes_order=(0, 1),
            axes_names=("v2", "v3"),
            unit=(u.arcsec, u.arcsec),
        )
        v2v3vacorr = gwcs.coordinate_frames.Frame2D(
            name="v2v3vacorr",
            axes_order=(0, 1),
            axes_names=("v2", "v3"),
            unit=(u.arcsec, u.arcsec),
        )
        world = gwcs.coordinate_frames.CelestialFrame(
            reference_frame=astropy.coordinates.ICRS(), name="world"
        )

        # Compute differential velocity aberration (DVA) correction:
        va_corr = cls.dva_corr_model(
            va_scale=scale_factor, v2_ref=v2_ref, v3_ref=v3_ref
        )

        pipeline = [
            gwcs.wcs.Step(detector, distortion),
            gwcs.wcs.Step(v2v3, va_corr),
            gwcs.wcs.Step(v2v3vacorr, tel2sky),
            gwcs.wcs.Step(world, None),
        ]
        return gwcs.wcs.WCS(pipeline)


    # Also copied and modified from https://github.com/spacetelescope/romanisim
    #  romanisim/models/wcs.py
    @classmethod
    def dva_corr_model(cls, va_scale, v2_ref, v3_ref):
        """Create transformation that accounts for differential velocity aberration (scale).

        Parameters
        ----------
        va_scale : float, None
            Ratio of the apparent plate scale to the true plate scale. When
            ``va_scale`` is `None`, it is assumed to be identical to ``1`` and
            an ``astropy.modeling.models.Identity`` model will be returned.

        v2_ref : float, None
            Telescope ``v2`` coordinate of the reference point in ``arcsec``. When
            ``v2_ref`` is `None`, it is assumed to be identical to ``0``.

        v3_ref : float, None
            Telescope ``v3`` coordinate of the reference point in ``arcsec``. When
            ``v3_ref`` is `None`, it is assumed to be identical to ``0``.

        Returns
        -------
        va_corr : astropy.modeling.CompoundModel, astropy.modeling.models.Identity
            A 2D compound model that corrects DVA. If ``va_scale`` is `None` or 1
            then `astropy.modeling.models.Identity` will be returned.

        """
        if va_scale is None or va_scale == 1:
            return astropy.modeling.models.Identity(2)

        if va_scale <= 0:
            SNLogger.warning( f"Velocity aberration scale must be a positive number: {va_scale}; "
                              f"Defaulting to scale of 1.0" )
            va_scale = 1.0

        va_corr = astropy.modeling.models.Scale(va_scale, name="dva_scale_v2") & astropy.modeling.models.Scale(
            va_scale, name="dva_scale_v3"
        )

        if v2_ref is None:
            v2_ref = 0

        if v3_ref is None:
            v3_ref = 0

        if v2_ref == 0 and v3_ref == 0:
            return va_corr

        # NOTE: it is assumed that v2, v3 angles and va scale are small enough
        # so that for expected scale factors the issue of angle wrapping
        # (180 degrees) can be neglected.
        v2_shift = (1 - va_scale) * v2_ref
        v3_shift = (1 - va_scale) * v3_ref

        va_corr |= astropy.modeling.models.Shift(v2_shift, name="dva_v2_shift") & astropy.modeling.models.Shift(
            v3_shift, name="dva_v3_shift"
        )
        va_corr.name = "DVA_Correction"
        return va_corr
