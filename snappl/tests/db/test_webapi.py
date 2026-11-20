import pytest
import time
import uuid

import numpy as np
from psycopg import sql

from snappl.db.db import DBCon
from snappl.provenance import Provenance
from snappl.imagecollection import ImageCollection
from snappl.image import Image
from snappl.diaobject import DiaObject
from snappl.utils import asUUID


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
            assert res[ "provenance_id" ] == d[ "id" ]

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


# TODO : update this test to not use ou2024 images.
# (But, for now, this is to just get this done.)
def test_diaforcedsource( loaded_ou2024_test_l2images, loaded_ou2024_test_diaobjects, dbclient ):
    prov = None
    photids = []
    try:
        dobj = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                       name='20172782', dbclient=dbclient )
        dobj = dobj[0]
        imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images',
                                                dbclient=dbclient )
        images = imcol.find_images( ra=dobj.ra, dec=dobj.dec, order_by='mjd', dbclient=dbclient )

        template_id = images[0].id
        imids = [ i.id for i in images[1:] ]

        rng = np.random.default_rng()
        fluxen = rng.uniform( low=10., high=10000., size=(len(imids),) )
        dfluxen = np.sqrt( 20.**2 + fluxen )

        prov = Provenance( process="fake_lightcurve", major=0, minor=1, params={"fake": True},
                           upstreams=[ Provenance.get_by_id( images[0].provenance_id ),
                                       Provenance.get_by_id( dobj.provenance_id ) ] )
        prov.save_to_db( tag='test_diaforcedsource' )

        # TODO : test with diaobject_position
        for imid, flux, dflux in zip( imids, fluxen, dfluxen ):
            res = dbclient.send( "savediaforcedsource",
                                 { 'provenance_id': str(prov.id),
                                   'diaobject_id': str(dobj.id),
                                   'diaobject_position_id': None,
                                   'image_id': str(imid),
                                   'template_id': str(template_id),
                                   'flux': flux,
                                   'dflux': dflux } )
            photids.append( asUUID( res['id'] ) )
            assert res['provenance_id'] == str( prov.id )
            assert res['diaobject_id'] == str( dobj.id )
            assert res['diaobject_position_id'] is None
            assert res['image_id'] == str( imid )
            assert res['template_id'] == str( template_id )
            assert res['flux'] == pytest.approx( flux, abs=0.1, rel=1e-6 )
            assert res['dflux'] == pytest.approx( dflux, abs=0.1, rel=1e-6 )

        # Make sure they got written
        with DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT COUNT(*) AS n FROM diaforcedsource" )
            tot_n_diaforcedsource = rows[0]['n']
            for photid, imid, flux, dflux in zip( photids, imids, fluxen, dfluxen ):
                rows = dbcon.execute( sql.SQL( "SELECT * FROM diaforcedsource WHERE id={pid}" )
                                      .format( pid=photid ) )
                assert len(rows) == 1
                row = rows[0]
                assert row['id'] == photid
                assert row['provenance_id'] == prov.id
                assert row['diaobject_id'] == dobj.id
                assert row['diaobject_position_id'] is None
                assert row['image_id'] == imid
                assert row['template_id'] == template_id
                assert row['flux'] == pytest.approx( flux, abs=0.1, rel=1e-6 )
                assert row['dflux'] == pytest.approx( dflux, abs=0.1, rel=1e-6 )

        # Set up base POST parameters for several following tests

        senddict = { 'provenance_id': str(prov.id),
                     'diaobject_id': str(dobj.id),
                     'diaobject_position_id': None,
                     'image_id': str(imids[0]),
                     'template_id': str(template_id),
                     'flux': fluxen[0],
                     'dflux': dfluxen[0]
                    }

        # Test writing an existing photometry point
        with pytest.raises( RuntimeError, match=( "Error response from server: "
                                                  "Error, diaforcedsource already exists." ) ):
            dbclient.send( "savediaforcedsource", senddict )

        # Now test exist_ok True with legiitimate matches and mismatches
        with DBCon() as dbcon:
            for atol, rtol in zip( [ None, 10. ], [ None, 'default', 1e-6, 1e-2 ] ):
                for val, err in ( (False, True), (True, False), (True, True) ):
                    mungabsflux = 0.
                    mungabsdflux = 0.
                    mungrelflux = 0.
                    mungreldflux = 0.
                    defaultrtol = ( rtol == 'default' )
                    rtol = 1e-6 if defaultrtol else rtol
                    if val:
                        mungabsflux = 0. if atol is None else atol
                        mungrelflux = fluxen[0] * ( 1e-6 if rtol is None else rtol )
                    if err:
                        mungabsflux = 0. if atol is None else atol
                        mungrelflux = dfluxen[0] * ( 1e-6 if rtol is None else rtol )

                    for ( mungflux, mungdflux ) in [ ( mungabsflux, mungabsdflux ),
                                                     ( mungrelflux, mungreldflux ),
                                                     ( mungabsflux + mungabsdflux, mungrelflux + mungreldflux ) ]:
                        for fac in [ 0.25, 1.5 ]:
                            # OMG it's a four-loop
                            thissend = senddict | { 'flux': fluxen[0] + mungflux * fac,
                                                    'dflux': dfluxen[0] + mungdflux * fac,
                                                    'exist_ok': True,
                                                    'atol': atol
                                                   }
                            if not defaultrtol:
                                thissend['rtol'] = rtol

                            if ( ( ( atol is None ) or ( thissend['flux'] - fluxen[0] <= atol ) )
                                 and
                                 ( ( rtol is None ) or ( thissend['flux'] - fluxen[0]
                                                         <= np.fabs( fluxen[0] * rtol ) ) )
                                 and
                                 ( ( atol is None ) or ( thissend['dflux'] - dfluxen[0] <= atol ) )
                                 and
                                 ( ( rtol is None ) or ( thissend['dflux'] - dfluxen[0]
                                                         <= np.fabs( dfluxen[0] * rtol ) ) )
                                ):
                                # If within tolerances, save should "work", but nothing is saved and
                                #   we get back what was in the database.
                                res = dbclient.send( "savediaforcedsource", thissend )
                                assert res['flux'] == pytest.approx( fluxen[0], abs=0.1, rel=1e-6 )
                                assert res['dflux'] == pytest.approx( dfluxen[0], abs=0.1, rel=1e-6 )
                                assert ( thissend['flux'] - res['flux'] ) == pytest.approx( mungflux * fac, abs=0.1 )
                                assert ( thissend['dflux'] - res['dflux'] ) == pytest.approx( mungdflux * fac, abs=0.1 )
                                rows, _cols = dbcon.execute( "SELECT COUNT(*) FROM diaforcedsource" )
                                assert rows[0][0] == tot_n_diaforcedsource

                            else:
                                # If outside tolerances, there should be an error
                                with pytest.raises( RuntimeError, match=( r"^Error response from server: "
                                                                          r"Error, a photometry point already exists "
                                                                          r"with flux/dflux within tolerances;" ) ):
                                    dbclient.send( "savediaforcedsource", thissend )


        # Test getting a photometry point
        for photid, imid, flux, dflux in zip( photids, imids, fluxen, dfluxen ):
            res = dbclient.send( f"getdiaforcedsource/{photid}" )
            assert res['id'] == str( photid )
            assert res['provenance_id'] == str( prov.id )
            assert res['diaobject_id'] == str( dobj.id )
            assert res['diaobject_position_id'] is None
            assert res['image_id'] == str( imid )
            assert res['template_id'] == str( template_id )
            assert res['flux'] == pytest.approx( flux, abs=0.1, rel=1e-6 )
            assert res['dflux'] == pytest.approx( dflux, abs=0.1, rel=1e-6 )

        # Test getting a lightcurve
        for ids in ( False, True ):
            expected_keys = { 'mjd', 'band', 'flux', 'dflux' }
            if ids:
                expected_keys = expected_keys.union( { 'id', 'image_id', 'template_id', 'diaobject_position_id' } )

            for sends in [ f"{prov.id}/{dobj.id}", f"test_diaforcedsource/fake_lightcurve/{dobj.id}" ]:
                if ids:
                    res = dbclient.send( f"getdiaforcedsourceltcv/{sends}", { 'include_ids': True } )
                else:
                    res = dbclient.send( f"getdiaforcedsourceltcv/{sends}" )
                assert set( res.keys() ) == expected_keys
                assert len( res['mjd'] ) == 7
                assert all ( r == pytest.approx( i.mjd, abs=0.001 ) for r, i in zip( res['mjd'], images[1:] ) )
                assert all ( r == i.band for r, i in zip( res['band'], images[1:] ) )
                assert all ( r == pytest.approx( f, abs=0.1, rel=1e-6 ) for r, f in zip( res['flux'], fluxen ) )
                assert all ( r == pytest.approx( df, abs=0.1, rel=1e-6 ) for r, df in zip( res['dflux'], dfluxen ) )
                if ids:
                    assert all( r == str(p) for r, p in zip( res['id'], photids ) )
                    assert all( r == str(i.id) for r, i in zip( res['image_id'], images[1:] ) )
                    assert all( r == str(template_id) for r in res['template_id'] )
                    assert all( r is None for r in res['diaobject_position_id'] )

    finally:
        with DBCon() as dbcon:
            if len(photids) > 0:
                dbcon.execute( sql.SQL( "DELETE FROM diaforcedsource WHERE id=ANY(ARRAY[{ids}])" )
                               .format( ids=sql.SQL(",").join( photids ) ) )
            if prov is not None:
                dbcon.execute( sql.SQL( "DELETE FROM provenance_tag WHERE provenance_id={provid}" )
                               .format( provid=prov.id ) )
                dbcon.execute( sql.SQL( "DELETE FROM provenance WHERE id={provid}" )
                               .format( provid=prov.id ) )
            dbcon.commit()


