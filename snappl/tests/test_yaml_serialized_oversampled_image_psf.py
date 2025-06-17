import yaml
import random
import pathlib
import pytest

import numpy as np

from snappl.psf import PSF, YamlSerialized_OversampledImagePSF


@pytest.fixture
def testpsf():
    loaded = np.load('psf_test_data/testpsfarray.npz')
    arr = loaded['args']
    arr /= arr.sum()
    mypsf = PSF.get_psf_object( "YamlSerialized_OversampledImagePSF", data=arr, x=3832., y=255., oversample_factor=3. )
    assert isinstance( mypsf, YamlSerialized_OversampledImagePSF )
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

        bpsf = PSF.get_psf_object( "YamlSerialized_OversampledImagePSF", x=0., y=0. )
        bpsf.read( barf )
        assert bpsf._x == 3832.
        assert bpsf._y == 255.
        assert bpsf._oversamp == 3.
        assert bpsf._data.shape == (77,77)
        assert bpsf._data.sum() == pytest.approx( 1., rel=1e-9 )
    finally:
        barf.unlink( missing_ok=True )
