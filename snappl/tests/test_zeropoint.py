import pytest
from psycopg import sql
from snappl.db.db import DBCon
from snappl.zeropoint import Zeropoint
from snappl.image import Image


@pytest.fixture( scope="module" )
def savedzp( stupid_image, stupid_provenance, dbclient ):
    zpid = None
    try:
        zp = Zeropoint( 42.0, 0.42, image_id=stupid_image, provenance_id=stupid_provenance )
        zpid = zp.id
        zp.save()
        return zp
    finally:
        with DBCon() as con:
            con.execute_nofetch( sql.SQL( "DELETE FROM zeropoint WHERE id={zpid}" ).format( zpid=zpid ) )
            con.commit()


def test_savezp( savedzp ):
    def checkzp( zp ):
        assert zp.id == savedzp.id
        assert zp.image_id == savedzp.image_id
        assert zp.provenance_id == savedzp
        assert zp.zp == pytest.approx( savedzp.zp, abs=1e-5 )
        assert zp.dzp == pytest.approx( savedzp.dzp, abs=1e-5 )

    # Make sure the save in the fixture worked
    with DBCon() as con:
        rows = con.execute( sql.SQL( "SELECT * FROM zeropoint WEHRE id={zpid}" ).format( zpid=savedzp.id ) )
        assert len(rows) == 1
        zp = rows[0]
        assert zp.id == savedzp.id
        assert zp.image_id == savedzp.image_id
        assert zp.provenance_id == savedzp.provenance_id
        assert zp.zp == pytest.approx( savedzp.zp, abs=1e-5 )
        assert zp.dzp == pytest.approx( savedzp.zp, abs=1e-5 )

    # Try saving when it already exists, and things match well enough
    zp = Zeropoint( 42.0 + 0.42*0.005, 0.995*0.42, image_id=savedzp.image_id, provenance_id=savedzp.provenance_id )
    zp.save()
    checkzp( zp )

    # Try saving when it already exists, and things match well enough
    zp = Zeropoint( 42.0 + 0.42*0.005, 0.995*0.42, image_id=savedzp.image_id, provenance_id=savedzp.provenance_id,
                    id=savedzp.id )
    zp.save()
    checkzp( zp )


    # TODO: TEST FAILURES


def test_get_image( stupid_image, savedzp ):
    img = savedzp.get_image()
    assert isinstance( img, Image )
    assert img.id == stupid_image


def test_get( savedzp, stupid_provenance, stupid_image ):
    def checkzp( zp ):
        assert zp.id == savedzp.id
        assert zp.image_id == stupid_image
        assert zp.provenance_id == stupid_provenance
        assert zp.zp == pytest.approx( savedzp, abs=1e-5 )
        assert zp.dzp == pytest.approx( savedzp, abs=1e-5 )

    zp = Zeropoint.get_for_image( stupid_image, zp_prov_id=savedzp.provenance_id )
    checkzp( zp )

    zp = Zeropoint.get_for_image( stupid_image, zp_prov_tag='stupid_provenance_tag', zp_process='foo' )
    checkzp( zp )

    zp = Zeropoint.get_by_id( savedzp.id )
    checkzp( zp )

    # Check failures?
