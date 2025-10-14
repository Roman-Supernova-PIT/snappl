import uuid
import pytest

from snappl.db.db import DiaObjectPosition

from basetest import BaseTestDB


class TestDiaObjectPosition( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance, stupid_object ):
        self.cls = DiaObjectPosition
        self.safe_to_modify = [ 'ra', 'ra_err', 'dec', 'dec_err', 'ra_dec_covar', 'calculated_at' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'diaobject_id', 'provenance_id' ] )
        self.uniques = []
        self.obj1 = DiaObjectPosition( id=uuid.uuid4(),
                                       provenance_id=stupid_provenance,
                                       diaobject_id=stupid_object,
                                       ra=128.,
                                       dec=42.,
                                       ra_err=0.001,
                                       dec_err=0.001,
                                       ra_dec_covar=1e-6 )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = DiaObjectPosition( id=uuid.uuid4(),
                                       provenance_id=stupid_provenance,
                                       diaobject_id=stupid_object,
                                       ra=64.,
                                       dec=-13.,
                                       ra_err=0.002,
                                       dec_err=0.002,
                                       ra_dec_covar=2e-6 )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'diaobject_id': stupid_object,
                       'ra': 23.,
                       'dec': -42.,
                       'ra_err': 0.003,
                       'dec_err': 0.003 }
