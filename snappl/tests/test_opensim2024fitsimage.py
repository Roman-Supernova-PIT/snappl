# TODO -- remove these next few lines!
# This needs to be set up in an environment
# where snappl is available.  This will happen "soon"
# Get Rob to fix all of this.  For now, this is a hack
# so you can work short term.
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent/"extern/snappl"))
# End of lines that will go away once we do this right. (<-- From Rob.)

import numpy as np
from snappl.image import OpenUniverse2024FITSImage
import astropy
import pytest
from snpit_utils.logger import SNLogger


def test_get_cutout():
    imagepath = str(pathlib.Path(__file__).parent/'image_test_data/Roman_TDS_simple_model_F184_662_11.fits.gz')
    image = OpenUniverse2024FITSImage(imagepath, None, 11)
    ra, dec = 7.5942407686430995, -44.180904726970695
    cutout = image.get_ra_dec_cutout(ra, dec, 5)
    comparison_cutout = np.load(str(pathlib.Path(__file__).parent/'image_test_data/test_cutout.npy'),
                                allow_pickle=True)
    message = "The cutout does not match the comparison cutout"
    assert np.array_equal(cutout._data, comparison_cutout), message
    # I am directly comparing for equality here because these numbers should
    # never actually change, provided the underlying image is unaltered. -Cole

    # Now we intentionally try to get a no overlap error.
    with pytest.raises(astropy.nddata.utils.NoOverlapError) as excinfo:
        ra, dec = 7.6942407686430995, -44.280904726970695
        cutout = image.get_ra_dec_cutout(ra, dec, 5)
    message = f"This should have caused a NoOverlapError but was actually {str(excinfo.value)}"
    assert 'do not overlap' in str(excinfo.value), message

    # Now we intentionally try to get a partial overlap error.
    with pytest.raises(astropy.nddata.utils.PartialOverlapError) as excinfo:
        ra, dec = 7.69380043,-44.13231831
        cutout = image.get_ra_dec_cutout(ra, dec, 55)
        message = f"This should have caused a PartialOverlapError but was actually {str(excinfo.value)}"
        assert 'partial' in str(excinfo.value), message


def test_set_data():
    imagepath = str(pathlib.Path(__file__).parent/'image_test_data/Roman_TDS_simple_model_F184_662_11.fits.gz')
    image = OpenUniverse2024FITSImage(imagepath, None, 11)

    with pytest.raises(ValueError) as excinfo:
        image.data = 'cheese'
        SNLogger.debug(image.data)
    message = f"This should have caused a ValueError but was actually {str(excinfo.value)}"
    assert 'must be a' in str(excinfo.value), message
    old_data = image.get_data()[0]
    image._data = old_data + 1
    assert np.array_equal(image._data, old_data + 1), "The data was not set correctly"
