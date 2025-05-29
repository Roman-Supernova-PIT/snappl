import astropy
import galsim

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
