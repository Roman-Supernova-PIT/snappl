import pytest
import pathlib

import numpy as np

import tox # noqa: F401
from tox.pytest import init_fixture # noqa: F401

from snappl.image import FITSImage, OpenUniverse2024FITSImage

from snpit_utils.config import Config


@pytest.fixture( scope='session', autouse = True )
def init_config():
    Config.init( '/home/snappl/snappl/tests/snappl_test_config.yaml', setdefault = True )


@pytest.fixture( scope='module' )
def ou2024imagepath():
    return str(pathlib.Path(__file__).parent/'image_test_data/Roman_TDS_simple_model_F184_662_11.fits.gz')


@pytest.fixture
def ou2024image( ou2024imagepath ):
    image = OpenUniverse2024FITSImage( ou2024imagepath, None, 11 )
    return image


# If you use this next fixture, you aren't supposed
#   to modify the image!  Make sure any modifications
#   you make are undone at the end of your test.
@pytest.fixture( scope='module' )
def ou2024image_module( ou2024imagepath ):
    """A module-scope test image with data loaded."""
    image = OpenUniverse2024FITSImage( ou2024imagepath, None, 11 )
    image.get_data( which='all', cache=True )
    image.get_wcs()
    return image


# If you use this next fixture, you aren't supposed
#   to modify the image!  Make sure any modifications
#   you make are undone at the end of your test.
@pytest.fixture( scope='module' )
def fitsimage_module( ou2024imagepath, ou2024image_module ):
    # Hack our way into having an object of the FITSImage type.
    #   Normally you don't instantiate a FITS image, but for our tests
    #   builde one up.  Never do something like this (i.e. accessing the
    #   underscored members of an object) in code outside this test
    #   fixture.
    fitsim = FITSImage( ou2024imagepath, None, 11 )
    orighdr = ou2024image_module._header
    fitsim._header = ou2024image_module._get_header()
    fitsim._wcs = ou2024image_module._wcs
    # Undo the internal change that _get_header made to ou2024image
    ou2024image._header = orighdr
    img, noi, flg = ou2024image_module.get_data( always_reload=False )
    fitsim._data = img
    fitsim._noise = noi
    fitsim._flags = flg

    return fitsim


# This next fixture will only work on the WCS extracted from ou2024image
# The hardcoded values are empirical.  We should probably compare them to
# (say) DS9, or to something else, to make sure they're really good.
@pytest.fixture( scope='module' )
def check_wcs():
    def wcs_checker( wcs ):
        testdata = [ { 'x': 0, 'y': 0, 'ra': 7.49441896, 'dec': -44.22945209 },
                     { 'x': 4087, 'y': 4087, 'ra': 7.69394648, 'dec': -44.13224703 },
                     { 'x': 0, 'y': 4087, 'ra': 7.52381115, 'dec': -44.11151047 },
                     { 'x': 4087, 'y': 0, 'ra': 7.66488541, 'dec': -44.25023227 },
                     { 'x': 2043.5, 'y': 2043.5, 'ra': 7.59426518, 'dec': -44.18089283 } ]

        for data in testdata:
            ra, dec = wcs.pixel_to_world( data['x'], data['y'] )
            assert isinstance( ra, float )
            assert isinstance( dec, float )
            assert ra == pytest.approx( data['ra'], abs=0.01/3600./np.cos(data['dec'] * np.pi/180.))
            assert dec == pytest.approx( data['dec'], abs=0.01/3600. )

            # ...I would have expected better than this, but empirically the
            # WCS as compared to the inverse WCS are only good to several
            # hundreths of a pixel.
            x, y = wcs.world_to_pixel( data['ra'], data['dec'] )
            assert isinstance( x, float )
            assert isinstance( y, float )
            assert x == pytest.approx( data['x'], abs=0.1 )
            assert y == pytest.approx( data['y'], abs=0.1 )

        xvals = np.array( [ t['x'] for t in testdata ] )
        yvals = np.array( [ t['y'] for t in testdata ] )
        ravals = np.array( [ t['ra'] for t in testdata ] )
        decvals = np.array( [ t['dec'] for t in testdata ] )

        ras, decs = wcs.pixel_to_world( xvals, yvals )
        assert isinstance( ras, np.ndarray )
        assert isinstance( decs, np.ndarray )
        assert np.all( ras == pytest.approx(ravals, abs=0.01/3600./np.cos(decs[0] * np.pi/180.) ) )
        assert np.all( decs == pytest.approx(decvals, abs=0.01/3600. ) )

        xs, ys = wcs.world_to_pixel( ravals, decvals )
        assert isinstance( xs, np.ndarray )
        assert isinstance( ys, np.ndarray )
        assert np.all( xs == pytest.approx( xvals, abs=0.1 ) )
        assert np.all( ys == pytest.approx( yvals, abs=0.1 ) )

    return wcs_checker
