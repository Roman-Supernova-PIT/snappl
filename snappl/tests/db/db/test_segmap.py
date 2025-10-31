import uuid
import pytest

from snappl.db.db import SegMap

from basetest import BaseTestDB


class TestSegMap( BaseTestDB ):

    @pytest.fixture
    def basetest_setup( self, stupid_provenance ):
        self.cls = SegMap
        self.safe_to_modify = [ 'band', 'ra', 'dec',
                                'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                                'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                                'filepath', 'width', 'height', 'position_angle', 'format' ]
        self.columns = set( self.safe_to_modify )
        self.columns.update( [ 'id', 'provenance_id', 'l2image_id' ] )
        self.uniques = []
        self.obj1 = SegMap( id=uuid.uuid4(),
                            provenance_id=stupid_provenance,
                            band='a',
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
                            filepath='segmap1',
                            width=1024,
                            height=1024,
                            position_angle=12.96,
                            format=1,
                            l2image_id=None )
        self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
        self.obj2 = SegMap( id=uuid.uuid4(),
                            provenance_id=stupid_provenance,
                            band='b',
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
                            filepath='segmap2',
                            width=1025,
                            height=1025,
                            position_angle=2.37,
                            format=2,
                            l2image_id=None )
        self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
        self.dict3 = { 'id': uuid.uuid4(),
                       'provenance_id': stupid_provenance,
                       'band': 'c',
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
                       'filepath': 'segmap3',
                       'width': 1026,
                       'height': 1026,
                       'position_angle': 0.212,
                       'format': 3,
                       'l2image_id': None }
