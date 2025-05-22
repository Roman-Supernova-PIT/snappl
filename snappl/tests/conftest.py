import pytest
import pathlib

import tox # noqa: F401
from tox.pytest import init_fixture # noqa: F401

from snappl.image import FITSImage, OpenUniverse2024FITSImage


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
