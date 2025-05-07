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


def test_get_cutout():
    roman_path = '/hpc/group/cosmology/OpenUniverse2024'
    truth = 'simple_model'
    band = 'F184'
    pointing = 662
    SCA = 11
    imagepath = roman_path + (f'/RomanTDS/images/{truth}/{band}/{pointing}'
                              f'/Roman_TDS_{truth}_{band}_{pointing}_'
                              f'{SCA}.fits.gz')
    image = OpenUniverse2024FITSImage(imagepath, None, SCA)
    ra, dec = 7.5942407686430995, -44.180904726970695
    cutout = image.get_cutout(ra, dec, 5)
    comparison_cutout = np.load(str(pathlib.Path(__file__).parent/'image_test_data/test_cutout.npy'),
                                allow_pickle=True)
    message = "The cutout does not match the comparison cutout"
    assert np.array_equal(cutout._data, comparison_cutout), message
    # I am directly comparing for equality here because these numbers should
    # never actually change, provided the underlying image is unaltered. -Cole

    # Now we intentionally try to get a no overlap error.
    try:
        ra, dec = 7.6942407686430995, -44.280904726970695
        cutout = image.get_cutout(ra, dec, 5)
        assert False, 'That should not have worked...'
    except Exception as e:
        message = f"This should have caused a NoOverlapError but was actually {e}"
        assert isinstance(e, astropy.nddata.utils.NoOverlapError), message

    # Now we intentionally try to get a partial overlap error.
    try:
        ra, dec = 7.69380043,-44.13231831
        cutout = image.get_cutout(ra, dec, 55)
        assert False, 'That should not have worked...'
    except Exception as e:
        message = f"This should have caused a PartialOverlapError but was actually {e}"
        assert isinstance(e, astropy.nddata.utils.PartialOverlapError), message
