import pytest
import numbers
import uuid

import numpy as np

import snappl.db.db
from snappl.spectrum1d import Spectrum1d
from snappl.logger import SNLogger

# MORE TESTS TO WRITE
#  * write tests that check that the verification in _set_data_dict works right
#  * write tests with non-database spectra, saving to non-standard file paths


@pytest.fixture
def bogus_images( stupid_provenance ):
    imgids = [ uuid.uuid4(), uuid.uuid4() ]
    try:
        with snappl.db.db.DBCon() as dbcon:
            dbcon.execute( "INSERT INTO l2image(id, provenance_id, band, ra, dec,"
                           "  ra_corner_00, ra_corner_01, ra_corner_10, ra_corner_11, "
                           "  dec_corner_00, dec_corner_01, dec_corner_10, dec_corner_11, "
                           "  filepath, format, mjd, exptime) "
                           "VALUES( %(id)s, %(provid)s, 'r', 128., 42., "
                           "  127.5, 127.5, 128.5, 128.5, 41.5, 42.5, 41.5, 42.5, "
                           "  '/foo/bar', 0, 60000., 100. )",
                           { 'id': imgids[0], 'provid': stupid_provenance }
                          )
            dbcon.execute( "INSERT INTO l2image(id, provenance_id, band, ra, dec,"
                           "  ra_corner_00, ra_corner_01, ra_corner_10, ra_corner_11, "
                           "  dec_corner_00, dec_corner_01, dec_corner_10, dec_corner_11, "
                           "  filepath, format, mjd, exptime) "
                           "VALUES( %(id)s, %(provid)s, 'r', 128., 42., "
                           "  127.5, 127.5, 128.5, 128.5, 41.5, 42.5, 41.5, 42.5, "
                           "  '/bar/foo', 0, 60000.1, 100. )",
                           { 'id': imgids[1], 'provid': stupid_provenance }
                          )
            dbcon.commit()

        yield imgids
    finally:
        with snappl.db.db.DBCon() as dbcon:
            dbcon.execute( "DELETE FROM l2image WHERE id=ANY(%(ids)s)", {'ids': imgids} )
            dbcon.commit()



@pytest.fixture
def gratuitous_spectrum( stupid_provenance, stupid_object, bogus_images ):
    data_dict = {
        'meta': {
            'provenance_id': stupid_provenance,
            'diaobject_id': stupid_object,
            'band': "The Beatles",
        },
        'combined': {
            'meta': { 'nfiles': 2 },
            'data': { 'lamb': np.array( [ 6000., 6010., 6020., 6030., 6040., 6050. ] ),
                      'flam': np.array( [   1.0,   1.5,   1.7,   1.5,   1.2,   1.0 ] ),
                      'func': np.array( [   0.1,   0.2,   0.2,   0.2,   0.1,   0.1 ] ),
                      'count': np.array( [    1,     2,     2,     2,     2,     1 ] )
                     }
        },
        'individual': [
            { 'meta': { 'image_id': bogus_images[0],
                        'x0': 512.,
                        'y0': 256.
                       },
              'data': { 'lamb': np.array( [ 6002., 6012., 6022., 6032., 6042. ] ),
                        'flam': np.array( [   1.0,   1.5,   1.7,   1.5,   1.2 ] ),
                        'func': np.array( [   0.1,   0.2,   0.2,   0.2,   0.1 ] )
                       }
             },
            { 'meta': { 'image_id': bogus_images[1],
                        'x0': 489.,
                        'y0': 137.,
                       },
              'data': { 'lamb': np.array( [ 6008., 6018., 6028., 6038., 6048. ] ),
                        'flam': np.array( [   1.5,    1.7,  1.5,   1.2,   1.0 ] ),
                        'func': np.array( [   0.2,    0.2,  0.2,   0.1,   0.1 ] )
                       }
             }
        ]
    }

    return data_dict


