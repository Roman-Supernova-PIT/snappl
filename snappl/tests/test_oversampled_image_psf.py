import yaml
import random
import pytest

import numpy as np
from astropy.io import fits

from snappl.psf import OversampledImagePSF

@pytest.fixture
def testpsf():
    loaded = np.load('psf_test_data/testpsfarray.npz')
    arr = loaded['args']
    mypsf = OversampledImagePSF.create( arr, 3832., 255., oversample_factor=3. )
    return mypsf

def test_create( testpsf ):
    assert testpsf._data.sum() == pytest.approx( 1., rel=1e-9 )


@pytest.mark.skip( reason="Comment out the skip to write some files for visual inspection" )
def test_interactive_write_stamp_to_fits_for_visual_inspection( testpsf ):
    fits.writeto( 'test_deleteme_orig.fits', testpsf._data, overwrite=True )
    fits.writeto( 'test_deleteme_resamp.fits', testpsf.get_stamp(), overwrite=True )

