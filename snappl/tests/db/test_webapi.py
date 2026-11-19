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
