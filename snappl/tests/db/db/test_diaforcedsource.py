import uuid
import pytest

from snappl.db.db import DiaForcedSource
from snappl.diaobject import DiaObject
from snappl.imagecollection import ImageCollection

from basetest import BaseTestDB


class TestDiaForcedSource( BaseTestDB ):
    @pytest.fixture
    def basetest_setup( self, stupid_provenance, loaded_ou2024_test_diaobjects, loaded_ou2024_test_l2images,
                        dbclient ):
        dobj = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                       name='20172782', dbclient=dbclient )
        dobj = dobj[0]
        dobjid = dobj.id
        imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images',
                                                dbclient=dbclient )
        images = imcol.find_images( ra=dobj.ra, dec=dobj.dec, order_by='mjd', dbclient=dbclient )
        template_id = images[0].id
        im1id = images[1].id
        im2id = images[2].id
        im3id = images[3].id

        self.cls = DiaForcedSource
        self.safe_to_modify = [ 'flux', 'dflux' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id',
                               'image_id', 'template_id' ] )
        self.uniques = []
        self.obj1 = DiaForcedSource( id=uuid.uuid4(),
                                     provenance_id=stupid_provenance,
                                     diaobject_id=dobjid,
                                     diaobject_position_id=None,
                                     image_id=im1id,
                                     template_id=template_id,
                                     flux=42.,
                                     dflux=3.14159265359
                                    )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = DiaForcedSource( id=uuid.uuid4(),
                                     provenance_id=stupid_provenance,
                                     diaobject_id=dobjid,
                                     diaobject_position_id=None,
                                     image_id=im2id,
                                     template_id=template_id,
                                     flux=64.,
                                     dflux=2.7182818
                                    )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'diaobject_id': dobjid,
                       'diaobject_position_id': None,
                       'image_id': im3id,
                       'template_id': template_id,
                       'flux': 137.,
                       'dflux': 1.414214
                      }

    # These tests from basetest.py fail because the only modifiable columns we have
    #   are floats, and floats will fail == tests
    @pytest.mark.skip( reason="Test will fail because of floating roundoff" )
    def test_get_by_attrs():
        pass

    @pytest.mark.skip( reason="Test will fail because of floating roundoff" )
    def test_bulk_upsert():
        pass
