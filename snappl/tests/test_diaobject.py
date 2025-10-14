import pytest
from snappl.diaobject import DiaObject, DiaObjectOU2024, DiaObjectManual
from snappl.provenance import Provenance


def test_no_construct_directly():
    for cls in [ DiaObject, DiaObjectOU2024, DiaObjectManual ]:
        with pytest.raises( RuntimeError, match=( "Don't call a DiaObject or subclass constructor.  "
                                                  "Use DiaObject.find_objects." ) ):
            cls()


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
