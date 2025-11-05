import datetime
import uuid
import pytest

from snappl.db.db import Spectrum1d

from basetest import BaseTestDB


class TestSpectrum1d( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance, stupid_object ):
        now = datetime.datetime.now( tz=datetime.UTC )
        self.cls = Spectrum1d
        self.safe_to_modify = [ 'filepath', 'created_at' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id', 'epoch' ] )
        self.uniques = []
        self.obj1 = Spectrum1d( id=uuid.uuid4(),
                                provenance_id=stupid_provenance,
                                diaobject_id=stupid_object,
                                filepath='/dev/null',
                                epoch=60000000,
                                created_at=now
                               )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = Spectrum1d( id=uuid.uuid4(),
                                provenance_id=stupid_provenance,
                                diaobject_id=stupid_object,
                                filepath='/bin/false',
                                epoch=60001000,
                                created_at=now + datetime.timedelta( days=1 )
                               )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'diaobject_id': stupid_object,
                       'filepath': '/bin/true',
                       'epoch': 60002000,
                       'created_at': now + datetime.timedelta( days=2 )
                      }
