import pytest
import psycopg

from snappl.provenance import Provenance


def test_provenance( dbclient ):
    wayupstream = Provenance( process="proc0", major=1, minor=0 )
    upstream2 = Provenance( process="proc1", major=42, minor=13 )
    upstream1 = Provenance( process="proc2", major=64, minor=128, upstreams=[ wayupstream ] )
    upstream1a = Provenance( process="proc2", major=256, minor=128, upstreams=[ wayupstream ] )
    downstream = Provenance( process="proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ] )

    # Verify recursion
    assert downstream.upstreams[0].id == upstream1.id
    assert downstream.upstreams[0].upstreams[0].id == wayupstream.id

    provstodel = { 'provs': [] }
    try:
        provstodel['provs'] = [ wayupstream.id, upstream2.id, upstream1.id, upstream1a.id ]
        wayupstream.save_to_db( dbclient, tag='kitten' )
        upstream2.save_to_db( dbclient, tag='foo' )
        upstream1.save_to_db( dbclient, tag='foo' )
        upstream1a.save_to_db( dbclient, tag='bar' )

        # Make sure we can't save something that already exists
        # (I don't know why sometimes I get one error, sometimes the other.)
        # with pytest.raises( RuntimeError, match="Got response 500: Error, provenance.* already exists" ):
        with pytest.raises( RuntimeError, match="Error saving provenance.*; it already exists in the database." ):
            wayupstream.save_to_db( dbclient, tag='foo', exists=False )
        # Make sure that didn't tag wayupstream with foo
        provs = Provenance.get_provs_for_tag( dbclient, 'foo' )
        assert len( provs) == 2
        assert str(wayupstream.id) not in [ p.id for p in provs ]

        # Make sure we can get a process we saved
        prov = Provenance.get( dbclient, "proc1", 42, 13, exists=True )
        assert isinstance( prov, Provenance )
        assert prov.id == upstream2.id

        # Make sure we can't get a process we haven't saved if exists=True
        with pytest.raises( RuntimeError, match='^Requested provenance .* does not exist in the database.' ):
            prov = Provenance.get( dbclient, "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                                   exists=True )

        # Make sure that if get a process with savetodb=False (the default), it doesn't get saved
        prov = Provenance.get( dbclient, "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ] )
        assert prov.id == downstream.id
        with pytest.raises( RuntimeError, match='^Requested provenance .* does not exist in the database.' ):
            prov = Provenance.get( dbclient, "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                                   exists=True )

        # Make sure that if we say savedb, the provenance is created
        provstodel['provs'].append( downstream.id )
        prov = Provenance.get( dbclient, "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                               savetodb=True )
        assert prov.id == downstream.id
        prov = Provenance.get( dbclient, "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                               exists=True )
        assert prov.id == downstream.id

        # And, while we're here, let's make sure prov came back with all its toys.
        def check_provs( prov1, prov2 ):
            assert prov1.id == prov2.id
            assert prov1.major == prov2.major
            assert prov1.minor == prov2.minor
            assert prov1.environment == prov2.environment
            assert prov1.env_major == prov2.env_major
            assert prov1.env_minor == prov2.env_minor
            assert prov1.params == prov2.params
            for u1, u2 in zip( prov1.upstreams, prov2.upstreams ):
                check_provs( u1, u2 )

        check_provs( prov, downstream )

        # Make sure we can get a provenance by an id:

        prov = Provenance.get_by_id( dbclient, downstream.id )
        check_provs( prov, downstream )

        # Make sure we can get provenances for a tag
        prov = Provenance.get_provs_for_tag( dbclient, 'foo', 'proc2' )
        check_provs( prov, upstream1 )

        provs = Provenance.get_provs_for_tag( dbclient, 'foo' )
        assert len(provs) == 2
        provs.sort( key=lambda x: x.id )
        origprovs = [ upstream1, upstream2 ]
        origprovs.sort( key=lambda x: x.id )
        check_provs( provs[0], origprovs[0] )
        check_provs( provs[1], origprovs[1] )

        # Check params
        downstream2 = Provenance( process=downstream.process, major=downstream.major, minor=downstream.minor,
                                  upstreams=downstream.upstreams, params={ 'answer': 42,
                                                                           'numbers': [4, 8, 15, 16, 23, 42],
                                                                           'cat': 'Echelle'
                                                                          } )
        assert downstream2.id != downstream.id
        provstodel['provs'].append( downstream2.id )
        downstream2.save_to_db( dbclient )
        prov = Provenance.get_by_id( dbclient, downstream2.id )
        check_provs( prov, downstream2 )
        assert prov.params['answer'] == 42
        assert prov.params['numbers'] == [ 4, 8, 15, 16, 23, 42 ]
        assert prov.params['cat'] == 'Echelle'

    finally:
        with open( '/secrets/pgpasswd' ) as ifp:
            pw = ifp.readline().strip()
        with psycopg.connect( dbname="roman_snpit", user="postgres", password=pw, host="postgres", port=5432 ) as con:
            cursor = con.cursor()
            cursor.execute( "DELETE FROM provenance_tag WHERE tag=ANY(%(tag)s)",
                            { 'tag': [ 'kitten', 'foo', 'bar', 'kaglorky' ] } )
            cursor.execute( "DELETE FROM provenance_upstream "
                            "WHERE upstream_id=ANY(%(provs)s) OR downstream_id=ANY(%(provs)s)",
                            provstodel )
            cursor.execute( "DELETE FROM provenance WHERE id=ANY(%(provs)s)", provstodel )
            con.commit()
