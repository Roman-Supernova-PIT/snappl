import pytest
from snappl.diaobject import DiaObject, DiaObjectOU2024, DiaObjectManual


def test_no_construct_directly():
    for cls in [ DiaObject, DiaObjectOU2024, DiaObjectManual ]:
        with pytest.raises( RuntimeError, match=( "Don't call a DiaObject or subclass constructor.  "
                                                  "Use DiaObject.find_objects." ) ):
            cls()


def test_find_ou2024_diaobject():
    objs = DiaObject.find_objects( provenance_tag='ou2024', id=20172782 )
    assert isinstance( objs, list )
    assert len(objs) == 1
    obj = objs[0]
    assert obj.id == 20172782
    assert obj.ra == pytest.approx( 7.5510934, abs=1e-5 )
    assert obj.dec == pytest.approx( -44.8071811, abs=1e-5 )
    assert obj.mjd_peak == pytest.approx( 62476.508, abs=1e-3 )
    assert obj.mjd_start == pytest.approx( 62450.0, abs=0.1 )
    assert obj.mjd_end == pytest.approx( 62881.0, abs=0.1 )
    assert obj.mjd_discovery is None
    assert obj.gentype == 10
    assert obj.peak_mag_g == pytest.approx( 23.16, abs=0.01 )

    objs = DiaObject.find_objects( provenance_tag='ou2024', id=1 )
    assert isinstance( objs, list )
    assert len(objs) == 0

    objs = DiaObject.find_objects( provenance_tag='ou2024', ra=7.5510934, dec=-44.8071811, radius=1.0 )
    assert isinstance( objs, list )
    assert len(objs) == 1
    obj = objs[0]
    assert obj.id == 20172782
    assert obj.ra == pytest.approx( 7.5510934, abs=1e-5 )
    assert obj.dec == pytest.approx( -44.8071811, abs=1e-5 )

    objs = DiaObject.find_objects( provenance_tag='ou2024', ra=7.5510934, dec=-44.8071811, radius=60.0 )
    assert len(objs) == 19
    assert any( o.id == 20172782 for o in objs )

    # TODO: test tstart, tend


def test_find_manual_diaobject():
    kwargs = { 'id': 42,
               'ra': 123.456,
               'dec': 78.90
              }
    for omit in [ [ 'id' ], [ 'id', 'ra' ], [ 'id', 'ra', 'dec' ], [ 'ra' ], [ 'ra', 'dec' ], [ 'dec' ] ]:
        tmpkwargs = kwargs.copy()
        for d in omit:
            del tmpkwargs[d]
        with pytest.raises( ValueError, match="finding a manual DiaObject requires all of id, ra, and dec" ):
            objs = DiaObject.find_objects( provenance_tag="manual", **tmpkwargs )

    objs = DiaObject.find_objects( provenance_tag="manual", **kwargs )
    assert len( objs ) == 1
    obj = objs[0]
    assert obj.id == 42
    assert obj.ra == pytest.approx( 123.456, abs=1e-3 )
    assert obj.dec == pytest.approx( 78.90, abs=1e-2 )


def test_get_dbou2024_object( dbclient, loaded_ou2024_test_diaobjects ):
    dobj = DiaObject.get_object( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                 name=20172782, dbclient=dbclient )
    import pdb; pdb.set_trace()
    pass
