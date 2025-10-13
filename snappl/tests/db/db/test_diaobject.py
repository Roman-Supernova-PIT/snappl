import uuid
import pytest

from snappl.db.db import DiaObject

from basetest import BaseTestDB


class TestDiaObject( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance ):
        self.cls = DiaObject
        self.safe_to_modify = [ 'name', 'iauname', 'ra', 'dec',
                                'mjd_discovery', 'mjd_max', 'mjd_start', 'mjd_end', 'properties' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'provenance_id' ] )
        self.uniques = []
        self.obj1 = DiaObject( id=uuid.uuid4(),
                               provenance_id=stupid_provenance,
                               name='obj1',
                               ra=128.,
                               dec=42.,
                               mjd_discovery=60015.,
                               mjd_max=60030.,
                               mjd_start=60010.,
                               mjd_end=60060. )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = DiaObject( id=uuid.uuid4(),
                               provenance_id=stupid_provenance,
                               name='obj2',
                               ra=64.,
                               dec=-13.,
                               mjd_discovery=60016.,
                               mjd_max=60031.,
                               mjd_start=60011.,
                               mjd_end=60061. )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'name': 'obj3',
                       'ra': 23.,
                       'dec': -42.,
                       'mjd_discovery': 60017.,
                       'mjd_max': 60032.,
                       'mjd_start': 60012.,
                       'mjd_end': 60062. }
