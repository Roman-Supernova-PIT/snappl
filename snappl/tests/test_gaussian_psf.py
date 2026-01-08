import time
import pytest
import numpy as np
import scipy.ndimage
from snappl.psf import PSF
from scipy.ndimage import center_of_mass


def test_gaussian_psf():

    # For σ=1-pixel, FWHM = 2.35, so size = 2*floor(5*FHWM) + 1 = 23
    gpsf = PSF.get_psf_object( 'gaussian', x=0, y=0, band='R062' )
    assert gpsf.stamp_size == 23
    t0 = time.perf_counter()
    stamp = gpsf.get_stamp( 0, 0 )
    t1 = time.perf_counter()
    restamp = gpsf.get_stamp( 0, 0 )
    t2 = time.perf_counter()
    assert np.all( stamp == restamp )
    # Should have used the cache the second time around, so
    #  should have been a lot faster not having to integrate.
    assert ( t2 - t1 ) < 0.1 * ( t1 - t0 )
    assert stamp.shape == ( gpsf.stamp_size, gpsf.stamp_size )
    assert stamp.sum() == pytest.approx( 1.0, abs=1e-9 )
    assert np.where( stamp.max() == stamp ) == ( np.array([11]), np.array([11]) )
    # 2nd moment along one axis should be σ².  It comes out a little off
    #   because this isn't a sampled gaussian, it's an integrated gaussian.
    mom2y = ( np.arange( -11, 12 )**2 * stamp[:, 11] ).sum() / stamp[:, 11].sum()
    mom2x = ( np.arange( -11, 12 )**2 * stamp[11, :] ).sum() / stamp[11, :].sum()
    assert mom2x == pytest.approx( 1.08, abs=0.01 )
    assert mom2y == pytest.approx( 1.08, abs=0.01 )

    # For σ=0.2 pixel, FWHM = 0.2 * 2.35, so size = 5
    gpsf = PSF.get_psf_object( 'gaussian', x=0, y=0, sigmax=0.2, sigmay=0.2, band='R062' )
    assert gpsf.stamp_size == 5
    stamp = gpsf.get_stamp( 0, 0 )
    assert stamp.shape == ( gpsf.stamp_size, gpsf.stamp_size )
    assert stamp.sum() == pytest.approx( 1.0, abs=1e-9 )
    assert np.where( stamp.max() == stamp ) == ( np.array([2]), np.array([2]) )
    # 2nd moments are much more off this undersampled, so don't bother

    # Make sure asymmetric PSFs render right
    gpsf = PSF.get_psf_object( 'gaussian', x=0, y=0, sigmax=0.3, sigmay=0.2, band='R062' )
    # σ=0.3 → FWHM=0.71, so size = 7
    assert gpsf.stamp_size == 7
    stamp = gpsf.get_stamp( 0, 0 )
    assert stamp.shape == ( gpsf.stamp_size, gpsf.stamp_size )
    assert stamp.sum() == pytest.approx( 1.0, abs=1e-9 )
    assert stamp[2, 3] == pytest.approx( stamp[4, 3], rel=1e-7 )
    assert stamp[3, 2] == pytest.approx( stamp[3, 4], rel=1e-7 )
    # Should be bigger in the x-direction; x is the second index
    assert stamp[3, 2] > stamp[2, 3]

    gpsf = PSF.get_psf_object( 'gaussian', x=0, y=0, sigmax=0.2, sigmay=0.3, band='R062' )
    # σ=0.3 → FWHM=0.71, so size = 7
    assert gpsf.stamp_size == 7
    stamp = gpsf.get_stamp( 0, 0 )
    assert stamp.shape == ( gpsf.stamp_size, gpsf.stamp_size )
    assert stamp.sum() == pytest.approx( 1.0, abs=1e-9 )
    assert stamp[2, 3] == pytest.approx( stamp[4, 3], rel=1e-7 )
    assert stamp[3, 2] == pytest.approx( stamp[3, 4], rel=1e-7 )
    # Should be bigger in the y-direction; y is the first index
    assert stamp[2, 3] > stamp[3, 2]

    # Test rotations
    gpsf45 = PSF.get_psf_object( 'gaussian', x=0, y=0., sigmax=0.3, sigmay=0.2, theta=45. )
    stamp45 = gpsf45.get_stamp( 0.5, 0.5 )
    assert stamp45[2, 2] == pytest.approx( stamp45[3, 3], rel=1e-7 )
    assert stamp45[3, 2] == pytest.approx( stamp45[2, 3], rel=1e-7 )
    assert stamp45[3, 3] > stamp45[3, 2]

    gpsf135 = PSF.get_psf_object( 'gaussian', x=0., y=0., sigmax=0.3, sigmay=0.2, theta=45. )
    stamp135 = gpsf135.get_stamp( 0.5, 0.5 )
    assert np.all( stamp45 == pytest.approx( stamp135.T, rel=1e-7 ) )

    gpsf30 = PSF.get_psf_object( 'gaussian', x=0., y=0., sigmax=0.3, sigmay=0.2, theta=30. )
    stamp30 = gpsf30.get_stamp( 0.5, 0.5 )
    assert stamp30[2, 2] == pytest.approx( stamp30[3, 3], rel=1e-7 )
    assert stamp30[3, 2] == pytest.approx( stamp30[2, 3], rel=1e-7 )
    assert stamp30[3, 3] > stamp30[3, 2]
    # Less of the flux has "rotated out of" the pixel offset in x by 0.5 at 30° as compared to 45°
    assert stamp30[3, 2] > stamp45[3, 2]

    # Test that centering all works right; see PSF.get_stamp documentation
    #   for how this is supposed to work.
    # Use a bigger stamp size so the "moment" centering that scipy.ndimage uses
    #   won't be subject to excessive clipping at the edges.
    #   (It's still going to be subject to the fact that scipy.ndimage.center_of_mass
    #   is assuming sampling, whereas we're doing integration, so they aren't
    #   consistently thinking about Gaussians.)
    gpsf = PSF.get_psf_object( 'gaussian', sigmax=0.2, sigmay=0.2, stamp_size=9 )

    stamp = gpsf.get_stamp( x=5, y=5, x0=5, y0=5 )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 4., abs=0.01 )
    assert cy == pytest.approx( 4., abs=0.01 )

    stamp = gpsf.get_stamp( x=5, y=5, x0=6, y0=6 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 3., abs=0.01 )
    assert cy == pytest.approx( 3., abs=0.01 )

    stamp = gpsf.get_stamp( x=5.2, y=5.7 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 4.066, abs=0.01 )     # ideally 4.2, but sampling
    assert cy == pytest.approx( 3.843, abs=0.01 )     # ideally 3.7, but sampling

    stamp = gpsf.get_stamp( x=5.7, y=5.2 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 3.843, abs=0.01 )     # ideally 3.7, but sampling
    assert cy == pytest.approx( 4.066, abs=0.01 )     # ideally 4.2, but sampling

    stamp = gpsf.get_stamp( x=5.2, y=5.7, x0=5, y0=5 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 4.066, abs=0.01 )     # ideally 4.2, but sampling
    assert cy == pytest.approx( 4.843, abs=0.01 )     # ideally 4.7, but sampling

    stamp = gpsf.get_stamp( x=5.7, y=5.2, x0=5, y0=5 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 4.843, abs=0.01 )     # ideally 4.7, but sampling
    assert cy == pytest.approx( 4.066, abs=0.01 )     # ideally 4.2, but sampling

    stamp = gpsf.get_stamp( x=5.5, y=5.5 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 3.5, abs=0.01 )
    assert cy == pytest.approx( 3.5, abs=0.01 )

    stamp = gpsf.get_stamp( x=5.5, y=5.5, x0=6, y0=6 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 3.5, abs=0.01 )
    assert cy == pytest.approx( 3.5, abs=0.01 )

    stamp = gpsf.get_stamp( x=5.5, y=5.5, x0=5, y0=5 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 4.5, abs=0.01 )
    assert cy == pytest.approx( 4.5, abs=0.01 )

    stamp = gpsf.get_stamp( x=5.5, y=5.5, x0=4, y0=4 )
    cy, cx = scipy.ndimage.center_of_mass( stamp )
    assert stamp.shape == (9, 9)
    assert stamp.sum() == pytest.approx( 1.0, rel=1e-7 )
    assert cx == pytest.approx( 5.5, abs=0.01 )
    assert cy == pytest.approx( 5.5, abs=0.01 )


