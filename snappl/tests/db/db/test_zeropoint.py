import pytest
import uuid
from snappl.db.db import Zeropoint
from basetest import BaseTestDB


class TestZeropoint( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance, stupid_images ):
        self.cls = Zeropoint
        self.safe_to_modify = [ 'zp', 'dzp' ]
        self.columns = { 'id', 'image_id', 'provenance_id', 'zp', 'dzp' }
        self.uniques = []
        self.obj1 = Zeropoint( id=uuid.uuid4(),
                               image_id=stupid_images[0],
                               provenance_id=stupid_provenance,
                               zp=1.0,
                               dzp=1.0
                              )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = Zeropoint( id=uuid.uuid4(),
                               image_id=stupid_images[1],
                               provenance_id=stupid_provenance,
                               zp=2.0,
                               dzp=2.0
                              )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'image_id': stupid_images[2],
                       'provenance_id': stupid_provenance,
                       'zp': 3.0,
                       'dzp': 3.0 }
