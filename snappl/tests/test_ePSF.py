import yaml
import random
import pytest

import numpy as np
from astropy.io import fits

from snappl.psf import ePSF

@pytest.fixture
def testepsf():
    loaded = np.load('psf_test_data/testpsfarray.npz')
    arr = loaded['args']
    mypsf = ePSF.create( arr, 3832., 255., oversample_factor=3. )
    return mypsf

def test_create( testepsf ):
    assert testepsf._data.sum() == pytest.approx( 1., rel=1e-9 )


@pytest.mark.skip( reason="Comment out the skip to write some files for visual inspection" )
def test_interactive_write_stamp_to_fits_for_visual_inspection( testepsf ):
    fits.writeto( 'test_deleteme_orig.fits', testepsf._data, overwrite=True )
    fits.writeto( 'test_deleteme_resamp.fits', testepsf.get_stamp(), overwrite=True )

