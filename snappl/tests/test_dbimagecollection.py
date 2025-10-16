import pytest
import pathlib

from snappl.imagecollection import ImageCollection
from snappl.image import OpenUniverse2024FITSImage
from snappl.config import Config
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
    base_path = pathlib.Path( Config.get().value( 'system.ou24.images' ) )
    images = imcol.find_images( filepath=str( allimages[0].path.relative_to( base_path ) ),
                                dbclient=dbclient )
    assert len(images) == 1
    assert images[0].id == allimages[0].id

    # TODO MORE TESTS
