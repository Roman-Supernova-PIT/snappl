import pytest
import uuid
import time

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
                'ndetected', 'properties' ]:
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

    dobjs = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                    ra=7.5510934, dec=-44.8071811, radius=60.0,
                                    order_by='ra', limit=10, dbclient=dbclient )
    assert len(dobjs) == 10
    ras = [ o.ra for o in dobjs ]
    sortedras = ras.copy()
    sortedras.sort()
    assert ras == sortedras
    assert dobjs[0].ra == pytest.approx( 7.529642270069371, abs=1e-6 )
    assert dobjs[9].ra == pytest.approx( 7.5552501571352515, abs=1e-6 )

    dobjs2 = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                     ra=7.5510934, dec=-44.8071811, radius=60.0,
                                     order_by='ra', offset=10, limit=5, dbclient=dbclient )
    assert len(dobjs2) == 5
    assert set( d.id for d in dobjs ).intersection( set( d.id for d in dobjs2 ) ) == set()
    ras = [ o.ra for o in dobjs2 ]
    sortedras = ras.copy()
    sortedras.sort()
    assert ras == sortedras
    assert dobjs2[0].ra == pytest.approx( 7.556117018768477,abs=1e-6 )
    assert dobjs2[4].ra == pytest.approx( 7.5643485108524455, abs=1e-6 )

    # TODO : test start, end, discovery, peak


def test_get_dbou2024_object_position( dbclient, loaded_ou2024_test_diaobjects ):
    dobj = DiaObject.get_object( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                 name=20172782, dbclient=dbclient )
    pos = dobj.get_position( provenance_tag='dbou2024_test', process='ou2024_diaobjects_truth_copy', dbclient=dbclient )
    assert pos['diaobject_id'] == str( dobj.id )
    # RA and Dec should be the same because both the object and the position were loaded from the truth tables
    assert pos['ra'] == pytest.approx( dobj.ra, abs=1e-6 )
    assert pos['dec'] == pytest.approx( dobj.dec, abs=1e-6 )

    dobjs = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                    ra=7.5510934, dec=-44.8071811, radius=60.0,
                                    order_by='ra', limit=5, dbclient=dbclient )
    poses = DiaObject.get_diaobject_positions( dobjs, provenance_tag='dbou2024_test',
                                               process='ou2024_diaobjects_truth_copy', dbclient=dbclient )
    assert len(poses) == 5
    assert set( poses.keys() ) == set( str(d.id) for d in dobjs )
    for d in dobjs:
        # RA and Dec should be the same because both the object and the position were loaded from the truth tables
        assert poses[str(d.id)]['ra'] == pytest.approx( d.ra, abs=1e-6 )
        assert poses[str(d.id)]['dec'] == pytest.approx( d.dec, abs=1e-6 )


def test_save_dbou2024_object_position( dbclient, loaded_ou2024_test_diaobjects ):
    prov = None
    try:
        dobj = DiaObject.get_object( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                     name=20172782, dbclient=dbclient )
        objprov = Provenance.get_by_id( dobj.provenance_id, dbclient=dbclient )
        prov = Provenance( 'test_update_position', 0, 1, upstreams=[objprov] )
        prov.save_to_db( tag='dbou2024_test', dbclient=dbclient )

        dobj.save_updated_position( prov, ra=dobj.ra+0.01, dec=dobj.dec+0.01, ra_err=0.01, dec_err=0.01,
                                    ra_dec_covar=0.0001, dbclient=dbclient )

        pos = dobj.get_position( position_provenance=prov, dbclient=dbclient )
        assert pos['ra'] == pytest.approx( dobj.ra + 0.01, abs=1e-6 )
        assert pos['dec'] == pytest.approx( dobj.dec + 0.01, abs=1e-6 )
        assert pos['ra_err'] == pytest.approx( 0.01, abs=1e-6 )
        assert pos['dec_err'] == pytest.approx( 0.01, abs=1e-6 )
        assert pos['ra_dec_covar'] == pytest.approx( 0.0001, abs=1e-10 )

    finally:
        if prov is not None:
            with DBCon() as dbcon:
                dbcon.execute( "DELETE FROM diaobject_position WHERE provenance_id=%(id)s", {'id': prov.id} )
                dbcon.execute( "DELETE FROM provenance_tag WHERE tag=%(tag)s AND process=%(proc)s",
                               {'tag': 'dbou2024_test', 'proc': 'test_update_position'} )
                dbcon.execute( "DELETE FROM provenance WHERE id=%(id)s", {'id': prov.id} )
                dbcon.commit()


