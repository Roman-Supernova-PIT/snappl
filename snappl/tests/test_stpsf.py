import pytest

import numpy as np
import scipy

from snappl.psf import PSF


def test_normalization():
    # This isn't really testing snappl code, it's checking out STPSF.
    # Empirically, the PSF normalization in the smaller clip varies by
    # at least several tenths of a percent when you use different random
    # seeds.
    bigsize = 501
    smallsize = 41
    bigpsfobj = PSF.get_psf_object("STPSF", band="R062", sca=17, size=bigsize)
    bigstamp = bigpsfobj.get_stamp(seed=42)
    assert bigstamp.shape == (bigsize, bigsize)
    smallpsfobj = PSF.get_psf_object("STPSF", band="R062", sca=17, size=smallsize)
    # Using the same seed here probably isn't doing what we want it to do,
    #   i.e. creating the same realization of the PSF that then gets
    #   downsampled.  But, maybe it is.  Someone should go read the code to find out.
    smallstamp = smallpsfobj.get_stamp(seed=42)
    assert smallstamp.shape == (smallsize, smallsize)

    assert bigstamp.sum() == pytest.approx(1.0, abs=0.001)

    x0 = bigsize // 2 - smallsize // 2
    x1 = x0 + smallsize
    assert smallstamp.sum() == pytest.approx(bigstamp[x0:x1, x0:x1].sum(), rel=1e-5)


def test_get_centered_psf():
    psfobj = PSF.get_psf_object("STPSF", band="R062", sca=17, size=41)

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


def test_get_offcenter_psf():
    # Try an offcenter PSF that's still centered on a pixel
    # The wings of this PSF are monstrous, so the centroiding
    #   doesn't come out quite precise when the thing is offset
    #   this much.

    psfobj = PSF.get_psf_object("STPSF", band="R062", sca=17, size=41.0)
    centerstamp = psfobj.get_stamp(seed=42)

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
            assert stamp[
                20 + yoff + 2048 - 2040, 20 + xoff + 2048 - 2050
            ] == pytest.approx(centerstamp[20 + yoff, 20 + xoff], abs=absoff)

    with pytest.raises(
        ValueError, match="ou24PSF.get_stamp called with x0 or y0 that does not match"
    ):
        _ = psfobj.get_stamp(2048.0, 2048.0)

    with pytest.raises(
        ValueError, match="ou24PSF.get_stamp called with x0 or y0 that does not match"
    ):
        _ = psfobj.get_stamp(2048.0, 2048.0, x0=2046, y0=2045)

    newstamp = psfobj.get_stamp(2048.0, 2048.0, x0=2050, y0=2040, seed=42)
    np.testing.assert_array_equal(stamp, newstamp)


def test_get_edge_centered_psf():
    # Try a PSF centered between two pixels.  Because of how we
    #   define 0.5 behavior in PSF.get_stamp, this should be
    #   centered to the *left* of the center of the image.
    psfobj = PSF.get_psf_object("STPSF", band="R062", sca=17, size=41.0)
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
    psfobj = PSF.get_psf_object("STPSF", band="R062", sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.5, 2048.5, x0=2050, y0=2046, seed=42)
    assert stamp.shape == (41, 41)
    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(18.22, abs=0.02)
    assert cy == pytest.approx(22.42, abs=0.03)
