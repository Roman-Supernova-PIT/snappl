import astropy
import galsim
import numpy as np
from snappl.wcs import BaseWCS, AstropyWCS, GalsimWCS


def test_astropywcs( ou2024image, check_wcs ):
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )
    assert wcs._wcs_is_astropy
    check_wcs( wcs )

    # Using ou2024image._get_header() here, which is naughty; we
    #   aren't supposed to use underscore functions outside
    #   the class.  But, this is a test, and we know that
    #   it's a OpenUniverse2024FITSImage.
    wcs = AstropyWCS.from_header( ou2024image._get_header() )
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )
    assert wcs._wcs_is_astropy
    check_wcs( wcs )

    apwcs = astropy.wcs.WCS( ou2024image._get_header() )
    wcs = AstropyWCS( apwcs )
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )
    assert wcs._wcs_is_astropy
    check_wcs( wcs )


def test_galsimwcs( ou2024image, check_wcs ):
    # Again, naughty use of _get_header
    wcs = GalsimWCS.from_header( ou2024image._get_header() )
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, GalsimWCS )
    assert wcs._wcs is None
    assert not wcs._wcs_is_astropy
    assert isinstance( wcs._gsimwcs, galsim.AstropyWCS )
    check_wcs( wcs )

    wcs =  GalsimWCS( gsimwcs = wcs._gsimwcs )
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, GalsimWCS )
    assert wcs._wcs is None
    assert not wcs._wcs_is_astropy
    assert isinstance( wcs._gsimwcs, galsim.AstropyWCS )
    check_wcs( wcs )


def test_get_astropywcs_get_galsimwcs( ou2024image, check_wcs ):
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, AstropyWCS )
    rawgswcs = wcs.get_galsim_wcs()
    assert isinstance( rawgswcs, galsim.AstropyWCS )
    gswcs = GalsimWCS( rawgswcs )
    check_wcs( gswcs )


def test_if_wcs_invertible(ou2024image):
    # OpenUniverse Images are in fk5 coordinates, i.e. they use
    # EQUINOX = 2000.0, but astropy SkyCoord defaults to ICRS.
    # Therefore, we enforce the frame to match the radesys of the WCS.
    # This test ensures this is done properly by converting (0,0) in pixel
    # coordinates into ra, dec coordinates and back. If we do this right,
    # we should get back (0,0) in pixel coordinates again with a tolerance of
    # about 1e-9 pixels. -Cole 6/2/2025
    # Astropy docs:
    # https://docs.astropy.org/en/stable/api/astropy.coordinates.SkyCoord.html
    # "Type of coordinate frame this SkyCoord should represent.
    # Defaults to to ICRS if not given or given as None.""
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, AstropyWCS )
    ra_dec = wcs.pixel_to_world(0, 0)
    x_y_pixel = wcs.world_to_pixel(ra_dec[0], ra_dec[1])
    assert np.abs(x_y_pixel[0]) < 1e-9, 'x coordinate did not invert properly'
    assert np.abs(x_y_pixel[1]) < 1e-9, 'y coordinate did not invert properly'
