import yaml
import random
import pytest

import numpy as np

from snappl.psf import ePSF, brandX_ePSF

@pytest.fixture
def testepsf():
    loaded = np.load('psf_test_data/testpsfarray.npz')
    arr = loaded['args']
    mypsf = brandX_ePSF.create( arr, 3832., 255., oversample_factor=3. )
    return mypsf

def test_write( testepsf ):
    barf = ''.join( random.choices( 'abcdefghijklmnopqrstuvwxyz', k=10 ) )
    testepsf.write( barf )
    
    y = yaml.safe_load( open(barf) )
    assert isinstance( y, dict )
    assert y['x0'] == 3832.
    assert y['y0'] == 255.
    assert y['oversamp'] == 3.
    assert y['shape0'] == 77
    assert y['shape1'] == 77
    assert isinstance( y['data'], str )

def test_read( testepsf ):
    barf = ''.join( random.choices( 'abcdefghijklmnopqrstuvwxyz', k=10 ) )
    testepsf.write( barf )

    bpsf = brandX_ePSF()
    bpsf.read( barf )
    assert bpsf._x0 == 3832.
    assert bpsf._y0 == 255.
    assert bpsf._oversamp == 3.
    assert bpsf._data.shape == (77,77)
    assert bpsf._data.sum() == pytest.approx( 1., rel=1e-9 )
