import os
import pytest

import numpy as np
import scipy

from astropy.io import fits  # noqa: F401

import snappl.psf
from snappl.psf import PSF

# These tests won't work on github until we get the right subset of galsim data
#   properly imported.
#
# They depend on a tds.yaml file existing in /sn_info_dir, and some of
#   the directories referred therein to have the right stuff in them.
#   Look in the phrosty archive under phrosty/examples/perlmutter/tds.yaml for
#   one such file that will work on perlmutter, *if* you also run in a
#   podman instance using the interactive_perlmutter.sh script in that
#   same directory.


@pytest.mark.skipif( os.getenv('GITHUB_SKIP'), reason="Skipping test until we have galsim data" )
def test_slow_normalization():
    # This isn't really testing snappl code, it's checking out galsim.
    # Empirically, the PSF normalization in the smaller clip varies by
    # at least several tenths of a percent when you use different random
    # seeds.
    bigsize = 201
    smallsize = 41
    bigpsfobj = PSF.get_psf_object( "ou24PSF_slow", pointing=6, sca=17, size=bigsize )
    bigstamp = bigpsfobj.get_stamp( seed=42 )
    assert bigstamp.shape == ( 201, 201 )
    smallpsfobj = PSF.get_psf_object( "ou24PSF_slow", pointing=6, sca=17, size=smallsize )
    # Using the same seed here probably isn't doing what we want it to do,
    #   i.e. creating the same realization of the PSF that then gets
    #   downsampled.  But, maybe it is.  Go read the code to find out.
    smallstamp = smallpsfobj.get_stamp( seed=42 )
    assert smallstamp.shape == ( 41, 41 )

    assert bigstamp.sum() == pytest.approx( 1., abs=0.001 )

    x0 = bigsize // 2 - smallsize // 2
    x1 = x0 + smallsize
    assert smallstamp.sum() == pytest.approx( bigstamp[x0:x1,x0:x1].sum(), rel=1e-5 )


