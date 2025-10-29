import pytest
import numbers

from snappl.config import Config
from snappl.segmap import SegmentationMap


# The segmap is saved to the database in the fixture,
#   so this test just makes sure it's there and
#   tries to load it back.
def test_save_and_find_segmap( sim_image_and_segmap, dbclient ):
    image, segmap = sim_image_and_segmap

    base_segmap_path = Config.get().value( 'system.paths.segmaps' )
    assert ( base_segmap_path / segmap.filepath ).is_file()

    def check_segmaps( oldsegmap, newsegmap ):
        for prop in ( 'id', 'provenance_id', 'band', 'ra', 'dec',
                      'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                      'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                      'filepath', 'width', 'height', 'format', 'l2image_id' ):
            if isinstance( getattr( oldsegmap, prop ), numbers.Real ):
                assert getattr( oldsegmap, prop ) == pytest.approx( getattr( newsegmap, prop ), rel=1e-7 )
            else:
                assert getattr( oldsegmap, prop ) == getattr( newsegmap, prop )

    newsegmap = SegmentationMap.get_by_id( segmap.id, dbclient=dbclient )
    check_segmaps( segmap, newsegmap )

    # TODO : to really test this, we should have more than one segmap loaded in....

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id, dbclient=dbclient )
    assert len(sms) == 1
    check_segmaps( segmap, sms[0] )

    sms = SegmentationMap.find_segmaps( provenance_tag='stupid_provenance_tag', process='foo', dbclient=dbclient )
    assert len(sms) == 1
    check_segmaps( segmap, sms[0] )

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id, ra=segmap.ra, dec=segmap.dec,
                                        dbclient=dbclient )
    assert len(sms) == 1
    check_segmaps( segmap, sms[0] )

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id,
                                        ra_min=segmap.ra - 20./3600., ra_max=segmap.ra + 20./3600.,
                                        dec_min=segmap.dec - 20./3600., dec_max=segmap.dec + 20./3600.,
                                        dbclient=dbclient)
    assert len(sms) == 1
    check_segmaps( segmap, sms[0] )

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id, ra=segmap.ra+1., dec=segmap.dec+1.,
                                        dbclient=dbclient )
    assert len(sms) == 0

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id, l2image_id=image.id, dbclient=dbclient )
    assert len(sms) == 1
    check_segmaps( segmap, sms[0] )

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id, ra=segmap.ra, dec=segmap.dec, band='R062',
                                        dbclient=dbclient )
    assert len(sms) == 1
    check_segmaps( segmap, sms[0] )

    sms = SegmentationMap.find_segmaps( provenance=segmap.provenance_id, ra=segmap.ra, dec=segmap.dec, band='Y106',
                                        dbclient=dbclient )
    assert len(sms) == 0