@pytest.fixture
def saved_gratuitous_spectrum( gratuitous_spectrum, dbclient ):
    spec = Spectrum1d( data_dict=gratuitous_spectrum, dbclient=dbclient )
    try:
        spec.save_to_db( write=True, dbclient=dbclient )
        yield spec
    finally:
        spec.full_filepath.unlink( missing_ok=True )
        with snappl.db.db.DBCon() as dbcon:
            dbcon.execute( "DELETE FROM spectrum1d WHERE id=%(id)s", {'id':spec.id} )
            dbcon.commit()


def recursive_compare( val1, val2, path='' ):
    if isinstance( val1, dict ):
        if not isinstance( val2, dict ):
            SNLogger.error( f"At {path}, left is a dict but right isn't" )
            return False
        if set( val1.keys() ) != set( val2.keys() ):
            SNLogger.error( f"At {path}, left and right don't have the same keys" )
            return False
        for key in val1:
            if not recursive_compare( val1[key], val2[key], path=f'{path}{key}.' ):
                return False
            return True

    elif isinstance( val1, list ):
        if not isinstance( val2, list ):
            SNLogger.error( f"At {path}, left is a list but right isn't" )
            return False
        if len(val1) != len(val2):
            SNLogger.error( f"At {path}, left and right don't have the same length" )
            return False
        for dex, ( item1, item2 ) in enumerate( zip( val1, val2 ) ):
            if not recursive_compare( item1, item2, path=f'{path}{dex}.' ):
                return False
            return True

    elif isinstance( val1, uuid.UUID ) or isinstance( val2, uuid.UUID ):
        if str( val1 ) == str( val2 ):
            return True
        else:
            SNLogger.error( f"At {path}, left and right don't match" )
            return False

    elif isinstance( val1, numbers.Real )  and not isinstance( val1, numbers.Integral ):
        if val1 == pytest.approx( val2, rel=1e-7 ):
            return True
        else:
            SNLogger.error( f"At {path}, left and right don't match within 1e-7" )
            return False

    else:
        if val1 == val2:
            return True
        else:
            SNLogger.error( f"At {path}, left and right don't match" )
            return False



def test_write_and_read_spectrum( bogus_images, gratuitous_spectrum ):
    ofpath = None
    try:
        spec = Spectrum1d( data_dict=gratuitous_spectrum, no_database=True )
        ofpath = spec.full_filepath
        spec.write_file()

        newspec = Spectrum1d( filepath=spec.filepath, no_database=True )
        assert recursive_compare( newspec.data_dict, spec.data_dict )



    finally:
        if ofpath is not None:
            ofpath.unlink( missing_ok=True )


def test_save_to_db( bogus_images, gratuitous_spectrum, dbclient ):
    spec = Spectrum1d( data_dict=gratuitous_spectrum, dbclient=dbclient )
    try:
        spec.save_to_db( write=False, dbclient=dbclient )
        assert not spec.full_filepath.exists()
        with snappl.db.db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", {'id': spec.id} )
            assert len(rows) == 1
            assert str(rows[0]['filepath']) == str(spec.filepath)
            # Could check other things, but naah, will effectively check that when
            #   we test get_spectrum
            dbcon.execute("DELETE FROM spectrum1d WHERE id=%(id)s", {'id': spec.id} )
            dbcon.commit()

        spec.save_to_db( write=True, dbclient=dbclient )
        assert spec.full_filepath.is_file()
        with snappl.db.db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", {'id': spec.id} )
            assert len(rows) == 1
            assert str(rows[0]['filepath']) == str(spec.filepath)

        oldspec = Spectrum1d( data_dict=gratuitous_spectrum, dbclient=dbclient )
        assert recursive_compare( spec.data_dict, oldspec.data_dict )

    finally:
        spec.full_filepath.unlink( missing_ok=True )
        with snappl.db.db.DBCon() as dbcon:
            dbcon.execute( "DELETE FROM spectrum1d WHERE id=%(id)s", {'id': spec.id} )
            dbcon.commit()


def test_get_find( saved_gratuitous_spectrum, dbclient ):
    # This test isn't great as there's only one spectrum saved.  We
    # should probably beef up this test by saving several test spectra
    # and making sure that searching really does the right thing.

    # Make sure we error out if we ask for a non-existent spectrum
    Spectrum1d.get_spectrum1d( uuid.uuid4(), dbclient=dbclient )
