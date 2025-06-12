import os
import pytest

import scipy

from astropy.io import fits  # noqa: F401

from snappl.psf import ou24PSF

# These tests won't work on github until we get the right subset of galsim data
#   properly imported.

# They depend on a tds.yaml file existing in /sn_info_dir, and some of
#   the directories referred therein to have the right stuff in them.
#   Look in the phrosty archive under phrosty/examples/perlmutter/tds.yaml for
#   one such file that will work on perlmutter, *if* you also run in a
#   podman instance using the interactive_perlmutter.sh script in that
#   same directory.


@pytest.mark.skipif( os.getenv('GITHUB_SKIP'), reason="Skipping test until we have galsim data" )
def test_normalization():
    # This isn't really testing snappl code, it's checking out galsim We
    # use a random seed here for repeatibility.  Empirically, the PSF
    # normalization in the smaller clip varies by at least several
    # tenths of a percent when you use different random numbers.
    bigsize = 201
    smallsize = 41
    bigpsfobj = ou24PSF( pointing=6, sca=17, size=bigsize )
    bigstamp = bigpsfobj.get_stamp( seed=42 )
    smallpsfobj = ou24PSF( pointing=6, sca=17, size=smallsize )
    # Using the same seed here probably isn't doing what we want it to do,
    #   i.e. creating the same realization of the PSF that then gets
    #   downsampled.  But, maybe it is.  Go read the code to find out.
    smallstamp = smallpsfobj.get_stamp( seed=42 )

    assert bigstamp.sum() == pytest.approx( 1., abs=0.001 )

    x0 = bigsize // 2 - smallsize // 2
    x1 = x0 + smallsize
    assert smallstamp.sum() == pytest.approx( bigstamp[x0:x1,x0:x1].sum(), rel=1e-5 )


@pytest.mark.skipif( os.getenv('GITHUB_SKIP'), reason="Skipping test until we have galsim data" )
def test_get_stamp():
    psfobj = ou24PSF( pointing=6, sca=17, size=41. )

    # It's slow getting galsim PSFs with photon ops, so we're not going to
    #   do as exhaustive of tets as we do for OversampledImagePSF

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

    # KEEP GOING
