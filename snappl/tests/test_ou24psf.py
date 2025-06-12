import os
import pytest

from astropy.io import fits

from snappl.psf import ou24PSF

# This test won't work on github until we get the right subset of galsim data
#   properly imported.
@pytest.mark.skipif( os.getenv('GITHUB_SKIP'), "Skipping test until we have galsim data" )
def test_get_stamp():
    psfobj = ou24PSF( pointing=6, sca=17, size=41. )

    stamp = psfobj.get_stamp( 2048, 2048 )
    fits.io.write_to( 'deleteme.fits', stamp, overwrite=True )
    
    
