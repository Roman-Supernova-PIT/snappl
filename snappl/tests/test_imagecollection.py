import pathlib
import pytest
import numbers
import numpy as np

import snappl.db.db
import snappl.image
from snappl.provenance import Provenance
from snappl.imagecollection import ImageCollection, ImageCollectionOU2024, ImageCollectionManualFITS
from snappl.config import Config


def test_get_collection():
    with pytest.raises( ValueError, match=r"Unknown image collection foo \(subset None\)" ):
        ImageCollection.get_collection( "foo" )


def test_imagecollectionou2024_base_path():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )
    assert isinstance( col, ImageCollectionOU2024 )
    assert col.base_path == pathlib.Path( cfg.value('system.ou24.images') )


def test_imagecollectionou2024_get_image_path():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )

    path = col.get_image_path( 13205, 'Y106', 1 )
    assert path == ( pathlib.Path( cfg.value('system.ou24.images') )
                     / 'Y106/13205/Roman_TDS_simple_model_Y106_13205_1.fits.gz' )


def test_imagecollectionou2024_get_image():
    cfg = Config.get()
    col = ImageCollection.get_collection( "ou2024" )

    expectedpath = ( pathlib.Path( cfg.value('system.ou24.images') )
                     / 'Y106/13205/Roman_TDS_simple_model_Y106_13205_1.fits.gz' )
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
    col = ImageCollection.get_collection( "ou2024" )

    # TODO, more tests, this is just a quick and basic
    imgs = col.find_images( band='Y106', ra=7.5510934, dec=-44.8071811 )
    assert len(imgs) == 135


def test_imagecollectionmanualfits_create():
    with pytest.raises( RuntimeError, match="manual_fits collection needs a base path" ):
        col = ImageCollection.get_collection( 'manual_fits' )

    base_path = '/photometry_Test_data/ou2024/images/simple_model'
    col = ImageCollection.get_collection( 'manual_fits', base_path='/photometry_Test_data/ou2024/images/simple_model' )
    assert isinstance( col, ImageCollectionManualFITS )
    assert col.base_path == pathlib.Path( base_path )

# TODO : write more tests for manual fits collection when more functionality is implemented


def test_imagecollectiondb( loaded_ou2024_test_l2images, dbclient ):
    prov = Provenance.get_provs_for_tag( 'dbou2024_test', process='import_ou2024_l2images', dbclient=dbclient )

    with snappl.db.db.DBCon( dictcursor=True ) as dbcon:
        images = dbcon.execute( "SELECT * FROM l2image WHERE provenance_id=%(provid)s", {'provid': prov.id} )

    imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images',
                                            dbclient=dbclient )

    def check_image( image, imagedict ):
        # Make sure the properties got loaded from the database
        # (This is why we are checking the underscore properties,
        # so the lazy-loading won't get hit.)
        # (sky_level and zeropoint aren't in the database, so don't check those.)
        nonlocal imcol
        assert image.id == imagedict['id']
        assert image.path == imcol.base_path / imagedict['filepath']
        for prop in ( 'width', 'height', 'pointing', 'sca', 'ra', 'dec',
                      'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                      'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                      'band', 'mjd', 'position_angle', 'exptime' ):
            if isinstance( imagedict[prop], numbers.Real ) and not isinstance( imagedict[prop], numbers.Integral ):
                assert getattr( image, f'_{prop}' ) == pytest.approx( imagedict[prop], rel=1e-7 )
                assert getattr( image, prop ) == pytest.approx( imagedict[prop], rel=1e-7 )
            else:
                assert getattr( image, f'_{prop}' ) == imagedict[prop]
                assert getattr( image, prop ) == imagedict[prop]

    im = imcol.get_image( images[0]['id'], dbclient=dbclient )
    check_image( im, images[0] )

    ims = imcol.find_images( dbclient=dbclient )
    assert len(ims) == len(images)
    for im in ims:
        image = None
        for image in images:
            if image['id'] == im.id:
                break
        assert image is not None
        check_image( im, image )
