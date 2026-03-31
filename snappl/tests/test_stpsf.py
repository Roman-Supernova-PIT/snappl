import pytest

import numpy as np
import scipy

from snappl.psf import PSF


def test_normalization():
    """Verify normalization of PSF for different stamp sizes.

    Specifically, verify that a big-enough PSF is close to 1
    and that smaller stamps have a normalization such that they
    match the sum of the subset of the big PSF stamp.
    """
    bigsize = 501
    mediumsize = 201
    smallsize = 41
    # Using the same seed here probably isn't doing what we want it to do,
    #   i.e. creating the same realization of the PSF that then gets
    #   downsampled.  But, maybe it is.  Someone should go read the code to find out.
    seed = 42

    bigpsfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=bigsize)
    bigstamp = bigpsfobj.get_stamp(seed=seed)
    assert bigstamp.shape == (bigsize, bigsize)

    mediumpsfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=mediumsize)
    mediumstamp = mediumpsfobj.get_stamp(seed=seed)
    assert mediumstamp.shape == (mediumsize, mediumsize)

    smallpsfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=smallsize)
    smallstamp = smallpsfobj.get_stamp(seed=seed)
    assert smallstamp.shape == (smallsize, smallsize)

    assert bigstamp.sum() == pytest.approx(1.0, abs=0.001)

    x0 = bigsize // 2 - mediumsize // 2
    x1 = x0 + mediumsize
    assert mediumstamp.sum() == pytest.approx(bigstamp[x0:x1, x0:x1].sum(), rel=1e-5)

    x0 = bigsize // 2 - smallsize // 2
    x1 = x0 + smallsize
    assert smallstamp.sum() == pytest.approx(bigstamp[x0:x1, x0:x1].sum(), rel=1e-5)


def test_get_centered_psf():
    psfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=41)

    # Try a basic centered PSF
    stamp = psfobj.get_stamp(seed=42)
    assert stamp.shape == (41, 41)
    # 2026-02-14 MWV: H158 comes out to 0.979.  See test_normalization for implicit comparison.
    assert stamp.sum() == pytest.approx(0.979, abs=0.001)

    cy, cx = scipy.ndimage.center_of_mass(stamp)
    # The roman PSF is asymmetric, so we don't expect the CoM to be the exact center.
    # The comparison numbers are what MWV go when adapting this test for STPSF
    assert cx == pytest.approx(19.856, abs=0.01)
    assert cy == pytest.approx(19.911, abs=0.01)


def test_get_offcenter_psf():
    # Try an offcenter PSF that's still centered on a pixel
    # The wings of the Roman WFI are quite large, so the centroiding
    # doesn't come out quite precise when the PSF is offset this much.

    x, y = 2048.0, 2048.0
    x0, y0 = 2050, 2040
    stamp_size = 41
    psfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=41.0)
    centerstamp = psfobj.get_stamp(x, y, seed=42)

    stamp = psfobj.get_stamp(x, y, x0=x0, y0=y0, seed=42)
    assert stamp.shape == (stamp_size, stamp_size)

    # Reversed because we're directly looking at the ndarray which is y, x
    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(19.856 + (x - x0), abs=0.2)
    assert cy == pytest.approx(19.911 + (y - y0), abs=0.2)

    # This stamp should just be a shifted version of centerstamp; verify
    #   that.  This check should be much more precise than the
    #   centroids, as wing-cutting won't matter for this check.
    # (Not *exactly* because centerstamp is at 2044,2044, not x,
    #   x, but the PSF can't vary much over 4 pixels...)
    absoff = 0.004 * centerstamp[stamp_size // 2, stamp_size // 2]
    for xoff in [-1, 0, 1]:
        for yoff in [-1, 0, 1]:
            assert stamp[stamp_size // 2 + yoff + int(y - y0), stamp_size // 2 + xoff + int(x - x0)] \
                    == pytest.approx(centerstamp[stamp_size // 2 + yoff, stamp_size // 2 + xoff], abs=absoff)


def test_get_edge_centered_psf():
    # Try a PSF centered between two pixels.  Because of how we
    #   define 0.5 behavior in PSF.get_stamp, this should be
    #   centered to the *left* of the center of the image.
    psfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.5, 2048.0, seed=42)
    assert stamp.shape == (41, 41)
    assert stamp.sum() == pytest.approx(0.979, abs=0.001)

    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(19.40, abs=0.02)
    assert cy == pytest.approx(19.911, abs=0.02)


def test_get_corner_centered_psf():
    # Try a PSF centered between four pixels.  Because of how we
    #   define 0.5 behavior in PSF.get_stamp, this should be
    #   centered to the *left* and *down* of the center of the image.
    psfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.5, 2048.5, seed=42)
    assert stamp.shape == (41, 41)
    assert stamp.sum() == pytest.approx(0.979, abs=0.001)

    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(19.40, abs=0.02)
    assert cy == pytest.approx(19.45, abs=0.02)


def test_get_offset_corner_centered_psf():
    # Try an offcenter PSF that's centered on a corner
    # The PSF center should be at -1.5, +2.5 pixels
    # relative to the stamp center... but then
    # offset because of the asymmetry of the roman PSF.
    psfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.5, 2048.5, x0=2050, y0=2046, seed=42)
    assert stamp.shape == (41, 41)

    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(18.40, abs=0.02)
    assert cy == pytest.approx(22.40, abs=0.03)


def test_get_offset_psf():
    """Test generating a non half-pixel offset."""
    psfobj = PSF.get_psf_object("STPSF", band="H158", sca=17, size=41.0)
    stamp = psfobj.get_stamp(2048.2, 2048.8, seed=42)
    assert stamp.shape == (41, 41)

    cy, cx = scipy.ndimage.center_of_mass(stamp)
    assert cx == pytest.approx(20.05, abs=0.05)
    assert cy == pytest.approx(19.8, abs=0.05)
