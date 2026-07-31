import pytest

from psycopg import sql

from snappl.db.db import DBCon
from snappl.image import Image
from snappl.provenance import Provenance
from snappl.zeropoint import Zeropoint


@pytest.fixture( scope="module" )
def zp_prov():
    prov = Provenance( 'testzp', 0, 0, { 'subclass': 'Zeropoint' } )
    try:
        with DBCon() as con:
            prov.save_to_db( 'zp_provtag' )
        yield prov
    finally:
        with DBCon() as con:
            con.execute( "DELETE FROM provenance_tag WHERE tag='zp_provtag'" )
            con.execute( sql.SQL( "DELETE FROM provenance WHERE id={pid}" ).format( pid=prov.id ) )
            con.commit()


@pytest.fixture( scope="module" )
def savedzp( stupid_images, zp_prov, dbclient ):
    zpid = None
    try:
        zp = Zeropoint.get_zeropoint( image=stupid_images[0], provenance=zp_prov,
                                      zp=42.0, dzp=0.42, meta={}, subclass="Zeropoint" )
        zp.save()
        zpid = zp.id
        yield zp
    finally:
        if zpid is not None:
            with DBCon() as con:
                con.execute_nofetch( sql.SQL( "DELETE FROM zeropoint WHERE id={zpid}" ).format( zpid=zpid ) )
                con.commit()


def test_savezp( savedzp ):
    def checkzp( zp ):
        assert zp.id == savedzp.id
        assert zp.image_id == savedzp.image_id
        assert zp.provenance_id == savedzp.provenance_id
        assert zp.zp(0, 0) == pytest.approx( savedzp.zp(0, 0), abs=1e-5 )
        _zp, _dzp = zp.zp( 0, 0, dzp=True )
        _savedzp, _saveddzp = savedzp.zp( 0, 0, dzp=True )
        assert _zp == pytest.approx( _savedzp, abs=1e-5 )
        assert _dzp == pytest.approx( _saveddzp, abs=1e-5 )
        assert zp.meta == {}

    # Make sure the save in the fixture worked
    with DBCon( dictcursor=True ) as con:
        rows = con.execute( sql.SQL( "SELECT * FROM zeropoint WHERE id={zpid}" ).format( zpid=savedzp.id ) )
        assert len(rows) == 1
        zp = rows[0]
        assert zp['id'] == savedzp.id
        assert zp['image_id'] == savedzp.image_id
        assert zp['provenance_id'] == savedzp.provenance_id
        _savedzp, _saveddzp = savedzp.zp( 0, 0, dzp=True )
        assert zp['zp'] == pytest.approx( _savedzp, abs=1e-5 )
        assert zp['dzp'] == pytest.approx( _saveddzp, abs=1e-5 )
        assert zp['meta'] == savedzp.meta

    # Try saving when it already exists, and things match well enough.
    # This call should update zp and dzp to match what's in the database.
    zp = Zeropoint.get_zeropoint( image=savedzp.image_id, provenance=savedzp.provenance_id,
                                  zp=42.0 + 0.42*0.005, dzp=0.995*0.42, meta={}, subclass="Zeropoint" )
    zp.save()
    checkzp( zp )

    # TODO: TEST FAILURES


def test_get_image( stupid_images, savedzp ):
    img = savedzp.get_image()
    assert isinstance( img, Image )
    assert img.id == stupid_images[0]


def test_get( savedzp, zp_prov, stupid_images ):
    def checkzp( zp ):
        assert zp.id == savedzp.id
        assert zp.image_id == stupid_images[0]
        assert zp.provenance_id == zp_prov.id
        assert zp.zp(0, 0) == pytest.approx( savedzp.zp(0, 0), abs=1e-5 )
        _zp, _dzp = zp.zp( 0, 0, dzp=True )
        _savedzp, _saveddzp = savedzp.zp( 0, 0, dzp=True )
        assert _zp == pytest.approx( _savedzp, abs=1e-5 )
        assert _dzp == pytest.approx( _saveddzp, abs=1e-5 )
        assert zp.meta == savedzp.meta

    zp = Zeropoint.get_for_image( stupid_images[0], zp_prov_id=savedzp.provenance_id )
    checkzp( zp )

    zp = Zeropoint.get_for_image( stupid_images[0], zp_prov_tag='zp_provtag', zp_process='testzp' )
    checkzp( zp )

    zp = Zeropoint.get_by_id( savedzp.id )
    checkzp( zp )

    zp = Zeropoint.get_zeropoint( image=stupid_images[0], provenance=zp_prov.id )
    checkzp( zp )

    zp = Zeropoint.get_zeropoint( image=stupid_images[0], provenance_tag="zp_provtag", process="testzp" )
    checkzp( zp )

    # Check failures?
