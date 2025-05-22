import pytest

import numpy as np
import astropy

from snappl.image import FITSImage
from snappl.wcs import AstropyWCS


# ======================================================================
# FITSImage tests
# Note that some of these tests use the ou2024image fixtures.
#   The reason is that the functions we're testing requires some
#   stuff that isn't defined in FITSImage.  However, all the
#   tests in this section tests the functions which themselves
#   are defined in FITSImage.

def test_get_wcs( ou2024image, fitsimage_module ):
    assert isinstance( fitsimage_module._wcs, AstropyWCS )
    assert fitsimage_module.get_wcs() is fitsimage_module._wcs
    assert ou2024image._wcs is None
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, AstropyWCS )
    assert wcs is ou2024image._wcs


def test_get_cutout( ou2024image_module ):
    image = ou2024image_module
    assert image.image_shape == ( 4088, 4088 )
    cutout = image.get_cutout( 200, 400, 11 )
    assert isinstance( cutout, FITSImage )
    assert isinstance( cutout._data, np.ndarray )
    assert cutout.image_shape == ( 11, 11 )
    # Remember numpy arrays are indexed y, x
    assert np.all( cutout._data == image._data[ 395:406, 195:206  ] )
    assert np.all( cutout._noise == image._noise[ 395:406, 195:206 ] )
    assert np.all( cutout._flags == image._flags[ 395:406 , 195:206 ] )

    with pytest.raises( astropy.nddata.utils.PartialOverlapError ):
        _ = image.get_cutout( 5, 2048, 21 )

    with pytest.raises( astropy.nddata.utils.PartialOverlapError ):
        _ = image.get_cutout( 2048, 4085, 21 )

    with pytest.raises( astropy.nddata.utils.NoOverlapError ):
        _ = image.get_cutout( 2048, 4200, 21 )


def test_get_ra_dec_cutout( ou2024image_module ):
    image = ou2024image_module
    ra, dec = 7.5942407686430995, -44.180904726970695

    wcs = image.get_wcs()
    x, y = wcs.world_to_pixel( ra, dec )
    x = int( np.floor( x + 0.5 ) )
    y = int( np.floor( y + 0.5 ) )

    cutout = image.get_ra_dec_cutout(ra, dec, 5)
    # assert isinstance( cutout, FITSImage )    # Won't work because we didn't pass a FITSImage...
    assert cutout.image_shape == ( 5, 5 )

    assert np.all( cutout.data == image.data[ y-2:y+3, x-2:x+3 ] )

    # Now we intentionally try to get a no overlap error.
    with pytest.raises(astropy.nddata.utils.NoOverlapError):
        ra, dec = 7.6942407686430995, -44.280904726970695
        cutout = image.get_ra_dec_cutout(ra, dec, 5)

    # Now we intentionally try to get a partial overlap error.
    with pytest.raises(astropy.nddata.utils.PartialOverlapError):
        ra, dec = 7.69380043,-44.13231831
        cutout = image.get_ra_dec_cutout(ra, dec, 55)


def test_set_data( fitsimage_module ):
    image = fitsimage_module

    origim = image.data
    orignoi = image.noise
    origfl = image.flags
    try:
        image.data = origim + 1
        assert np.all( origim + 1 == image.data )
        image.noise = orignoi + 1
        assert np.all( orignoi + 1 == image.noise )
        image.flags = origfl + 1
        assert np.all( origfl + 1 == image.flags )

        with pytest.raises( TypeError, match="Data must be a 2d numpy array of floats." ):
            image.data = 'cheese'
        with pytest.raises( TypeError, match="Data must be a 2d numpy array of floats." ):
            image.data = origfl
        with pytest.raises( TypeError, match="Data must be a 2d numpy array of floats." ):
            image.data = np.array( [1., 2., 3.] )
        with pytest.raises( TypeError, match="Flags must be a 2d numpy array of integers." ):
            image.flags = origim
        with pytest.raises( TypeError, match="Flags must be a 2d numpy array of integers." ):
            image.flags = np.array( [1, 2, 3] )

    finally:
        # Gotta restore the module-scope fixture's data!
        image._data = origim
        image._noise = orignoi
        image._flags = origfl


