import pytest
import numpy as np

import sys
sys.path.insert( 0, '.' )
from base_testimagepsf import BaseTestImagePSF

from snappl.psf import PSF, OversampledImagePSF


class TestOversampledImagePSF( BaseTestImagePSF ):
    __psfclass__ = OversampledImagePSF

    @pytest.fixture
    def testpsf( self ):
        loaded = np.load('psf_test_data/testpsfarray.npz')
        arr = loaded['args']
        mypsf = PSF.get_psf_object( "OversampledImagePSF", data=arr, x=3832., y=255.,
                                    oversample_factor=3., normalize=True )
        assert isinstance( mypsf, self.__psfclass__ )
        return mypsf

    def make_psf_for_test_stamp( self, x=1023, y=511, oversamp=3, sigmax=1.2, sigmay=None ):
        # Make a 3x oversampled PSF that's a gaussian with sigma 1.2 (in
        # image pixel units, not oversampled units).  2√(2ln2)*1.2 = FWHM of
        # 2.83, so for a radius of 5 FWHMs (to be really anal), we want a
        # 29×29 stamp in image units.
        #
        # 3× oversampled means an 87×87 data array.  87 // 2 = 43
        # 5× oversampled means a 145×145 data array.  145 // 2 = 72
        xc = np.floor( x + 0.5 )
        yc = np.floor( y + 0.5 )

        sigmay = sigmax if sigmay is None else sigmay

        assert isinstance( oversamp, int )
        size = int( np.ceil( oversamp * 29 ) )
        size += 1 if size % 2 == 0 else 0
        ctr = size // 2

        xvals = np.arange( -ctr, ctr+1 ) + oversamp * ( np.floor( x + 0.5 ) - x )
        yvals = np.arange( -ctr, ctr+1 ) + oversamp * ( np.floor( y + 0.5 ) - y )
        ovsigmax = oversamp * sigmax
        ovsigmay = oversamp * sigmay
        data = np.exp( -( xvals[np.newaxis,:]**2 / ( 2. * ovsigmax**2 ) +
                          yvals[:,np.newaxis]**2 / ( 2. * ovsigmay**2 ) ) )
        data /= data.sum()
        psf = PSF.get_psf_object( "OversampledImagePSF", data=data, x=x, y=y, oversample_factor=oversamp )

        datacx = size // 2 + ( x - xc ) * oversamp
        datacy = size // 2 + ( y - yc ) * oversamp

        return psf, datacx, datacy


    def test_get_stamp_orientation( self ):
        self.run_test_get_stamp_orientation()

    def test_get_stamp_centered_oversampled( self ):
        self.run_test_get_stamp_centered_oversampled()

    @pytest.mark.xfail( reason="We know this doesn't work right yet." )
    def test_get_stamp_centered_oversampled_with_undersampled_psf( self ):
        self.run_test_get_stamp_centered_oversampled( oversamp=3, sigma=0.3 )

    def test_get_stamp_offset_oversampled( self ):
        self.run_test_get_stamp_offset_oversampled()

    def test_get_imagepsf( self, testpsf ):
        self.run_test_get_imagepsf( testpsf, oversamp=3. )