def test_processing_run( dbclient, stupid_object ):
    process = 'test_processing_run'
    epoch = 60000123
    key = { 'process': process, 'diaobject_id': str(stupid_object), 'epoch': epoch }
    provid = None
    try:
        # A run that does not exist is created as 'processing'
        res = dbclient.send( "startprocessingrun", { **key, 'execution': 'exec-1' } )
        assert res['status'] == 'processing'
        assert res['execution'] == 'exec-1'
        assert res['epoch'] == epoch
        assert res['started_at'] is not None and res['finished_at'] is None
        runid = res['id']

        # Starting it again is not refused: it is the same row, started again by another execution
        res = dbclient.send( "startprocessingrun", { **key, 'execution': 'exec-2' } )
        assert res['status'] == 'processing'
        assert res['id'] == runid
        assert res['execution'] == 'exec-2'

        # Finish it
        provid = Provenance( process="test_processing_run_product", major=1, minor=0 )
        provid.save_to_db()
        res = dbclient.send( "finishprocessingrun", { **key, 'status': 'done', 'provenance_id': str(provid.id) } )
        assert res['updated'] is True
        assert res['status'] == 'done'
        assert res['provenance_id'] == str( provid.id )
        assert res['finished_at'] is not None
        assert res['execution'] == 'exec-2'

        # A late or repeated finish does not change it
        res = dbclient.send( "finishprocessingrun", { **key, 'status': 'failed', 'message': 'too late' } )
        assert res['updated'] is False
        assert res['status'] == 'done'
        assert res['message'] is None

        # A run that is done can be started again (a repeat on purpose); starting it clears what it said
        res = dbclient.send( "startprocessingrun", { **key, 'execution': 'exec-5' } )
        assert res['id'] == runid
        assert res['status'] == 'processing'
        assert res['provenance_id'] is None and res['finished_at'] is None
        assert res['execution'] == 'exec-5'
        res = dbclient.send( "finishprocessingrun", { **key, 'status': 'done', 'provenance_id': str(provid.id) } )
        assert res['updated'] is True and res['status'] == 'done'

        # A failed run can be started again, and starting it clears what it said
        failkey = { **key, 'epoch': epoch + 1 }
        res = dbclient.send( "startprocessingrun", failkey )
        assert res['status'] == 'processing'
        res = dbclient.send( "finishprocessingrun", { **failkey, 'status': 'failed', 'message': 'it broke',
                                                      'execution': 'exec-3' } )
        assert ( res['status'], res['message'], res['execution'] ) == ( 'failed', 'it broke', 'exec-3' )
        res = dbclient.send( "startprocessingrun", { **failkey, 'execution': 'exec-4' } )
        assert res['status'] == 'processing'
        assert res['message'] is None and res['finished_at'] is None and res['provenance_id'] is None
        assert res['execution'] == 'exec-4'

        # Find
        res = dbclient.send( "findprocessingruns", { 'process': process } )
        assert { r['epoch'] for r in res } == { epoch, epoch + 1 }
        res = dbclient.send( "findprocessingruns", { 'process': process, 'status': 'done' } )
        assert [ r['epoch'] for r in res ] == [ epoch ]
        res = dbclient.send( "findprocessingruns", { 'diaobject_id': str(stupid_object), 'epoch': epoch + 1 } )
        assert [ r['status'] for r in res ] == [ 'processing' ]
        res = dbclient.send( "findprocessingruns", { 'process': process, 'order_by': 'epoch', 'limit': 1 } )
        assert [ r['epoch'] for r in res ] == [ epoch ]
        assert dbclient.send( "findprocessingruns", { 'process': 'no_such_process' } ) == []

        # Errors
        with pytest.raises( RuntimeError, match='^Error response from server.*No run of' ):
            dbclient.send( "finishprocessingrun", { **key, 'epoch': epoch + 5, 'status': 'done' } )
        with pytest.raises( RuntimeError, match='^Error response from server.*Unknown status' ):
            dbclient.send( "finishprocessingrun", { **key, 'status': 'processing' } )
        with pytest.raises( RuntimeError, match='^Error response from server.*epoch must be an integer' ):
            dbclient.send( "startprocessingrun", { **key, 'epoch': '60000123' } )
        with pytest.raises( RuntimeError, match='^Error response from server.*epoch must be an integer' ):
            dbclient.send( "startprocessingrun", { **key, 'epoch': True } )
        with pytest.raises( RuntimeError, match='^Error response from server.*diaobject_id must be a UUID' ):
            dbclient.send( "startprocessingrun", { **key, 'diaobject_id': 'not-a-uuid' } )
        with pytest.raises( RuntimeError, match='^Error response from server.*process must be' ):
            dbclient.send( "startprocessingrun", { **key, 'process': '  ' } )
        with pytest.raises( RuntimeError, match='^Error response from server.*Missing required keys' ):
            dbclient.send( "startprocessingrun", { 'process': process } )
        with pytest.raises( RuntimeError, match='^Error response from server.*Unknown keys' ):
            dbclient.send( "startprocessingrun", { **key, 'bogus': 1 } )
        with pytest.raises( RuntimeError, match='^Error response from server.*violates foreign key' ):
            dbclient.send( "startprocessingrun", { **key, 'diaobject_id': str( uuid.uuid4() ) } )
    finally:
        with DBCon() as con:
            con.execute( "DELETE FROM processing_run WHERE process=%(p)s", { 'p': process } )
            if provid is not None:
                con.execute( "DELETE FROM provenance WHERE id=%(id)s", { 'id': provid.id } )
            con.commit()


