import pytest
import time

import numpy as np
import scipy
from astropy.io import fits

from snpit_utils.logger import SNLogger
from snappl.psf import OversampledImagePSF


@pytest.fixture
def testpsf():
    loaded = np.load('psf_test_data/testpsfarray.npz')
    arr = loaded['args']
    mypsf = OversampledImagePSF.create( arr, 3832., 255., oversample_factor=3. )
    return mypsf


def test_create( testpsf ):
    assert testpsf._data.sum() == pytest.approx( 1., rel=1e-9 )
    # data array was 77×77, we are oversampled by 3x, so nominally
    #  it's 25.7×25.7 on the image.  But, the array size is an integer,
    #  and it floors, so we should get 25
    assert testpsf.stamp_size == 25
    assert testpsf.clip_size == 25
    assert testpsf.oversample_factor == 3
    assert testpsf.x == 3832.
    assert testpsf.y == 255.
    loaded = np.load( 'psf_test_data/testpsfarray.npz' )
    arr = loaded['args']
    assert np.all( arr / arr.sum() == testpsf.oversampled_data )
    # TODO : test that normalize=False works


@pytest.mark.skip( reason="Comment out the skip to write some files for visual inspection" )
def test_interactive_write_stamp_to_fits_for_visual_inspection( testpsf ):
    fits.writeto( 'test_deleteme_orig.fits', testpsf._data, overwrite=True )
    fits.writeto( 'test_deleteme_resamp.fits', testpsf.get_stamp(), overwrite=True )


def make_psf_for_test_stamp( x=1023, y=1023, oversamp=3 ):
    # Make a 3x oversampled PSF that's a gaussian with sigma 1.2 (in
    # image pixel units, not oversampled units).  2√(2ln2)*1.2 = FWHM of
    # 2.83, so for a radius of 5 FWHMs (to be really anal), we want a
    # 29×29 stamp in image units.
    #
    # 3× oversampled means an 87×87 data array.  87 // 2 = 43
    # 5× oversampled means a 145×145 data array.  145 // 2 = 72

    assert isinstance( oversamp, int )
    size = int( np.ceil( oversamp * 29 ) )
    size += 1 if size % 2 == 0 else 0
    ctr = size // 2

    xvals = np.arange( -ctr, ctr+1 ) + oversamp * ( np.floor( x + 0.5 ) - x )
    yvals = np.arange( -ctr, ctr+1 ) + oversamp * ( np.floor( y + 0.5 ) - y )
    sigma = 1.2
    ovsigma = oversamp * sigma
    data = np.exp( -( xvals[np.newaxis,:]**2 + yvals[:,np.newaxis]**2 ) / ( 2. * ovsigma**2 ) )
    data /= data.sum()
    psf = OversampledImagePSF.create( data=data, x=x, y=y, oversample_factor=oversamp )

    return psf


# "centered" here means the original PSF is centered; we're going to
#   render it offset
def test_get_stamp_centered_oversampled():
    psf = make_psf_for_test_stamp()

    # If we just get_stamp(), we should get a 29×29 image centered on the middle
    # We don't actually really expect the stamp to be exactly expectedgauss, because
    #   the interpolation in get_stamp() is more sophisticated than just "evaluate
    #   the gaussian at the point".  We should be oversampled enough, though, that
    #   it's damn close.
    clipx = np.arange( -14, 15 )
    clipy = np.arange( -14, 15 )
    sigma = 1.2
    expectedgauss = np.exp( -( clipx[np.newaxis,:]**2 + clipy[:,np.newaxis]**2 ) / ( 2. * sigma**2 ) )
    expectedgauss /= expectedgauss.sum()
    clip = psf.get_stamp()
    assert clip.shape == ( 29, 29 )
    # Doing an absolute, not a relative, comparison because where the gaussian is
    #   approximately zero, we don't need it to be identically 0
    assert np.all( clip == pytest.approx( expectedgauss, abs=0.001 / ( 29*29 ) ) )

    # Render a bunch that are offset and make sure they center up where
    # expected

    # When the relative position is offset by an integer from the place
    #   we evaluted the pixel at ((1023, 1023) in this case), the PSF
    #   should still be centered on the center pixel of the image.
    relpos = [ -2.5, -1.8, -1.4, -1.0,  -0.8, -0.1,  0.,  0.1,  0.8, 1.0, 1.4,   1.8,  2.5 ]
    ctrexp = [ 13.5, 14.2, 13.6,   14., 14.2, 13.9, 14., 14.1, 13.8, 14., 14.4, 13.8, 13.5 ]

    for xrel, xctr in zip( relpos, ctrexp ):
        for yrel, yctr in zip( relpos, ctrexp ):
            clip = psf.get_stamp( 1023 + xrel, 1023 + yrel )
            assert clip.shape == ( 29, 29 )
            cy, cx = scipy.ndimage.center_of_mass( clip )
            assert cx == pytest.approx( xctr, abs=0.01 )
            assert cy == pytest.approx( yctr, abs=0.01 )


# Test the scary case where we pass a PSF that's not centered on its natural clip
def test_get_stamp_offset_oversampled():

    n = 0
    t = 0

    oversamp = 3
    psfposes = [ 1023.3792, 1023., 1023.5, 1023.8 ]
    for xpos in psfposes:
        for ypos in psfposes:
            psf = make_psf_for_test_stamp( xpos, ypos, oversamp=oversamp )
            # Make sure the raw data array we passed is at the right spot
            xround = np.floor( xpos + 0.5 )
            yround = np.floor( ypos + 0.5 )
            cy, cx = scipy.ndimage.center_of_mass( psf.oversampled_data )
            assert cy == pytest.approx( ( 29 * oversamp ) // 2 + (ypos-yround) * oversamp, abs=0.01*oversamp )
            assert cx == pytest.approx( ( 29 * oversamp ) // 2 + (xpos-xround) * oversamp, abs=0.01*oversamp )


            # If we just get_stamp(), it will get it at the x, y we created with
            t0 = time.perf_counter()
            clip = psf.get_stamp()
            t += time.perf_counter() - t0
            n += 1
            assert clip.shape == ( 29, 29 )
            cy, cx = scipy.ndimage.center_of_mass( clip )
            assert cx == pytest.approx( 14. + (xpos-xround), abs=0.01 )
            assert cy == pytest.approx( 14. + (ypos-yround), abs=0.01 )


            relpos = [ -2.5, -1.0,  -0.8, -0.1,  0.,  0.1,  0.8, 2.5 ]
            ctrexp = [ 13.5,  14.,  14.2, 13.9, 14., 14.1, 13.8, 13.5 ]
            # OMG, N⁴
            for xrel, xctr in zip( relpos, ctrexp ):
                for yrel, yctr in zip( relpos, ctrexp ):
                    clip = psf.get_stamp( 1023 + xrel, 1023 + yrel )
                    assert clip.shape == ( 29, 29 )
                    cy, cx = scipy.ndimage.center_of_mass( clip )
                    assert cx == pytest.approx( xctr, abs=0.01 )
                    assert cy == pytest.approx( yctr, abs=0.01 )

    SNLogger.debug( f"Average get_stamp runtime: {t/n}" )
