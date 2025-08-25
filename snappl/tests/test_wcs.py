import numpy as np

import astropy
import galsim
import gwcs

from snappl.wcs import BaseWCS, AstropyWCS, GalsimWCS, GWCS


def test_astropywcs( ou2024image, check_wcs ):
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )
    assert wcs._wcs_is_astropy
    check_wcs( wcs )

    wcs = AstropyWCS.from_header( ou2024image.get_fits_header() )
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )
    assert wcs._wcs_is_astropy
    check_wcs( wcs )

    apwcs = astropy.wcs.WCS( ou2024image.get_fits_header() )
    wcs = AstropyWCS( apwcs )
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )
    assert wcs._wcs_is_astropy
    check_wcs( wcs )


def test_galsimwcs( ou2024image, check_wcs ):
    wcs = GalsimWCS.from_header( ou2024image.get_fits_header() )
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


def test_if_ou2024image_wcs_invertible(ou2024image):
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


def test_gwcs( romandatamodel_image, check_wcs ):
    wcs = romandatamodel_image.get_wcs()
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, GWCS )
    assert isinstance( wcs._gwcs, gwcs.wcs.WCS )

    # This is just a regression test, since I've only used this code to find the values
    testdata = [ { 'x': 0, 'y': 0, 'ra': 79.99384677, 'dec': 29.97428036, },
                 { 'x': 4087, 'y': 4087, 'ra': 79.84864636, 'dec': 30.09743131 },
                 { 'x': 0, 'y': 4087, 'ra': 79.99377225, 'dec': 30.09721375 },
                 { 'x': 4087, 'y': 0, 'ra': 79.84966829, 'dec': 29.97460354 },
                 { 'x': 2043.5, 'y': 2043.5, 'ra': 79.92142552, 'dec': 30.03557704 } ]

    # These WCSes have more precise inverse than the ones we get from FITS files
    check_wcs( wcs, testdata, invabs=0.01, arcsecprecision=0.002 )

    # Test the astropy WCS approximation
    awcs = AstropyWCS( apwcs=wcs.get_astropy_wcs(degree=5) )
    check_wcs( awcs, testdata, arcsecprecision=0.002 )
