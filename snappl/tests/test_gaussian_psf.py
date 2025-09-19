import time
import pytest
import numpy as np
import scipy.ndimage
from snappl.psf import PSF


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

    # Make sure stretcy is right
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
    import pdb; pdb.set_trace()
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
    #   won't be subject to excessive clipping at the edges
    gpsf = PSF.get_psf_object( 'gaussian', sigmax=0.2, sigmay=0.2, stamp_size=7 )

    stamp = gpsf.get_stamp( x=5, y=5, x0=5, y0=5 )
    assert stamp.shape == (7, 7)
    cx, cy = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 3., abs=0.01 )
    assert cy == pytest.approx( 3., abs=0.01 )

    stamp = gpsf.get_stamp( x=5, y=5, x0=6, y0=6 )
    cx, cy = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 2., abs=0.01 )
    assert cy == pytest.approx( 2., abs=0.01 )

    stamp = gpsf.get_stamp( x=5.2, y=5.7, x0=5, y0=5 )
    cx, cy = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 3.2, abs=0.01 )
    assert cy == pytest.approx( 2.7, abs=0.01 )

    stamp = gpsf.get_stamp( x=5.7, y=5.2, x0=5, y0=5 )
    cx, cy = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 2.7, abs=0.01 )
    assert cy == pytest.approx( 3.2, abs=0.01 )

    stamp = gpsf.get_stamp( x=5.5, y=5.5, x0=5, y0=5 )
    cx, cy = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 2.5, abs=0.01 )
    assert cy == pytest.approx( 2.5, abs=0.01 )

    stamp = gpsf.get_stamp( x=5.5, y=5.5, x0=4, y0=4 )
    cx, cy = scipy.ndimage.center_of_mass( stamp )
    assert cx == pytest.approx( 3.5, abs=0.01 )
    assert cy == pytest.approx( 3.5, abs=0.01 )
