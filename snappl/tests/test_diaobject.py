import pytest
import uuid

from snappl.diaobject import DiaObject
from snappl.provenance import Provenance
from snappl.db.db import DBCon


def test_find_ou2024_diaobject():
    objs = DiaObject.find_objects( collection='ou2024', name=20172782 )
    assert isinstance( objs, list )
    assert len(objs) == 1
    obj = objs[0]
    assert obj.name == '20172782'
    assert obj.ra == pytest.approx( 7.5510934, abs=1e-5 )
    assert obj.dec == pytest.approx( -44.8071811, abs=1e-5 )
    assert obj.mjd_peak == pytest.approx( 62476.508, abs=1e-3 )
    assert obj.mjd_start == pytest.approx( 62450.0, abs=0.1 )
    assert obj.mjd_end == pytest.approx( 62881.0, abs=0.1 )
    assert obj.mjd_discovery is None
    assert obj.properties['gentype'] == 10
    assert obj.properties['peak_mag_g'] == pytest.approx( 23.16, abs=0.01 )

    objs = DiaObject.find_objects( collection='ou2024', name=1 )
    assert isinstance( objs, list )
    assert len(objs) == 0

    objs = DiaObject.find_objects( collection='ou2024', ra=7.5510934, dec=-44.8071811, radius=1.0 )
    assert isinstance( objs, list )
    assert len(objs) == 1
    obj = objs[0]
    assert obj.name == '20172782'
    assert obj.ra == pytest.approx( 7.5510934, abs=1e-5 )
    assert obj.dec == pytest.approx( -44.8071811, abs=1e-5 )

    objs = DiaObject.find_objects( collection='ou2024', ra=7.5510934, dec=-44.8071811, radius=60.0 )
    assert len(objs) == 19
    assert any( o.name == '20172782' for o in objs )

    # TODO: test tstart, tend


def test_find_manual_diaobject():
    kwargs = { 'name': 42,
               'ra': 123.456,
               'dec': 78.90
              }
    for omit in [ [ 'name' ], [ 'name', 'ra' ], [ 'name', 'ra', 'dec' ], [ 'ra' ], [ 'ra', 'dec' ], [ 'dec' ] ]:
        tmpkwargs = kwargs.copy()
        for d in omit:
            del tmpkwargs[d]
        with pytest.raises( ValueError, match="finding a manual DiaObject requires all of name, ra, and dec" ):
            objs = DiaObject.find_objects( collection="manual", **tmpkwargs )

    objs = DiaObject.find_objects( collection="manual", **kwargs )
    assert len( objs ) == 1
    obj = objs[0]
    assert obj.name == '42'
    assert obj.ra == pytest.approx( 123.456, abs=1e-3 )
    assert obj.dec == pytest.approx( 78.90, abs=1e-2 )


def _check_objects( obj1, obj2 ):
    for prop in [ 'id', 'provenance_id', 'name', 'iauname', 'ra', 'dec',
                'mjd_discovery', 'mjd_peak', 'mjd_start', 'mjd_end',
                'properties' ]:
        assert getattr( obj1, prop ) == getattr( obj2, prop )


def test_get_dbou2024_object( dbclient, loaded_ou2024_test_diaobjects ):
    # Using the default collection of 'snpitdb' here

    # Get object with provenance tag, process, and name
    dobj = DiaObject.get_object( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                 name=20172782, dbclient=dbclient )
    assert dobj.name == '20172782'
    assert dobj.iauname is None
    assert dobj.ra == pytest.approx( 7.5510934, abs=1e-5 )
    assert dobj.dec == pytest.approx( -44.8071811, abs=1e-5 )

    # Get object with id
    dobj2 = DiaObject.get_object( diaobject_id=dobj.id, provenance_tag='dbou2024_test',
                                  process='import_ou2024_diaobjects', dbclient=dbclient )
    _check_objects( dobj, dobj2 )

    # Get object with id and provenance
    prov = Provenance.get_provs_for_tag( 'dbou2024_test', 'import_ou2024_diaobjects', dbclient=dbclient )
    dobj2 = DiaObject.get_object( diaobject_id=dobj.id, provenance=prov, dbclient=dbclient )
    _check_objects( dobj, dobj2 )

    # Get object with id and provenance_id
    dobj2 = DiaObject.get_object( diaobject_id=dobj.id, provenance=prov.id, dbclient=dbclient )
    _check_objects( dobj, dobj2 )

    # TODO : check failure modes


