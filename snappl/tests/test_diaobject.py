import pytest

from snappl.diaobject import DiaObject


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