def test_galaxy_stamp():
    gpsf = PSF.get_psf_object("gaussian", x=0, y=0, band="R062", stamp_size = 71)
    # Test centering
    for x in [1000.0, 1000.25, 1000.5]:
        for y in [1000.0, 1000.25, 1000.5]:
            oversamp = 5
            x0 = 999
            y0 = 999
            midpix = gpsf.stamp_size // 2
            expected_center_x = midpix + x - x0
            expected_center_y = midpix + y - y0
            galaxy_stamp = gpsf.get_galaxy_stamp(x=x, y=y, x0=x0, y0=y0, flux=1e6, oversamp=oversamp)
            cy, cx = center_of_mass(galaxy_stamp)
            assert cx == pytest.approx(expected_center_x, abs=1/oversamp)
            assert cy == pytest.approx(expected_center_y, abs=1/oversamp)

    # Test total flux
    gpsf = PSF.get_psf_object("gaussian", x=0, y=0, band="R062", stamp_size=71)
    x=1000.0
    y=1000.0
    x0 = 1000
    y0 = 1000
    galaxy_stamp = gpsf.get_galaxy_stamp(x=x, y=y, x0=x0, y0=y0, flux=1e6, oversamp=8, bulge_R = 2, bulge_n=3,
    disk_R= 2, disk_n = 3)
    assert galaxy_stamp.sum() == pytest.approx(991866, rel=1e-3) # Empirically, only 99.1 % of flux is in 71x71 stamp