def test_spectrum1d_with_included_images( dbclient, stupid_provenance, stupid_object ):
    images = []
    spectra = []
    try:
        for i in range( 3 ):
            ra = 180. + i
            images.append( Image( id=uuid.uuid4(), filepath=f'spec_included_image_{i}',
                                  provenance_id=stupid_provenance, width=1024, height=1024,
                                  observation_id=str(i), sca=1, band='PRISM', ra=ra, dec=0.,
                                  ra_corner_00=ra-0.2, ra_corner_01=ra-0.2, ra_corner_10=ra+0.2,
                                  ra_corner_11=ra+0.2, dec_corner_00=-0.2, dec_corner_01=0.2,
                                  dec_corner_10=-0.2, dec_corner_11=0.2, mjd=60000.+i, exptime=100, format=1 ) )
            images[-1]._position_angle = 0.
            images[-1].save_to_db()
        ids = [ str(i.id) for i in images ]

        specid = str( uuid.uuid4() )
        spectra.append( specid )
        payload = { 'id': specid, 'provenance_id': str(stupid_provenance), 'diaobject_id': str(stupid_object),
                    'diaobject_position_id': None, 'band': 'PRISM', 'filepath': 's3://bucket/spec_output/final/a.parquet',
                    'mjd_start': 60000., 'mjd_end': 60002.01, 'epoch': 60001000,
                    'included_image_ids': [ ids[2], ids[0] ] }

        res = dbclient.send( "savespectrum1d", payload )
        assert res['id'] == specid
        assert res['filepath'] == 's3://bucket/spec_output/final/a.parquet'
        assert res['diaobject_position_id'] is None
        assert res['included_image_ids'] == sorted( [ ids[0], ids[2] ] )

        res = dbclient.send( f"getspectrum1d/{specid}" )
        assert res['included_image_ids'] == sorted( [ ids[0], ids[2] ] )

        res = dbclient.send( "findspectra1d", { 'provenance': str(stupid_provenance), 'diaobject_id': str(stupid_object),
                                                'filepath': 's3://bucket/spec_output/final/a.parquet' } )
        assert [ r['id'] for r in res ] == [ specid ]
        assert res[0]['included_image_ids'] == sorted( [ ids[0], ids[2] ] )
        assert dbclient.send( "findspectra1d", { 'provenance': str(stupid_provenance),
                                                  'filepath': 's3://bucket/spec_output/final/other.parquet' } ) == []

        # The same registration again changes nothing
        res = dbclient.send( "savespectrum1d", payload )
        assert res['included_image_ids'] == sorted( [ ids[0], ids[2] ] )
        assert len( dbclient.send( "findspectra1d", { 'provenance': str(stupid_provenance) } ) ) == 1

        # A run again for the same key points to the new file (its version is in its name) and
        # replaces the images that went in
        payload2 = { **payload, 'filepath': 's3://bucket/spec_output/final/a_v2.parquet', 'mjd_end': 60003.0,
                     'included_image_ids': ids }
        res = dbclient.send( "savespectrum1d", payload2 )
        assert res['filepath'] == 's3://bucket/spec_output/final/a_v2.parquet'
        assert res['mjd_end'] == 60003.0
        assert res['included_image_ids'] == sorted( ids )

        # No list sent: the images are left as they are
        payload3 = { k: v for k, v in payload2.items() if k != 'included_image_ids' }
        payload3['filepath'] = 's3://bucket/spec_output/final/a_v3.parquet'
        res = dbclient.send( "savespectrum1d", payload3 )
        assert res['filepath'] == 's3://bucket/spec_output/final/a_v3.parquet'
        assert res['included_image_ids'] == sorted( ids )

        # An empty list means none
        res = dbclient.send( "savespectrum1d", { **payload3, 'included_image_ids': [] } )
        assert res['included_image_ids'] == []

        # What identifies a spectrum cannot change under its id
        with pytest.raises( RuntimeError, match='^Error response from server.*different epoch' ):
            dbclient.send( "savespectrum1d", { **payload, 'epoch': 60002000 } )
        # The database's own unique key (provenance, object, epoch) refuses another id
        with pytest.raises( RuntimeError, match='^Error response from server.*unique' ):
            dbclient.send( "savespectrum1d", { **payload, 'id': str( uuid.uuid4() ) } )
        # Unknown images and bad ids
        with pytest.raises( RuntimeError, match='^Error response from server.*foreign key' ):
            dbclient.send( "savespectrum1d", { **payload, 'included_image_ids': [ str( uuid.uuid4() ) ] } )
        with pytest.raises( RuntimeError, match='^Error response from server.*must be UUIDs' ):
            dbclient.send( "savespectrum1d", { **payload, 'included_image_ids': [ 'x' ] } )
        with pytest.raises( RuntimeError, match='^Error response from server.*must be a list' ):
            dbclient.send( "savespectrum1d", { **payload, 'included_image_ids': ids[0] } )

        # A spectrum written the old way (nine fields, no images) still works
        old = { 'id': str( uuid.uuid4() ), 'provenance_id': str(stupid_provenance),
                'diaobject_id': str(stupid_object), 'diaobject_position_id': None, 'band': 'PRISM',
                'filepath': 'old.hdf5', 'mjd_start': 60000., 'mjd_end': 60001., 'epoch': 60005000 }
        spectra.append( old['id'] )
        res = dbclient.send( "savespectrum1d", old )
        assert res['included_image_ids'] == []
    finally:
        with DBCon() as con:
            if len( spectra ) > 0:
                con.execute( "DELETE FROM spectrum1d_included_image WHERE spectrum1d_id=ANY(%(ids)s::uuid[])",
                             { 'ids': spectra } )
                con.execute( "DELETE FROM spectrum1d WHERE id=ANY(%(ids)s::uuid[])", { 'ids': spectra } )
            if len( images ) > 0:
                con.execute( "DELETE FROM l2image WHERE id=ANY(%(ids)s)", { 'ids': [ i.id for i in images ] } )
            con.commit()


