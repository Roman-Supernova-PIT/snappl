import datetime
import uuid
import pytest

from snappl.db.db import PasswordLink

from basetest import BaseTestDB


class TestPasswordLink( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self ):
        self.cls = PasswordLink
        self.columns = { 'id', 'userid', 'expires' }
        self.safe_to_modify = [ 'userid', 'expires' ]
        self.uniques = []
        self.obj1 = PasswordLink( id=uuid.uuid4(),
                                  userid=uuid.uuid4(),
                                  expires=datetime.datetime.now( tz=datetime.UTC )
                                 )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = PasswordLink( id=uuid.uuid4(),
                                  userid=uuid.uuid4(),
                                  expires=datetime.datetime.now( tz=datetime.UTC )
                                 )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'userid': uuid.uuid4(),
                       'expires': datetime.datetime.now( tz=datetime.UTC )
                      }
