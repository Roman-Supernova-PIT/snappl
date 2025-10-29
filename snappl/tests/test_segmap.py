from snappl.config import Config
from snappl.segmap import SegmentationMap


# The segmap is saved to the database in the fixture,
#   so this test just makes sure it's there and
#   tries to load it back.
def test_save_and_find_segmap( sim_image_and_segmap, dbclient ):
    image, segmap = sim_image_and_segmap

    base_segmap_path = Config.get().value( 'system.paths.segmaps' )
    assert ( base_segmap_path / segmap.filepath ).is_file()

    newsegmap = SegmentationMap.get_by_id( segmap.id, dbclient=dbclient )

    import pdb; pdb.set_trace()
    pass