def test_findl2images_without_a_provenance( dbclient ):
    """No provenance: the images of every provenance are searched; with one, only its images."""
    provs = []
    images = []
    try:
        for n in range( 2 ):
            prov = Provenance( process=f"test_findl2images_any_{n}", major=1, minor=0 )
            prov.save_to_db()
            provs.append( prov )
            im = Image( id=uuid.uuid4(), filepath=f'findl2images_any_{uuid.uuid4()}', provenance_id=prov.id,
                        width=1024, height=1024, observation_id=f'any{n}', sca=n+1, band='PRISM',
                        ra=150.0, dec=2.0, ra_corner_00=149.9, ra_corner_01=149.9, ra_corner_10=150.1,
                        ra_corner_11=150.1, dec_corner_00=1.9, dec_corner_01=2.1, dec_corner_10=1.9,
                        dec_corner_11=2.1, mjd=60000.+n, exptime=100, format=1 )
            im._position_angle = 0.
            im.save_to_db()
            images.append( im )
        ids = { str(i.id) for i in images }
        query = { 'band': 'PRISM', 'ra': 150.0, 'dec': 2.0 }

        res = dbclient.send( "findl2images", query )
        assert ids <= { str(r['id']) for r in res }
        res = dbclient.send( "findl2images", { **query, 'provenance': str(provs[0].id) } )
        assert [ str(r['id']) for r in res ] == [ str(images[0].id) ]
        res = dbclient.send( "findl2images", { **query, 'ra': 10.0, 'dec': -50.0 } )
        assert ids.isdisjoint( { str(r['id']) for r in res } )
        with pytest.raises( RuntimeError, match='^Error response from server.*process needs provenance_tag' ):
            dbclient.send( "findl2images", { **query, 'process': 'test_findl2images_any_0' } )
    finally:
        with DBCon() as con:
            for im in images:
                con.execute( "DELETE FROM l2image WHERE id=%(id)s", { 'id': im.id } )
            for prov in provs:
                con.execute( "DELETE FROM provenance WHERE id=%(id)s", { 'id': prov.id } )
            con.commit()


