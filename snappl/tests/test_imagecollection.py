import pathlib
import pytest
import numpy as np

import snappl.image
from snappl.imagecollection import ImageCollection, ImageCollectionOU2024, ImageCollectionManualFITS
from snpit_utils.config import Config


def test_get_collection():
    with pytest.raises( ValueError, match=r"Unknown image collection foo \(subset None\)" ):
        ImageCollection.get_collection( "foo" )


def test_imagecollectionou2024_base_path():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )
    assert isinstance( col, ImageCollectionOU2024 )
    assert col.base_path == pathlib.Path( cfg.value('ou24.images') )


def test_imagecollectionou2024_get_image_path():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )

    path = col.get_image_path( 13205, 'Y106', 1 )
    assert path == pathlib.Path( cfg.value('ou24.images') ) / 'Y106/13205/Roman_TDS_simple_model_Y106_13205_1.fits.gz'


def test_imagecollectionou2024_get_image():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )

    expectedpath = pathlib.Path( cfg.value('ou24.images') ) / 'Y106/13205/Roman_TDS_simple_model_Y106_13205_1.fits.gz'
    img1 = col.get_image( path=expectedpath )
    assert isinstance( img1, snappl.image.OpenUniverse2024FITSImage )
    hdr = img1.get_fits_header()
    assert img1.path == expectedpath
    hdr = img1.get_fits_header()
    assert hdr['MJD-OBS'] == pytest.approx( 62170.424, abs=1e-3 )
    assert hdr['FILTER'] == 'Y106'
    assert isinstance( img1.data, np.ndarray )
    # assert img1.data.dtype == '>f8'
    assert img1.data.dtype == np.dtype('float64')
    assert img1.data.shape == ( 4088, 4088 )
    # assert img1.noise.dtype == '>f4'
    assert img1.noise.dtype == np.dtype('float32')
    assert img1.noise.shape == ( 4088, 4088 )
    assert img1.flags.dtype == np.dtype('uint32')
    assert img1.flags.shape == ( 4088, 4088 )

    img2 = col.get_image( pointing=13205, band='Y106', sca=1 )
    assert img2.path == img1.path
    assert np.all( img2.data == img1.data )


def test_imagecollectionou2024_find_images():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )

    # TODO, more tests, this is just a quick and basic
    imgs = col.find_images( filter='Y106', ra=7.5510934, dec=-44.8071811 )
    assert len(imgs) == 135


def test_imagecollectionmanualfits_create():
    with pytest.raises( RuntimeError, match="manual_fits collection needs a base path" ):
        col = ImageCollection.get_collection( 'manual_fits' )

    base_path = '/photometry_Test_data/ou2024/images/simple_model'
    col = ImageCollection.get_collection( 'manual_fits', base_path='/photometry_Test_data/ou2024/images/simple_model' )
    assert isinstance( col, ImageCollectionManualFITS )
    assert col.base_path == pathlib.Path( base_path )

# TODO : write more tests for manual fits collection when more functionality is implemented