# ======================================================================
# OpenUniverse2024FITSImage tests

def test_get_data( ou2024image ):
    try:
        # Notice the types are explicitly called out as big-endian below, even
        #   if the architecture of the system  is little-endian.  This is because
        #   FITS files are defined to be big-endian, and astropy reads them
        #   straight.  (...except that the integer flags don't seem to
        #   be big-endian, so I am confused as to what astropy and/or fitsio
        #   and/or numpy really does.)
        data, = ou2024image.get_data( 'data' )
        assert isinstance( data, np.ndarray )
        assert data.shape == ( 4088, 4088 )
        assert data.dtype == ">f8"
        assert data[2004:2084, 2004:2084].sum() == pytest.approx( 2500099.0, rel=1e-5 )

        noise, = ou2024image.get_data( 'noise' )
        assert isinstance( noise, np.ndarray )
        assert noise.shape == ( 4088, 4088 )
        assert noise.dtype == ">f4"
        assert noise[2004:2084, 2004:2084].sum() == pytest.approx( 2443894.0, rel=1e-5 )

        flags, = ou2024image.get_data( 'flags' )
        assert isinstance( flags, np.ndarray )
        assert flags.shape == ( 4088, 4088 )
        assert flags.dtype == "uint32"
        assert flags[2004:2084, 2004:2048].sum() == 0

        assert ou2024image._data is None
        assert ou2024image._noise is None
        assert ou2024image._flags is None

        data2, noise2, flags2 = ou2024image.get_data()
        assert data2 is not data
        assert noise2 is not noise
        assert flags2 is not flags
        assert np.all( data2 == data )
        assert np.all( noise2 == noise )
        assert np.all( flags2 == flags )
        assert ou2024image._data is None
        assert ou2024image._noise is None
        assert ou2024image._flags is None

        props = [ 'data', 'noise', 'flags' ]
        for prop in props:
            res = ou2024image.get_data( prop, cache=True )
            assert isinstance( res, list )
            assert len(res) == 1
            assert isinstance( res[0], np.ndarray )
            assert res[0].shape == ( 4088, 4088 )
            assert res[0] is getattr( ou2024image, f"_{prop}" )
            assert isinstance( ou2024image._header, astropy.io.fits.header.Header )
            for otherprop in props:
                if otherprop == prop:
                    continue
                assert getattr( ou2024image, f"_{otherprop}" ) is None
            setattr( ou2024image, f"_{prop}", None)
            setattr( ou2024image, "_header", None )

        data3, noise3, flags3 = ou2024image.get_data( cache=True )
        assert isinstance( ou2024image._header, astropy.io.fits.header.Header )
        assert np.all( data3 == data )
        assert np.all( noise3 == noise )
        assert np.all( flags3 == flags )
        assert data3 is not data
        assert noise3 is not noise
        assert flags3 is not flags
        assert data3 is ou2024image._data
        assert noise3 is ou2024image._noise
        assert flags3 is ou2024image._flags

        data4, noise4, flags4 = ou2024image.get_data( always_reload=True )
        assert data3 is ou2024image._data
        assert noise3 is ou2024image._noise
        assert flags3 is ou2024image._flags
        assert data4 is not data3
        assert noise4 is not noise3
        assert flags4 is not flags3
        assert np.all( data4 == data )
        assert np.all( noise4 == noise )
        assert np.all( flags4 == flags )
    finally:
        # ...I don't think there's anything needing cleaning up
        # We didn't use the module-scope fixture
        pass


def test_band( ou2024image_module ):
    assert ou2024image_module.band == 'F184'


def test_get_header( ou2024image, ou2024image_module ):
    assert isinstance( ou2024image_module._header, astropy.io.fits.header.Header )
    assert ou2024image_module._header == ou2024image_module._get_header()
    assert ou2024image._header is None
    hdr = ou2024image._get_header()
    assert isinstance( hdr, astropy.io.fits.header.Header )
    assert hdr is ou2024image._header