def test_one_file_under_two_provenances( dbclient ):
    """filepath is not unique: a file processed again is a row of its own, under its provenance."""
    provs = []
    ids = []
    filepath = f'mast:ROMAN/product/two_provenances_{uuid.uuid4()}_cal.asdf'
    try:
        for n in range( 2 ):
            prov = Provenance( process="test_two_provenances", major=1, minor=0,
                               params={ 'calibration_software_version': f'1.0.{n}' } )
            prov.save_to_db()
            provs.append( prov )
        rows = []
        for n, prov in enumerate( provs ):
            ids.append( str( uuid.uuid4() ) )
            rows.append( { 'id': ids[-1], 'provenance_id': str(prov.id), 'band': 'PRISM', 'ra': 151.0, 'dec': 3.0,
                           'ra_corner_00': 150.9, 'ra_corner_01': 150.9, 'ra_corner_10': 151.1,
                           'ra_corner_11': 151.1, 'dec_corner_00': 2.9, 'dec_corner_01': 3.1,
                           'dec_corner_10': 2.9, 'dec_corner_11': 3.1, 'filepath': filepath, 'format': 100,
                           'mjd': 60000., 'exptime': 100., 'observation_id': 'two_prov', 'sca': 1,
                           'filedate': f'2026-11-0{n+1}T12:00:00+00:00' } )

        # The bulk save with ignore_conflicts: both rows go in, although they have the same filepath
        columns = { key: [ row[key] for row in rows ] for key in rows[0] }
        res = dbclient.send( "bulksavel2images?ignore_conflicts=1", columns )
        assert res['inserted'] == 2
        found = dbclient.send( "findl2images", { 'filepath': filepath } )
        assert sorted( str(r['id']) for r in found ) == sorted( ids )
        # filedate is saved and returned, and tells the two apart
        by_id = { str(r['id']): r for r in found }
        assert by_id[ids[0]]['filedate'] < by_id[ids[1]]['filedate']
        assert by_id[ids[0]]['provenance_id'] != by_id[ids[1]]['provenance_id']

        # The same rows again change nothing
        res = dbclient.send( "bulksavel2images?ignore_conflicts=1", columns )
        assert res['inserted'] == 0
        assert len( dbclient.send( "findl2images", { 'filepath': filepath } ) ) == 2

        # The id is the only unique key left: the same id again is refused by savel2image
        with pytest.raises( RuntimeError, match='^Error response from server' ):
            dbclient.send( "savel2image", rows[0] )

        # The segmentation maps of the two processings of the file have one file too
        segpath = filepath.replace( '_cal.', '_segm.' )
        segids = []
        for row in rows:
            segids.append( str( uuid.uuid4() ) )
            dbclient.send( "savesegmap", { 'id': segids[-1], 'provenance_id': row['provenance_id'], 'band': 'PRISM',
                                           'ra': 151.0, 'dec': 3.0, 'ra_corner_00': 150.9, 'ra_corner_01': 150.9,
                                           'ra_corner_10': 151.1, 'ra_corner_11': 151.1, 'dec_corner_00': 2.9,
                                           'dec_corner_01': 3.1, 'dec_corner_10': 2.9, 'dec_corner_11': 3.1,
                                           'filepath': segpath, 'format': 0, 'l2image_id': row['id'] } )
        for row in rows:
            found = dbclient.send( "findsegmaps", { 'provenance': row['provenance_id'], 'filepath': segpath } )
            assert [ r['l2image_id'] for r in found ] == [ row['id'] ]

        # An image saved without filedate has none
        plain = dict( rows[0], id=str( uuid.uuid4() ), observation_id='two_prov_plain' )
        del plain['filedate']
        ids.append( plain['id'] )
        dbclient.send( "savel2image", plain )
        found = dbclient.send( "findl2images", { 'filepath': filepath, 'provenance': str(provs[0].id) } )
        assert { str(r['id']): r['filedate'] for r in found }[plain['id']] is None
    finally:
        with DBCon() as con:
            con.execute( "DELETE FROM segmap WHERE filepath=%(path)s", { 'path': filepath.replace( '_cal.', '_segm.' ) } )
            con.execute( "DELETE FROM l2image WHERE id=ANY(%(ids)s::uuid[])", { 'ids': ids } )
            for prov in provs:
                con.execute( "DELETE FROM provenance WHERE id=%(id)s", { 'id': prov.id } )
            con.commit()
