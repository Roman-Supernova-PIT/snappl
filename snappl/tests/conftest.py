import pytest
import pathlib

import numpy as np

from astropy.io import fits

import tox # noqa: F401
from tox.pytest import init_fixture # noqa: F401

from snappl.image import FITSImage, OpenUniverse2024FITSImage, ManualFITSImage

from snpit_utils.config import Config


@pytest.fixture( scope='session', autouse = True )
def init_config():
    Config.init( '/snappl/snappl/tests/snappl_test_config.yaml', setdefault = True )


@pytest.fixture( scope='module' )
def ou2024imagepath():
    return str('/photometry_test_data/ou2024/images/simple_model/Y106/13205/'
               'Roman_TDS_simple_model_Y106_13205_1.fits.gz')


@pytest.fixture
def ou2024image( ou2024imagepath ):
    image = OpenUniverse2024FITSImage( ou2024imagepath, None, 11 )
    return image

@pytest.fixture
def manual_fits_image( ou2024imagepath):
    header = fits.open('/photometry_test_data/ou2024/images/simple_model/Y106/13205/'
                       'Roman_TDS_simple_model_Y106_13205_1.fits.gz')[0].header
    data = np.ones((25, 25), dtype = np.float32)
    noise = np.zeros((25, 25), dtype = np.float32)
    flags = np.zeros((25, 25), dtype = np.uint32)
    return ManualFITSImage(header, data, noise=noise, flags=flags)

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
# The hardcoded values are empirical.  I've used DS9 on the test
# image to verify that they're good to at least ~5 decimal places.
@pytest.fixture( scope='module' )
def check_wcs():
    def wcs_checker( wcs ):
        testdata = [ { 'x': 0, 'y': 0, 'ra': 7.49435552, 'dec': -44.95508301 },
                     { 'x': 4087, 'y': 4087, 'ra': 7.58168925, 'dec': -44.79212825 },
                     { 'x': 0, 'y': 4087, 'ra': 7.42167102, 'dec': -44.84398918   },
                     { 'x': 4087, 'y': 0, 'ra': 7.65461745, 'dec': -44.90311993 },
                     { 'x': 2043.5, 'y': 2043.5, 'ra': 7.53808422, 'dec': -44.87361374 } ]

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
