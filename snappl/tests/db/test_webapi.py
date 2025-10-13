import pytest

from snappl.db.db import DBCon
from snappl.provenance import Provenance


def test_create_get_provenance( dbclient ):
    wayupstream = Provenance( process="proc0", major=1, minor=0 )
    upstream2 = Provenance( process="proc1", major=42, minor=13 )
    upstream1 = Provenance( process="proc2", major=64, minor=128, upstreams=[ wayupstream ] )
    upstream1a = Provenance( process="proc2", major=256, minor=128, upstreams=[ wayupstream ] )
    downstream = Provenance( process="proc3", major=23, minor=64738,
                                            upstreams=[ upstream1, upstream2 ] )
    try:
        wayupstreamdict = wayupstream.spec_dict()
        wayupstreamdict.update( { 'id': str(wayupstream.id), 'tag': 'kitten' } )
        upstream2dict = upstream2.spec_dict()
        upstream2dict.update( { 'id': str(upstream2.id), 'tag': 'foo' } )
        upstream1dict = upstream1.spec_dict()
        upstream1dict.update( { 'id': str(upstream1.id), 'tag': 'foo' } )
        upstream1adict = upstream1a.spec_dict()
        upstream1adict.update( { 'id': str(upstream1a.id), 'tag': 'bar' } )
        downstreamdict = downstream.spec_dict()
        downstreamdict.update( { 'id': str(downstream.id), 'tag': 'foo' } )

        for d in [ wayupstreamdict, upstream2dict, upstream1dict, upstream1adict, downstreamdict ]:
            res = dbclient.send( "createprovenance", d )
            assert res[ "status" ] == "ok"

        for newprov in [ dbclient.send( f"getprovenance/{downstream.id}" ),
                         dbclient.send( "getprovenance/foo/proc3" ) ]:
            assert set( u['id'] for u in newprov['upstreams'] ) == { str(upstream1.id), str(upstream2.id) }
            for u in newprov['upstreams']:
                if u['id'] == str( upstream1.id ):
                    assert set( p['id'] for p in u['upstreams'] ) == { str(wayupstream.id) }
            for k, v in newprov.items():
                assert ( k == 'upstreams' ) or ( downstreamdict[k] == v )

        res = dbclient.send( "provenancesfortag/foo" )
        assert isinstance( res, list )
        assert set( r['id'] for r in res ) == set( str(i) for i in [ upstream2.id, upstream1.id, downstream.id ] )

        res = dbclient.send( f"tagprovenance/kaglorky/proc3/{downstream.id}" )
        assert res['status'] == 'ok'
        res = dbclient.send( "provenancesfortag/foo" )
        assert str(downstream.id) in [ r['id'] for r in res ]
        res = dbclient.send( "provenancesfortag/kaglorky" )
        assert set( r['id'] for r in res ) == { str(downstream.id) }

        # Test the null operation tagging where a tag already exists
        res = dbclient.send( f"tagprovenance/kaglorky/proc3/{downstream.id}" )
        res = dbclient.send( "provenancesfortag/kaglorky" )
        assert set( r['id'] for r in res ) == { str(downstream.id) }

        # Can't tag a provenance where the process is already tagged as such
        with pytest.raises( RuntimeError, match=( '^Failed to connect.*already exists a provenance' ), ):
            res = dbclient.send( f"tagprovenance/kaglorky/proc3/{wayupstream.id}", retries=1 )

        # But can replace it if we tell it to
        res = dbclient.send( f"tagprovenance/kaglorky/proc3/{wayupstream.id}/1")
        res = dbclient.send( "provenancesfortag/kaglorky" )
        assert set( r['id'] for r in res ) == { str(wayupstream.id) }

    finally:
        with DBCon() as con:
            con.execute( "DELETE FROM provenance_tag WHERE tag IN ('kitten', 'foo', 'bar', 'kaglorky')" )
            subdict = {'prov': [ wayupstream.id, upstream2.id, upstream1.id, upstream1a.id, downstream.id ]}
            con.execute( "DELETE FROM provenance_upstream "
                         "WHERE downstream_id=ANY(%(prov)s) OR upstream_id=ANY(%(prov)s)",
                         subdict )
            con.execute( "DELETE FROM provenance WHERE id=ANY(%(prov)s)", subdict )

            con.commit()
