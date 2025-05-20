import pytest
import pathlib

import numpy as np
import astropy

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
    # Undo the internal change that _get_header made to ou2024image
    ou2024image._header = orighdr
    img, noi, flg = ou2024image_module.get_data( always_reload=False )
    fitsim._data = img
    fitsim._noise = noi
    fitsim._flags = flg

    return fitsim


# ======================================================================
# FITSImage tests

# Need to use the ou2024image_model fixture here because we need
#   _get_header, which isn't implemented in FITSImage.  However,
#   test_cutout is implemented in FITSImage, which is why this test is
#   here.
def test_cutout( ou2024image_module ):
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


@pytest.mark.skip( reason="Currently broken, see RuntimeError in image.py" )
def test_get_ra_dec_cutout( fitsimage_module ):
    image = fitsimage_module
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
