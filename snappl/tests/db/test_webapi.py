import pytest
import time
import uuid

from snappl.db.db import DBCon
from snappl.provenance import Provenance
from snappl.image import Image


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
        t0 = time.perf_counter()
        with pytest.raises( RuntimeError, match=( '^Error response from server.*already exists a provenance' ), ):
            res = dbclient.send( f"tagprovenance/kaglorky/proc3/{wayupstream.id}", retries=1 )
        assert time.perf_counter() - t0 < 0.2

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


def test_save_get_find_images( dbclient ):
    improv = None
    images = []
    try:
        improv = Provenance( process="test_load_image", major=1, minor=0 )
        improv.save_to_db()

        curim = Image.find_images( provenance=improv )
        assert len(curim) == 0

        # We want to make a bunch of images so we can both test inserting and getting them, but
        #   also so we can test searching for them.  We'll do this by listing a series of ra/dec,
        #   and then just incrementing mjd, observation_id, etc.

        scalist = [ 1, 2 ]
        bandlist = [ 'r', 'i' ]
        ralist = [ 180.0, 180.1, 180.5, 200.0, 200.5 ]
        declist = [ -10.0, -10.1, -10.0, 32.0, 40.0 ]
        mjd0 = 60000.
        dmjd = 10.
        obs_id0 = 1
        dobs_id = 1

        scadex = 0
        banddex = 0
        mjd = mjd0
        obs_id = obs_id0
        for i, ( ra, dec ) in enumerate( zip( ralist, declist ) ):
            im = Image( id=uuid.uuid4(), filepath=f'image_{i}', provenance_id=improv.id, width=1024, height=1024,
                        observation_id=str(obs_id), sca=scalist[scadex], band=bandlist[banddex],
                        ra=ra, dec=dec,
                        ra_corner_00=ra-0.2, ra_corner_01=ra-0.2, ra_corner_10=ra+0.2, ra_corner_11=ra+0.2,
                        dec_corner_00=dec-0.2, dec_corner_01=dec+0.2, dec_corner_10=dec-0.2, dec_corner_11=dec+0.2,
                        mjd=mjd, exptime=600, format=1 )
            # Have to hack position angle since there will be no wcs to get
            im._position_angle = 0.
            images.append( im )
            im.save_to_db()
            scadex += 1
            if scadex >= len( scalist ):
                scadex = 0
            banddex += 1
            if banddex >= len( bandlist ):
                banddex = 0
            obs_id += dobs_id
            mjd += dmjd


        def compare_images( ims1, ims2 ):
            assert len(ims1) == len(ims2)
            # Don't assume anything about the order in which the images were returned
            im2dexofim1 = []
            for im1dex in range( len(ims1) ):
                dex = [ i for i in range(len(ims2)) if ims2[i].id == ims1[im1dex].id ]
                assert len(dex) == 1
                im2dexofim1.append( dex[0] )
            for im1dex in range( len(ims1) ):
                for eqprop in [ 'id', 'filepath', 'provenance_id', 'width', 'height', '_format',
                                'observation_id', 'sca', 'band' ]:
                    assert getattr( ims1[im1dex], eqprop ) == getattr( ims2[im2dexofim1[im1dex]], eqprop )
                for approxprop in [ 'ra', 'dec', 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                                    'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                                    'mjd', 'exptime' ]:
                    assert ( getattr( ims1[im1dex], approxprop ) ==
                             pytest.approx( getattr( ims2[im2dexofim1[im1dex]], approxprop ), rel=1e-7 ) )

        foundimg = Image.get_image( images[0].id )
        compare_images( images[:1], [foundimg] )

        foundimgs = Image.find_images( provenance=improv )
        compare_images( images, foundimgs )

        # TODO -- write more tests to make sure the right things are found when more criteria are given

        # Now try to bulk insert the images.  Remove them first so we can put them back in.
        with DBCon() as con:
            con.execute( "DELETE FROM l2image WHERE id=ANY(%(ids)s)", { 'ids': [ i.id for i in images ] } )
            con.commit()
        curim = Image.find_images( provenance=improv )
        assert len(curim) == 0

        Image.bulk_save_to_db( images )
        foundimgs = Image.find_images( provenance=improv )
        compare_images( images, foundimgs )

        # Make sure we get an error if we try to save an image that's already in the database
        with pytest.raises( RuntimeError, match="Error response from server: duplicate key value" ):
            images[0].save_to_db()

        # Make sure we get an error if we try to bulk save images already in the database
        # (TODO: another test where one is in, the other isn't; make sure neither get saved.)
        with pytest.raises( RuntimeError, match=( "Error response from server: Got an exception trying "
                                                  "to bulk insert images: duplicate key value" ) ):
            Image.bulk_save_to_db( images )

        # Make sure we get an error if the provenance id is wrong
        with DBCon() as con:
            con.execute( "DELETE FROM l2image WHERE id=ANY(%(ids)s)", { 'ids': [ i.id for i in images ] } )
            con.commit()
        curim = Image.find_images( provenance=improv )
        assert len(curim) == 0

        images[0].provenance_id = uuid.uuid4()
        with pytest.raises( RuntimeError, match=( "Error response from server: insert or update on table .* "
                                                  "violates foreign key constraint" ) ):
            images[0].save_to_db()

        with pytest.raises( RuntimeError, match=( "Error response from server: Got an exception trying "
                                                  "to bulk insert images: insert or update on table .* "
                                                  "violates foreign key constraint" ) ):
            Image.bulk_save_to_db( images )

    finally:
        with DBCon() as con:
            if len(images) > 0:
                con.execute( "DELETE FROM l2image WHERE id=ANY(%(ids)s)", { 'ids': [ i.id for i in images ] } )
            if improv is not None:
                con.execute( "DELETE FROM provenance WHERE id=%(id)s", { 'id': improv.id } )
            con.commit()
