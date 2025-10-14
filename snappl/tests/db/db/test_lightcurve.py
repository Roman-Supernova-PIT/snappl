import datetime
import uuid
import pytest

from snappl.db.db import Lightcurve

from basetest import BaseTestDB


class TestLightcurve( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance, stupid_object ):
        now = datetime.datetime.now( tz=datetime.UTC )
        self.cls = Lightcurve
        self.safe_to_modify = [ 'filter', 'filepath', 'created_at' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'provenance_id', 'diaobject_id' ] )
        self.uniques = []
        self.obj1 = Lightcurve( id=uuid.uuid4(),
                                provenance_id=stupid_provenance,
                                diaobject_id=stupid_object,
                                filter='a',
                                filepath='/dev/null',
                                created_at=now
                                      )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = Lightcurve( id=uuid.uuid4(),
                                provenance_id=stupid_provenance,
                                diaobject_id=stupid_object,
                                filter='b',
                                filepath='/bin/false',
                                created_at=now + datetime.timedelta( days=1 )
                               )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'diaobject_id': stupid_object,
                       'filter': 'c',
                       'filepath': '/bin/true',
                       'created_at': now + datetime.timedelta( days=2 )
                      }