@pytest.mark.skipif( os.getenv('GITHUB_SKIP'), reason="Skipping test until we have galsim data" )
def test_slow_get_stamp():
    psfobj = PSF.get_psf_object( "ou24PSF_slow", pointing=6, sca=17, size=41. )
    assert isinstance( psfobj, snappl.psf.ou24PSF_slow )

    # It's slow getting galsim PSFs with photon ops, so we're not going to
    #   do as exhaustive of tets as we do for OversampledImagePSF.  Use
    #   an explicit seed here so tests are reproducible.

    # Try a basic centered PSF
    stamp = psfobj.get_stamp( seed=42 )
    assert stamp.shape == ( 41, 41 )
    # Empirically, a 41×41 stamp comes out at 0.986.  See test_normalization above.
    assert stamp.sum() == pytest.approx( 0.986, abs=0.001 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    # The roman PSF is asymmetric, so we don't expect the CoM to be the exact center.
    # The comparison numbers are what we got the first time we ran this test...
    assert cx == pytest.approx( 19.716, abs=0.01 )
    assert cy == pytest.approx( 19.922, abs=0.01 )

    centerstamp = stamp

    # Try an offcenter PSF that's still centered on a pixel
    # The wings of this PSF are monstrous, so the centroiding
    #   doesn't come out quite precise when the thing is offset
    #   this much.
    stamp = psfobj.get_stamp( 2048., 2048., x0=2050, y0=2040, seed=42 )
    assert stamp.shape == ( 41, 41 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 19.716 + ( 2048 - 2050 ), abs=0.2 )
    assert cy == pytest.approx( 19.922 + ( 2048 - 2040 ), abs=0.2 )
    # This stamp should just be a shifted version of centerstamp; verify
    #   that.  This check should be much more precise than the
    #   centroids, as wing-cutting won't matter for this check.
    # (Not *exactly* because centerstamp is at 2044,2044, not 2048,
    #   2048, but the PSF can't vary much over 4 pixels...)
    absoff = 0.004 * centerstamp[ 20, 20 ]
    for xoff in [ -1, 0, 1 ]:
        for yoff in [ -1, 0, 1 ]:
            assert ( stamp[ 20 + yoff + 2048-2040, 20 + xoff + 2048-2050 ] ==
                     pytest.approx( centerstamp[ 20 + yoff, 20 + xoff ], abs=absoff ) )

    # Try a PSF centered between two pixels.  Because of how we
    #   define 0.5 behavior in PSF.get_stamp, this should be
    #   centered to the *left* of the center of the image.
    stamp = psfobj.get_stamp( 2048.5, 2048., seed=42 )
    assert stamp.shape == ( 41, 41 )
    assert stamp.sum() == pytest.approx( 0.986, abs=0.001 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 19.22, abs=0.02 )
    assert cy == pytest.approx( 19.92, abs=0.02 )

    # Try an offcenter PSF that's centered on a corner
    # The PSF center should be at -1.5, +2.5 pixels
    # relative to the stamp center... but then
    # offset because of the asymmetry of the roman PSF.
    stamp = psfobj.get_stamp( 2048.5, 2048.5, x0=2050, y0=2046, seed=42 )
    assert stamp.shape == ( 41, 41 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 18.22, abs=0.02 )
    assert cy == pytest.approx( 22.42, abs=0.03 )


# Continue this when ou24psf is more than a wrapper around ou24PSF_slow
# @pytest.mark.skipif( os.getenv('GITHUB_SKIP'), reason="Skipping test until we have galsim data" )
# def test_get_stamp():
#     # Use the defaults, which will be an internal image of size 201 and a stamp size of 41
#     psfobj = PSF.get_psf_object( "ou24PSF", pointing=6, sca=17, oversample_factor=11,  oversampled_size=451 )
#     assert isinstance( psfobj, snappl.psf.ou24PSF )
#
#     # Try a basic centered PSDF
#     stamp = psfobj.get_stamp()
#     assert stamp.shape == ( 41, 41 )
#     # TODO MORE

@pytest.mark.skipif(os.getenv("GITHUB_SKIP"), reason="Skipping test until we have galsim data")
def test_check_phot_off():
    # Check and make sure that photon ops are actually off, when passing
    #  include_photonOps=False, they weren't previously. If they are off, the
    # sum of the image should always equal what it is in the test below.
    psfobj = PSF.get_psf_object( "ou24PSF_slow", pointing=6, sca=17, size=41.,
                                 include_photonOps=False )
    stamp = psfobj.get_stamp( 2048., 2048., x0=2050, y0=2040)
    regression_val = 2.0617566108703613
    assert stamp.sum() == pytest.approx(regression_val , abs=1e-7 ), \
        "Check that photon_ops is False, the sum" +\
              f"of the image should equal {regression_val}, was actually {stamp.sum()}"


@pytest.mark.skipif(os.getenv("GITHUB_SKIP"), reason="Skipping test until we have galsim data")
def test_normalization():
    # This isn't really testing snappl code, it's checking out galsim.
    # Empirically, the PSF normalization in the smaller clip varies by
    # at least several tenths of a percent when you use different random
    # seeds.
    bigsize = 201
    smallsize = 41
    bigpsfobj = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=bigsize)
    bigstamp = bigpsfobj.get_stamp(seed=42)
    assert bigstamp.shape == (201, 201)
    smallpsfobj = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=smallsize)
    # Using the same seed here probably isn't doing what we want it to do,
    #   i.e. creating the same realization of the PSF that then gets
    #   downsampled.  But, maybe it is.  Go read the code to find out.
    smallstamp = smallpsfobj.get_stamp(seed=42)
    assert smallstamp.shape == (41, 41)

    assert bigstamp.sum() == pytest.approx(1.0, abs=0.001)

    x0 = bigsize // 2 - smallsize // 2
    x1 = x0 + smallsize
    assert smallstamp.sum() == pytest.approx(bigstamp[x0:x1, x0:x1].sum(), rel=1e-5)


