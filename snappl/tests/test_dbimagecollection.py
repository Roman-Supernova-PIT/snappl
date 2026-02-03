import pytest

from snappl.imagecollection import ImageCollection
from snappl.image import OpenUniverse2024FITSImage
from snappl.utils import env_as_bool


# This test is kinda slow, so give users the option to skip it
@pytest.mark.skipif( env_as_bool('SKIP_SLOW_TESTS'), reason='SKIP_SLOW_TESTS is set' )
def test_load_ou2024_l2images_1proc( loaded_ou2024_test_l2images_1proc, dbclient ):
    imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images_1proc',
                                            dbclient=dbclient )
    allimages = imcol.find_images( dbclient=dbclient )
    assert len(allimages) == 8
    assert all( isinstance(i, OpenUniverse2024FITSImage) for i in allimages )


# This also tests load_ou2024_l2images with nprocs=4
def test_ou2024_find_images( loaded_ou2024_test_l2images, dbclient ):
    imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images',
                                            dbclient=dbclient )
    allimages = imcol.find_images( dbclient=dbclient )
    assert len(allimages) == 8
    assert all( isinstance(i, OpenUniverse2024FITSImage) for i in allimages )

    # Test searching by filepath
    images = imcol.find_images( filepath=str( allimages[0].filepath ), dbclient=dbclient )
    assert len(images) == 1
    assert images[0].id == allimages[0].id

    # Test searching by observation_id
    images = imcol.find_images( observation_id=allimages[0].observation_id, dbclient=dbclient )
    assert len(images) == 1
    assert images[0].id == allimages[0].id

    # Test searching by SCA
    images = imcol.find_images( sca=15, dbclient=dbclient )
    assert len(images) == 3
    assert set( i.id for i in images ) == set( i.id for i in allimages if i.sca==15 )

    # Test searching by observation_id and SCA
    images = imcol.find_images( sca=allimages[0].sca, observation_id=allimages[0].observation_id, dbclient=dbclient )
    assert len(images) == 1
    assert images[0].id == allimages[0].id

    # Test searching by observation_id, SCA, and band
    images = imcol.find_images( sca=allimages[0].sca, observation_id=allimages[0].observation_id, band=allimages[0].band,
                                dbclient=dbclient )
    assert len(images) == 1
    assert images[0].id == allimages[0].id

    images = imcol.find_images( sca=allimages[0].sca, observation_id=allimages[0].observation_id, band='FOO',
                                dbclient=dbclient )
    assert len(images) == 0

    # Find all images that diaobject 20172782... which should be all of them
    images = imcol.find_images( ra=7.5510934, dec=-44.8071811, dbclient=dbclient )
    assert len(images) == 8

    # Find all images that overlap a point where there are 4
    # (Chosen visually with ds9)
    images = imcol.find_images( ra=7.5417396, dec=-44.87838, dbclient=dbclient )
    assert len(images) == 4

    # Make sure an outside point gets none of them
    images = imcol.find_images( ra=7.65477, dec=-44.90313, dbclient=dbclient )
    assert len(images) == 0

    # TODO MORE TESTS ... mjd, exptime


def test_ou2024_get_image( loaded_ou2024_test_l2images, dbclient ):
    imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images',
                                            dbclient=dbclient )
    allimages = imcol.find_images( dbclient=dbclient )
    assert len(allimages) == 8
    assert all( isinstance(i, OpenUniverse2024FITSImage) for i in allimages )

    img = imcol.get_image( image_id=allimages[0].id, dbclient=dbclient )
    assert img.id == allimages[0].id

    img = imcol.get_image( path=allimages[0].filepath, dbclient=dbclient )
    assert img.id == allimages[0].id

    img = imcol.get_image( observation_id=allimages[0].observation_id, sca=allimages[0].sca, band=allimages[0].band,
                           dbclient=dbclient )
    assert img.id == allimages[0].id

    assert img.data.shape == (4088, 4088)