def test_find_dbou2024_object( dbclient, loaded_ou2024_test_diaobjects ):
    dobj = DiaObject.get_object( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                 name=20172782, dbclient=dbclient )
    # Find objects near ra, dec
    dobjs = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                    ra=dobj.ra, dec=dobj.dec, dbclient=dbclient )
    assert isinstance( dobjs, list )
    assert len(dobjs) == 1
    _check_objects( dobj, dobjs[0] )

    dobjs = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects', name=1,
                                    dbclient=dbclient )
    assert isinstance( dobjs, list )
    assert len(dobjs) == 0

    dobjs = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                    ra=7.5510934, dec=-44.8071811, radius=1.0, dbclient=dbclient )
    assert isinstance( dobjs, list )
    assert len(dobjs) == 1
    assert dobjs[0].name == '20172782'

    dobjs = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                    ra=7.5510934, dec=-44.8071811, radius=60.0, dbclient=dbclient )
    assert len(dobjs) == 19

    # TODO : test start, end, discovery, peak


def test_save_diaobject( test_object_provenance, dbclient ):
    objids = [ uuid.uuid4() ]
    try:
        kwargs = { 'id': objids[0],
                   'provenance_id': test_object_provenance.id,
                   'name': "Fred",
                   'ra': 128.,
                   'dec': -13.,
                   'mjd_discovery': 60000.,
                   'properties': { 'answer': 42 }
                  }
        diaobj = DiaObject( **kwargs )
        res = diaobj.save_object( dbclient=dbclient )
        assert res['id'] == str( diaobj.id )
        assert res['provenance_id'] == str( diaobj.provenance_id )
        assert res['name'] == diaobj.name
        assert res['ra'] == pytest.approx( diaobj.ra, abs=1e-6 )
        assert res['dec'] == pytest.approx( diaobj.dec, abs=1e-6 )
        assert res['mjd_discovery'] == pytest.approx( diaobj.mjd_discovery, abs=1e-5 )
        assert res['properties'] == { "answer": 42 }
        assert all( res[i] is None for i in [ 'iauname', 'mjd_peak', 'mjd_start', 'mjd_end' ] )

        foundobj = DiaObject.get_object( provenance=test_object_provenance, diaobject_id=diaobj.id, dbclient=dbclient )
        assert all( getattr(foundobj, prop) == getattr(diaobj, prop) for prop in kwargs.keys() )

        foundobj = DiaObject.get_object( provenance=test_object_provenance, name=diaobj.name, dbclient=dbclient )
        assert all( getattr(foundobj, prop) == getattr(diaobj, prop) for prop in kwargs.keys() )

        # Make sure we can't save the same object twice
        with pytest.raises( RuntimeError, match=( f"Failed to connect.*Got response 500.*diaobject "
                                                  f"{diaobj.id} already exists!" ) ):
            diaobj.name = 'George'
            diaobj.save_object( dbclient=dbclient )

        # Make sure we can't save the same name/provenance twice
        with pytest.raises( RuntimeError, match="Failed to connect.*Got response 500.*diaobject with name Fred" ):
            objids.append( uuid.uuid4() )
            diaobj.id = objids[-1]
            diaobj.name = 'Fred'
            diaobj.save_object( dbclient=dbclient )

        # Make sure it yells at us if things are missing
        for omit in [ 'provenance_id', 'name', 'ra', 'dec', 'mjd_discovery' ]:
            objids.append( uuid.uuid4() )
            tmp = kwargs.copy()
            tmp['id'] = objids[-1]
            tmp[omit] = None
            diaobj = DiaObject( **tmp )
            with pytest.raises( RuntimeError, match="Failed to connect.*Got response 500: Missing required keys" ):
                diaobj.save_object( dbclient=dbclient )

            tmp = kwargs.copy()
            objids.append( uuid.uuid4() )
            tmp['id'] = objids[-1]
            del tmp[omit]
            with pytest.raises( RuntimeError, match="Failed to connect.*Got response 500: Missing required keys" ):
                diaobj.save_object( dbclient=dbclient )

    finally:
        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM diaobject WHERE id=ANY(%(ids)s)", { 'ids': objids } )
            dbcon.commit()
