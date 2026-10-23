import pathlib
import pytest
import numbers

import snappl.db.db
from snappl.provenance import Provenance
from snappl.imagecollection import ImageCollection, ImageCollectionManualFITS


def test_get_collection():
    with pytest.raises( ValueError, match=r"Unknown image collection foo \(subset None\)" ):
        ImageCollection.get_collection( "foo" )

# TODO : refactor theses tests so they don't depend on snappl_ou2024



def test_imagecollectionmanualfits_create():
    with pytest.raises( RuntimeError, match="manual_fits collection needs a base path" ):
        col = ImageCollection.get_collection( 'manual_fits' )

    base_path = '/home/photometry_test_data/ou2024/images/simple_model'
    col = ImageCollection.get_collection( 'manual_fits',
                                          base_path='/home/photometry_test_data/ou2024/images/simple_model' )
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
        for prop in ( 'width', 'height', 'observation_id', 'sca', 'ra', 'dec',
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
