import pytest

import numpy as np
import astropy

from snappl.wcs import BaseWCS, AstropyWCS


# TODO : this is really a regression test,
#   not a unit test, since the test values
#   are empirical
# We should make sure all the SIP stuff and so
#   forth is getting applied and we're
#   really getting precise positions!
#   Compare to DS9?
def test_astropywcs( ou2024image ):
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, BaseWCS )
    assert isinstance( wcs, AstropyWCS )
    assert isinstance( wcs._wcs, astropy.wcs.WCS )

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