@pytest.mark.skipif(os.getenv("GITHUB_SKIP"), reason="Skipping test until we have galsim data")
def test_get_stamp():
    # Note that in this test I have to re-call get_psf_object each time I want to make a stamp,
    # because the fast version of ou24PSF is not designed to allow x0 or y0 to change.

    psfobj = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=41.0)
    assert isinstance(psfobj, snappl.psf.ou24PSF)

    # It's slow getting galsim PSFs with photon ops, so we're not going to
    #   do as exhaustive of tets as we do for OversampledImagePSF.  Use
    #   an explicit seed here so tests are reproducible.

    # Try a basic centered PSF
    stamp = psfobj.get_stamp(seed=42)
    assert stamp.shape == (41, 41)
    # Empirically, a 41×41 stamp comes out at 0.986.  See test_normalization above.
    assert stamp.sum() == pytest.approx(0.986, abs=0.001)
    cy, cx = scipy.ndimage.center_of_mass(stamp)
    # The roman PSF is asymmetric, so we don't expect the CoM to be the exact center.
    # The comparison numbers are what we got the first time we ran this test...
    assert cx == pytest.approx(19.716, abs=0.01)
    assert cy == pytest.approx(19.922, abs=0.01)

    centerstamp = stamp

    # Try an offcenter PSF that's still centered on a pixel
    # The wings of this PSF are monstrous, so the centroiding
    #   doesn't come out quite precise when the thing is offset
    #   this much.

    psfobj = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.0, 2048.0, x0=2050, y0=2040, seed=42)
    assert stamp.shape == (41, 41)
    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(19.716 + (2048 - 2050), abs=0.2)
    assert cy == pytest.approx(19.922 + (2048 - 2040), abs=0.2)
    # This stamp should just be a shifted version of centerstamp; verify
    #   that.  This check should be much more precise than the
    #   centroids, as wing-cutting won't matter for this check.
    # (Not *exactly* because centerstamp is at 2044,2044, not 2048,
    #   2048, but the PSF can't vary much over 4 pixels...)
    absoff = 0.004 * centerstamp[20, 20]
    for xoff in [-1, 0, 1]:
        for yoff in [-1, 0, 1]:
            assert stamp[20 + yoff + 2048 - 2040, 20 + xoff + 2048 - 2050] == pytest.approx(
                centerstamp[20 + yoff, 20 + xoff], abs=absoff
            )

    with pytest.raises(ValueError, match="ou24PSF.get_stamp called with x0 or y0 that does not match"):
        _ = psfobj.get_stamp(2048.0, 2048.0)

    with pytest.raises(ValueError, match="ou24PSF.get_stamp called with x0 or y0 that does not match"):
        _ = psfobj.get_stamp(2048.0, 2048.0, x0=2046, y0=2045)

    newstamp = psfobj.get_stamp(2048.0, 2048.0, x0=2050, y0=2040, seed=42)
    np.testing.assert_array_equal(stamp, newstamp)


    # Try a PSF centered between two pixels.  Because of how we
    #   define 0.5 behavior in PSF.get_stamp, this should be
    #   centered to the *left* of the center of the image.
    psfobj = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.5, 2048.0, seed=42)
    assert stamp.shape == (41, 41)
    assert stamp.sum() == pytest.approx(0.986, abs=0.001)
    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(19.22, abs=0.02)
    assert cy == pytest.approx(19.92, abs=0.02)



    # Try an offcenter PSF that's centered on a corner
    # The PSF center should be at -1.5, +2.5 pixels
    # relative to the stamp center... but then
    # offset because of the asymmetry of the roman PSF.
    psfobj = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.5, 2048.5, x0=2050, y0=2046, seed=42)
    assert stamp.shape == (41, 41)
    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(18.22, abs=0.02)
    assert cy == pytest.approx(22.42, abs=0.03)


@pytest.mark.skipif(os.getenv("GITHUB_SKIP"), reason="Skipping test until we have galsim data")
def test_set_wcs():
    # For some testing and simulation cases, we want to be able to set the WCS of the PSF manually.
    # This is a test that this works.
    psfobj_1 = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=41.0)
    assert isinstance(psfobj_1, snappl.psf.ou24PSF)

    psfobj_2 = PSF.get_psf_object("ou24PSF", pointing=5934, sca=3, size=41.0)
    assert isinstance(psfobj_2, snappl.psf.ou24PSF)

    psfobj_1.get_stamp( seed=42 )
    psfobj_2.get_stamp( seed=42 )

    assert psfobj_1._wcs != psfobj_2._wcs, "The initial WCS should be different for different PSF objects with" + \
    "different pointing/sca."

    psfobj_1 = PSF.get_psf_object("ou24PSF", pointing=6, sca=17, size=41.0)
    psfobj_2 = PSF.get_psf_object("ou24PSF", pointing=5934, sca=3, size=41.0)

    psfobj_1.get_stamp( seed=42 )
    psfobj_2.get_stamp( seed=42, input_wcs=psfobj_1._wcs )

    assert psfobj_1._wcs == psfobj_2._wcs, "The WCS should be the same after setting it manually."