import yaml
import random
import pathlib
import pytest

import numpy as np

from snappl.psf import YamlSerialized_OversampledImagePSF


@pytest.fixture
def testpsf():
    loaded = np.load('psf_test_data/testpsfarray.npz')
    arr = loaded['args']
    mypsf = YamlSerialized_OversampledImagePSF.create( arr, 3832., 255., oversample_factor=3. )
    return mypsf


def test_write( testpsf ):
    barf = pathlib.Path( ''.join( random.choices( 'abcdefghijklmnopqrstuvwxyz', k=10 ) ) )
    try:
        testpsf.write( barf )

        y = yaml.safe_load( open(barf) )
        assert isinstance( y, dict )
        assert y['x0'] == 3832.
        assert y['y0'] == 255.
        assert y['oversamp'] == 3.
        assert y['shape0'] == 77
        assert y['shape1'] == 77
        assert isinstance( y['data'], str )
    finally:
        barf.unlink( missing_ok=True )


def test_read( testpsf ):
    barf = pathlib.Path( ''.join( random.choices( 'abcdefghijklmnopqrstuvwxyz', k=10 ) ) )
    try:
        testpsf.write( barf )

        bpsf = YamlSerialized_OversampledImagePSF()
        bpsf.read( barf )
        assert bpsf._x == 3832.
        assert bpsf._y == 255.
        assert bpsf._oversamp == 3.
        assert bpsf._data.shape == (77,77)
        assert bpsf._data.sum() == pytest.approx( 1., rel=1e-9 )
    finally:
        barf.unlink( missing_ok=True )