def test_save_diaobject( test_object_provenance, dbclient ):
    objids = [ uuid.uuid4(), uuid.uuid4(), uuid.uuid4() ]
    try:
        kwargs = { 'id': objids[0],
                   'provenance_id': test_object_provenance.id,
                   'name': "Fred",
                   'ra': 128.,
                   'dec': -13.,
                   'mjd_discovery': 60000.,
                   'properties': { 'answer': 42 }
                  }
        kwargs2 = { 'id': objids[1],
                    'provenance_id': test_object_provenance.id,
                    'name': "George",
                    'ra': 128.0001,
                    'dec': -13.0001,
                    'mjd_discovery': 60010.,
                    'properties': { 'bad_luck': 13 }
                   }
        kwargs3 = { 'id': objids[2],
                    'provenance_id': test_object_provenance.id,
                    'name': "Ron",
                    'ra': 128.0003,
                    'dec': -13.0003,
                    'mjd_discovery': 60020.,
                    'properties': { 'reboot': 64738 }
                   }

        diaobj = DiaObject( **kwargs )
        res = diaobj.save_object( dbclient=dbclient )
        assert res['id'] == str( diaobj.id )
        assert res['provenance_id'] == str( diaobj.provenance_id )
        assert res['name'] == diaobj.name
        assert res['ra'] == pytest.approx( diaobj.ra, abs=1e-6 )
        assert res['dec'] == pytest.approx( diaobj.dec, abs=1e-6 )
        assert res['mjd_discovery'] == pytest.approx( diaobj.mjd_discovery, abs=1e-5 )
        assert res['ndetected'] == 1
        assert res['properties'] == { "answer": 42 }
        assert all( res[i] is None for i in [ 'iauname', 'mjd_peak', 'mjd_start', 'mjd_end' ] )

        foundobj = DiaObject.get_object( provenance=test_object_provenance, diaobject_id=diaobj.id, dbclient=dbclient )
        assert all( getattr(foundobj, prop) == getattr(diaobj, prop) for prop in kwargs.keys() )

        foundobj = DiaObject.get_object( provenance=test_object_provenance, name=diaobj.name, dbclient=dbclient )
        assert all( getattr(foundobj, prop) == getattr(diaobj, prop) for prop in kwargs.keys() )

        # Test association
        diaobj2 = DiaObject( **kwargs2 )
        retval = diaobj2.save_object( dbclient=dbclient )
        assert retval['id'] == str( diaobj.id )
        assert retval['id'] != str( diaobj2.id )
        assert retval['ra'] == pytest.approx( diaobj.ra, abs=1e-6 )
        assert retval['dec'] == pytest.approx( diaobj.dec, abs=1e-6 )
        assert not retval['ra'] == pytest.approx( diaobj2.ra, abs=1e-6 )
        assert not retval['dec'] == pytest.approx( diaobj2.dec, abs=1e-6 )
        assert retval['properties'] == diaobj.properties
        assert retval['properties'] != diaobj2.properties
        assert retval['ndetected'] == 2
        # Make sure that an object of the given id wasn't saved
        t0 = time.perf_counter()
        with pytest.raises( RuntimeError, match="Error response from server: Object not found" ):
            DiaObject.get_object( diaobject_id=diaobj2.id, dbclient=dbclient )
        assert time.perf_counter() - t0 < 0.2
        # Make sure if we get the object back it has ndetected=2
        foundobj = DiaObject.get_object( provenance=test_object_provenance, diaobject_id=diaobj.id, dbclient=dbclient )
        assert foundobj.ndetected == 2

        # Make sure we can't save the same name/provenance twice
        t0 = time.perf_counter()
        with pytest.raises( RuntimeError, match="Error response from server:.*diaobject with name Fred" ):
            diaobj3 = DiaObject( **kwargs3 )
            diaobj3.name = diaobj.name
            diaobj3.save_object( dbclient=dbclient )
        assert time.perf_counter() - t0 < 0.2

        # Test lack of association
        diaobj3 = DiaObject( **kwargs3 )
        retval = diaobj3.save_object( dbclient=dbclient )
        assert retval['id'] == str( diaobj3.id )
        assert retval['name'] == diaobj3.name

        # Make sure we can save objects with just the minimal data
        diaobj = DiaObject( ra=1., dec=2., provenance_id=test_object_provenance.id, mjd_discovery=60000. )
        objids.append( diaobj.id )
        diaobj.save_object()

        # Make sure it yells at us if things are missing
        for omit in [ 'provenance_id', 'ra', 'dec', 'mjd_discovery' ]:
            objids.append( uuid.uuid4() )
            tmp = kwargs.copy()
            tmp['id'] = objids[-1]
            tmp[omit] = None
            diaobj = DiaObject( **tmp )
            t0 = time.perf_counter()
            with pytest.raises( RuntimeError, match="Error response from server: Missing required keys" ):
                diaobj.save_object( dbclient=dbclient )
            assert time.perf_counter() - t0 < 0.2

            tmp = kwargs.copy()
            objids.append( uuid.uuid4() )
            tmp['id'] = objids[-1]
            del tmp[omit]
            t0 = time.perf_counter()
            with pytest.raises( RuntimeError, match="Error response from server: Missing required keys" ):
                diaobj.save_object( dbclient=dbclient )
            assert time.perf_counter() - t0 < 0.2

    finally:
        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM diaobject WHERE id=ANY(%(ids)s)", { 'ids': objids } )
            dbcon.commit()
