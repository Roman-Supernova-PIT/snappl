import uuid
import pytest

from snappl.db.db import L2Image

from basetest import BaseTestDB


class TestL2Image( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance ):
        self.cls = L2Image
        self.safe_to_modify = [ 'pointing', 'sca', 'filter', 'ra', 'dec',
                                'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                                'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                                'filepath', 'extension', 'width', 'height', 'format', 'mjd',
                                'exptime', 'properties' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'provenance_id' ] )
        self.uniques = []
        self.obj1 = L2Image( id=uuid.uuid4(),
                             provenance_id=stupid_provenance,
                             pointing=1,
                             sca=1,
                             filter='a',
                             ra=1.,
                             dec=1.,
                             ra_corner_00=1.,
                             ra_corner_01=1.,
                             ra_corner_10=1.,
                             ra_corner_11=1.,
                             dec_corner_00=1.,
                             dec_corner_01=1.,
                             dec_corner_10=1.,
                             dec_corner_11=1.,
                             filepath='l2image1',
                             width=1024,
                             height=1024,
                             format=1,
                             mjd=60000.,
                             exptime=60. )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = L2Image( id=uuid.uuid4(),
                             provenance_id=stupid_provenance,
                             pointing=2,
                             sca=2,
                             filter='b',
                             ra=2.,
                             dec=2.,
                             ra_corner_00=2.,
                             ra_corner_01=2.,
                             ra_corner_10=2.,
                             ra_corner_11=2.,
                             dec_corner_00=2.,
                             dec_corner_01=2.,
                             dec_corner_10=2.,
                             dec_corner_11=2.,
                             filepath='l2image2',
                             width=1025,
                             height=1025,
                             format=2,
                             mjd=60001.,
                             exptime=61. )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'pointing': 3,
                       'sca': 3,
                       'filter': 'c',
                       'ra': 3.,
                       'dec': 3.,
                       'ra_corner_00': 3.,
                       'ra_corner_01': 3.,
                       'ra_corner_10': 3.,
                       'ra_corner_11': 3.,
                       'dec_corner_00': 3.,
                       'dec_corner_01': 3.,
                       'dec_corner_10': 3.,
                       'dec_corner_11': 3.,
                       'filepath': 'l2image3',
                       'width': 1026,
                       'height': 1026,
                       'format': 3,
                       'mjd': 60002.,
                       'exptime': 62. }
