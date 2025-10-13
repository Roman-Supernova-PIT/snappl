import uuid
import pytest

from snappl.db.db import Provenance

from basetest import BaseTestDB


class TestProvenance( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self ):
        self.cls = Provenance
        self.columns = { 'id',
                         'environment',
                         'env_major',
                         'env_minor',
                         'process',
                         'major',
                         'minor',
                         'params' }
        self.safe_to_modify = [ 'environment', 'env_major', 'env_minor','process', 'major', 'minor', 'params' ]
        self.uniques = []
        self.obj1 = Provenance( id=uuid.uuid4(),
                                environment=0,
                                env_major=1,
                                env_minor=0,
                                process='proc1',
                                major=1,
                                minor=1,
                               )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = Provenance( id=uuid.uuid4(),
                                environment=1,
                                env_major=2,
                                env_minor=2,
                                process='proc2',
                                major=2,
                                minor=3,
                               )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'environment': 2,
                       'env_major': 3,
                       'env_minor': 3,
                       'process': 'proc3',
                       'major': 3,
                       'minor': 4 }
