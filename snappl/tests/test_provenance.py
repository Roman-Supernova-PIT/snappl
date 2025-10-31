import pytest
import uuid

from snappl.config import Config
from snappl.provenance import Provenance
from snappl.db.db import DBCon


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
        # Just save a provenance, make sure it shows up but is not tagged
        gratprov1 = Provenance( process="gratprov", major=1, minor=0 )
        provstodel['provs'].append( gratprov1.id )
        gratprov1.save_to_db( dbclient=dbclient )
        with DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", {'id': gratprov1.id} )
            assert len(rows) == 1
            rows = dbcon.execute( "SELECT * FROM provenance_tag WHERE provenance_id=%(id)s", {'id': gratprov1.id} )
            assert len(rows) == 0

        # Tag an existing provenance
        gratprov1.save_to_db( tag='kaglorky', dbclient=dbclient )
        with DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance_tag WHERE provenance_id=%(id)s", {'id': gratprov1.id} )
            assert len(rows) == 1
            assert rows[0]['tag'] == 'kaglorky'

        # Try the null op (with lots of network and database thought to do nothing)
        gratprov1.save_to_db( tag='kaglorky', dbclient=dbclient )

        # Make a second provenance, make sure we can't save it with the same tag
        gratprov2 = Provenance( process="gratprov", major=2, minor=0 )
        provstodel['provs'].append( gratprov2.id )
        assert gratprov2.id != gratprov1.id
        with pytest.raises( RuntimeError, match="Failed to connect.*Got response 500.*already exists a provenance" ):
            gratprov2.save_to_db( tag='kaglorky', dbclient=dbclient )

        # Make sure we can (succesfully) save a provenance and a tag all in one go
        gratprov3 = Provenance( process="alternate_gratprov", major=1, minor=0 )
        provstodel['provs'].append( gratprov3.id )
        gratprov3.save_to_db( tag='gazorniplotz', dbclient=dbclient )
        gratprov3.save_to_db( tag='kaglorky', dbclient=dbclient )
        with DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance_tag WHERE tag=%(tag)s", {'tag': 'kaglorky'} )
            assert len(rows) == 2
            assert set( [ r['provenance_id'] for r in rows ] ) == { gratprov1.id, gratprov3.id }
            rows = dbcon.execute( "SELECT * FROM provenance_tag WHERE tag=%(tag)s", {'tag': 'gazorniplotz'} )
            assert rows[0]['provenance_id'] == gratprov3.id

        # Fail to get a provenance
        with pytest.raises( ValueError, match=r"^No such provenance" ):
            Provenance.get_by_id( uuid.uuid4(), dbclient=dbclient )

        # Make sure we get None for a nonexistent provenance if that's what we want
        noprov = Provenance.get_by_id( uuid.uuid4(), dbclient=dbclient, return_none_if_not_exists=True )
        assert noprov is None

        # Now test upstreams and all that
        provstodel['provs'].extend( [ wayupstream.id, upstream2.id, upstream1.id, upstream1a.id ] )
        wayupstream.save_to_db( tag='kitten', dbclient=dbclient )
        upstream2.save_to_db( tag='foo', dbclient=dbclient )
        upstream1.save_to_db( tag='foo', dbclient=dbclient )
        upstream1a.save_to_db( tag='bar', dbclient=dbclient )

        # Make sure we can't save something that already exists
        # (I don't know why sometimes I get one error, sometimes the other.)
        # with pytest.raises( RuntimeError, match="Got response 500: Error, provenance.* already exists" ):
        with pytest.raises( RuntimeError, match="Error saving provenance.*; it already exists in the database." ):
            wayupstream.save_to_db( tag='foo', exists=False, dbclient=dbclient )
        # Make sure that didn't tag wayupstream with foo
        provs = Provenance.get_provs_for_tag( 'foo', dbclient=dbclient )
        assert len( provs) == 2
        assert str(wayupstream.id) not in [ p.id for p in provs ]

        # Make sure we can get a process we saved
        prov = Provenance.get( "proc1", 42, 13, exists=True, dbclient=dbclient )
        assert isinstance( prov, Provenance )
        assert prov.id == upstream2.id

        # Make sure we can't get a process we haven't saved if exists=True
        with pytest.raises( RuntimeError, match='^Requested provenance .* does not exist in the database.' ):
            prov = Provenance.get( "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                                   exists=True, dbclient=dbclient )

        # Make sure that if get a process with savetodb=False (the default), it doesn't get saved
        prov = Provenance.get( "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ], dbclient=dbclient )
        assert prov.id == downstream.id
        with pytest.raises( RuntimeError, match='^Requested provenance .* does not exist in the database.' ):
            prov = Provenance.get( "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                                   exists=True, dbclient=dbclient )

        # Make sure that if we say savedb, the provenance is created
        provstodel['provs'].append( downstream.id )
        prov = Provenance.get( "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                               savetodb=True, dbclient=dbclient )
        assert prov.id == downstream.id
        prov = Provenance.get( "proc3", major=23, minor=64738, upstreams=[ upstream1, upstream2 ],
                               exists=True, dbclient=dbclient )
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
        prov = Provenance.get_by_id( downstream.id, dbclient=dbclient )
        check_provs( prov, downstream )

        # Make sure we can get provenances for a tag
        prov = Provenance.get_provs_for_tag( 'foo', 'proc2', dbclient=dbclient )
        check_provs( prov, upstream1 )

        provs = Provenance.get_provs_for_tag( 'foo', dbclient=dbclient )
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
        downstream2.save_to_db( dbclient=dbclient )
        prov = Provenance.get_by_id( downstream2.id, dbclient=dbclient )
        check_provs( prov, downstream2 )
        assert prov.params['answer'] == 42
        assert prov.params['numbers'] == [ 4, 8, 15, 16, 23, 42 ]
        assert prov.params['cat'] == 'Echelle'

        # Check that creating a provenance with params from Config does the right thing.

        prov = Provenance( process="configed", major=1, minor=8, params=Config.get() )
        provstodel['provs'].append( prov.id )
        assert 'system' not in prov.params

        prov = Provenance( process="configed", major=1, minor=8, params=Config.get(), omitkeys=[] )
        provstodel['provs'].append( prov.id )
        assert 'system' in prov.params

        prov = Provenance( process="configed", major=1, minor=8, params=Config.get(),
                           keepkeys=['system.db'], omitkeys=None )
        assert set( prov.params.keys() ) == { 'system' }
        assert set( prov.params['system'].keys() ) == { 'db' }

    finally:
        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM provenance_tag WHERE tag=ANY(%(tag)s)",
                           { 'tag': [ 'kitten', 'foo', 'bar', 'kaglorky', 'gazorniplotz' ] } )
            dbcon.execute( "DELETE FROM provenance_upstream "
                           "WHERE upstream_id=ANY(%(provs)s) OR downstream_id=ANY(%(provs)s)",
                           provstodel )
            dbcon.execute( "DELETE FROM provenance WHERE id=ANY(%(provs)s)", provstodel )
            dbcon.commit()
