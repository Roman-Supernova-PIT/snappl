# import uuid
# import pytest

# from snappl.db.db import DiaObjectClassification

# from basetest import BaseTestDB


# class TestDiaObjectClassification( BaseTestDB ):

#     @pytest.fixture
#     def basetest_setup( self, stupid_provenance, stupid_object ):
#         self.cls = DiaObjectClassification
#         # Leaving 'probability' out of safe_to_modify becasue the tests will run =, and this is a float
#         self.safe_to_modify = [ 'class_id' ]
#         self.columns = set( self.safe_to_modify )
#         self.columns.update( [ 'id', 'diaobject_id', 'provenance_id', 'probability' ] )
#         self.uniques = []
#         self.obj1 = DiaObjectClassification( id=uuid.uuid4(),
#                                              provenance_id=stupid_provenance,
#                                              diaobject_id=stupid_object,
#                                              class_id=1,
#                                              probability=0.2 )
#         self.dict1 = { k: getattr( self.obj1, k ) for k in self.columns }
#         self.obj2 = DiaObjectClassification( id=uuid.uuid4(),
#                                              provenance_id=stupid_provenance,
#                                              diaobject_id=stupid_object,
#                                              class_id=2,
#                                              probability=0.4 )
#         self.dict2 = { k: getattr( self.obj2, k ) for k in self.columns }
#         self.dict3 = { 'id': uuid.uuid4(),
#                        'provenance_id': stupid_provenance,
#                        'diaobject_id': stupid_object,
#                        'class_id': 3,
#                        'probability': 0.8 }
