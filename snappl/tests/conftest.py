import pytest
import uuid
import pathlib
import simplejson

import numpy as np
import psycopg.types

from astropy.io import fits

import tox # noqa: F401
from tox.pytest import init_fixture # noqa: F401

from snappl.imagecollection import ImageCollection
from snappl.image import FITSImage, RomanDatamodelImage
from snappl.admin.load_snana_ou2024_diaobject import load_snana_ou2024_diaobject
from snappl.config import Config
from snappl.dbclient import SNPITDBClient
from snappl.provneance import Provenance
from snappl.db.db import DBCon


@pytest.fixture( scope='session' )
def output_directories():
    outdir = pathlib.Path( 'test_output' )
    if outdir.exists() and not outdir.is_dir():
        raise RuntimeError( f"{outdir} exists but is not a directory" )
    outdir.mkdir( parents=True, exist_ok=True )

    plotdir = pathlib.Path( 'test_plots' )
    if plotdir.exists() and not plotdir.is_dir():
        raise RuntimeError( f"{plotdir} exists but is not a directory" )
    plotdir.mkdir( parents=True, exist_ok=True )

    return outdir, plotdir


@pytest.fixture( scope='session', autouse=True )
def init_config():
    Config.init( '/home/snappl/snappl/tests/snappl_test_config.yaml', setdefault=True )


@pytest.fixture( scope="session" )
def ou2024collection():
    return ImageCollection.get_collection( 'ou2024' )


@pytest.fixture( scope='session' )
def ou2024imagerelpath():
    return 'Y106/13205/Roman_TDS_simple_model_Y106_13205_1.fits.gz'


@pytest.fixture( scope='module' )
def ou2024imagepath( ou2024imagerelpath, ou2024collection ):
    return str( ou2024collection.base_path / ou2024imagerelpath )


@pytest.fixture
def ou2024image( ou2024collection, ou2024imagerelpath ):
    return ou2024collection.get_image( path=ou2024imagerelpath )


# If you use this next fixture, you aren't supposed
#   to modify the image!  Make sure any modifications
#   you make are undone at the end of your test.
@pytest.fixture( scope='module' )
def ou2024image_module(  ou2024collection, ou2024imagerelpath ):
    image = ou2024collection.get_image( path=ou2024imagerelpath )
    image.get_data( which='all', cache=True )
    image.get_wcs()
    return image


@pytest.fixture
def manual_fits_image( ou2024imagepath):
    header = fits.open(ou2024imagepath)[0].header
    data = np.ones((25, 25), dtype = np.float32)
    noise = np.zeros((25, 25), dtype = np.float32)
    flags = np.zeros((25, 25), dtype = np.uint32)
    return FITSImage( path=ou2024imagepath, header=header, data=data, noise=noise, flags=flags )


@pytest.fixture
def romandatamodel_image_path():
    return '/photometry_test_data/sample_asdf_data/F106_WFI1_MJD60627.5_inject_cal.asdf'


@pytest.fixture
def romandatamodel_image( romandatamodel_image_path ):
    image = RomanDatamodelImage( romandatamodel_image_path )
    return image



# If you use this next fixture, you aren't supposed
#   to modify the image!  Make sure any modifications
#   you make are undone at the end of your test.
@pytest.fixture( scope='module' )
def fitsimage_module( ou2024imagepath, ou2024image_module ):
    # Hack our way into having an object of the FITSImage type.
    #   Normally you don't instantiate a FITS image, but for our tests
    #   build one up.  Never do something like this (i.e. accessing the
    #   underscored members of an object) in code outside this test
    #   fixture.
    fitsim = FITSImage( ou2024imagepath )
    orighdr = ou2024image_module._header
    fitsim._header = ou2024image_module.get_fits_header()
    fitsim._wcs = ou2024image_module._wcs
    # Undo the internal change that get_fits_header made to ou2024image
    ou2024image._header = orighdr
    img, noi, flg = ou2024image_module.get_data( always_reload=False )
    fitsim._data = img
    fitsim._noise = noi
    fitsim._flags = flg

    return fitsim


@pytest.fixture
def unloaded_fitsimage_basepath():
    return '/photometry_test_data/simple_gaussian_test/sig1.0/test_60030.0'


@pytest.fixture
def unloaded_fitsimage( unloaded_fitsimage_basepath ):
    p = unloaded_fitsimage_basepath
    return FITSImage( path=f'{p}_image.fits',
                      noisepath=f'{p}_noise.fits',
                      flagspath=f'{p}_flags.fits',
                     )


@pytest.fixture( scope='module' )
def check_wcs():
    def wcs_checker( wcs, testdata=None, arcsecprecision=0.01, invabs=0.1 ):
        if testdata is None:
            # This default test data is for ou2024image
            # The hardcoded values are empirical.  I've used DS9 on the test
            # image to verify that they're good to at least ~5 decimal places.
            testdata = [ { 'x': 0, 'y': 0, 'ra': 7.49435552, 'dec': -44.95508301 },
                         { 'x': 4087, 'y': 4087, 'ra': 7.58168925, 'dec': -44.79212825 },
                         { 'x': 0, 'y': 4087, 'ra': 7.42167102, 'dec': -44.84398918   },
                         { 'x': 4087, 'y': 0, 'ra': 7.65461745, 'dec': -44.90311993 },
                         { 'x': 2043.5, 'y': 2043.5, 'ra': 7.53808422, 'dec': -44.87361374 } ]

        for data in testdata:
            ra, dec = wcs.pixel_to_world( data['x'], data['y'] )
            assert isinstance( ra, float )
            assert isinstance( dec, float )
            assert ra == pytest.approx( data['ra'], abs=arcsecprecision/3600./np.cos(data['dec'] * np.pi/180.))
            assert dec == pytest.approx( data['dec'], abs=arcsecprecision/3600. )

            # ...I would have expected better than the default of 0.1
            # pixels, but empirically the WCS as compared to the inverse
            # WCS are only good to several hundreths of a pixel.
            x, y = wcs.world_to_pixel( data['ra'], data['dec'] )
            assert isinstance( x, float )
            assert isinstance( y, float )
            assert x == pytest.approx( data['x'], abs=invabs )
            assert y == pytest.approx( data['y'], abs=invabs )

        xvals = np.array( [ t['x'] for t in testdata ] )
        yvals = np.array( [ t['y'] for t in testdata ] )
        ravals = np.array( [ t['ra'] for t in testdata ] )
        decvals = np.array( [ t['dec'] for t in testdata ] )

        ras, decs = wcs.pixel_to_world( xvals, yvals )
        assert isinstance( ras, np.ndarray )
        assert isinstance( decs, np.ndarray )
        assert np.all( ras == pytest.approx(ravals, abs=arcsecprecision/3600./np.cos(decs[0] * np.pi/180.) ) )
        assert np.all( decs == pytest.approx(decvals, abs=arcsecprecision/3600. ) )

        xs, ys = wcs.world_to_pixel( ravals, decvals )
        assert isinstance( xs, np.ndarray )
        assert isinstance( ys, np.ndarray )
        assert np.all( xs == pytest.approx( xvals, abs=0.1 ) )
        assert np.all( ys == pytest.approx( yvals, abs=0.1 ) )

    return wcs_checker


@pytest.fixture( scope="module" )
def loaded_ou2024_test_diaobjects():
    prov = None
    try:
        with DBCon() as dbcon:
            # Load up the necessary provenance

            prov = Provenance( 'import_ou2024_diaobjects', 0, 1 )
            import pdb; pdb.set_trace()
            rows, cols = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': prov.id } )
            if len(rows) == 0:
                dbcon.execute( "INSERT INTO provenance(id,process,major,minor,params) "
                               "VALUES (%(id)s,%(proc)s,%(maj)s,%(min)s,%(params)s)",
                               { 'id': prov.id, 'proc': prov.process, 'maj': prov.major, 'min': prov.minor,
                                 'params': psycopg.types.json.Jsonb({}) } )
            rows, cols = dbcon.execute( "SELECT tag,process,provenance_id FROM provenance_tag "
                                        "WHERE tag=%(tag)s AND process=%(proc)s",
                                        { 'tag': 'dbou2024_test', 'proc': prov.process } )
            if len(rows) > 1:
                raise RuntimeError( "This should never happen." )
            elif len(rows) == 1:
                if rows[0][2] != prov.id:
                    raise ValueError( f"Provenance tag dbou2024_test process {prov.process} is in the database with "
                                      f"provenance{rows[0][2]}, but we wanted {prov.id}" )
            else:
                dbcon.execute( "INSERT INTO provenance_tag(tag,process,provenance_id) VALUES (%(tag)s,%(proc)s,%(id)s)",
                               { 'tag': 'dbou2024_test', 'proc': 'import_ou2024_diaobjects', 'id': prov.id } )
            dbcon.commit()

            # Load whatever parquet files are in the ou2024 truth direictory of photometry_test_data

            pqdir = pathlib.Path( "/photometry_test_data/ou2024/snana_truth" )
            pqfiles = pqdir.glob( "snana*.parquet" )
            for pqf in pqfiles:
                load_snana_ou2024_diaobject( prov.id, pqf, dbcon=dbcon )

        yield True

    finally:
        with DBCon() as dbcon:
            if prov is not None:
                dbcon.execute( "DELETE FROM diaobject WHERE provenance_id=%(id)s", { 'id': prov.id } )
            dbcon.execute( "DELETE FROM provenance_tag WHERE tag='dbou2024_test'" )
            dbcon.execute( "DELETE FROM provenance WHERE process='import_ou2024_diaobjects'" )
            dbcon.commit()


@pytest.fixture( scope='session' )
def dbuser():
    # Creates a test user with password 'test_password'

    try:
        with DBCon() as dbcon:
            dbcon.execute( "INSERT INTO authuser(id, username, displayname, email, pubkey, privkey) "
                           "VALUES (%(id)s, %(user)s, %(dname)s, %(email)s, %(pub)s, %(priv)s)",
                           { 'id': '788e391e-ca63-4057-8788-25cc8647e722',
                             'user': 'test',
                             'dname': 'test user',
                             'email': 'test@nowhere.org',
                             'pub': """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA1QLihZJ78NHKppUBUaZI
sel7WFKp/3Pr14nbel+BpfOVWrIIIiMegQSAliWRszNLQezKwHTXM4DUxZu7LG/q
zut37v5WSVWCK8wSW+zy6e9vnuVkcrzdEJgkztUaiC8lMnHVE0ycpLTICcAu0wtv
WP32ScyNbiHidyPZwNd9XB4juLl9j7K6hs7WQwmeMOyw8dUZuE8b/jiHrAxxnHjE
Sli8bjR7I6X3AX8U81bP4qFjTjGuy85dIeZEbyS6UpbmkZ+imr/0wLa9knRoW0hU
Uz8p+P/Vts3rimpQtPajtRzCpTY4lRfh05YDmr2rc1WHJ/IPu3v7sIUg8K/egoPJ
VU3c2QYGpwmpnldbb+bpSUXxpsQVtFw5pHmqEbfKXWNM8CTkii8s6bI03/JQREBU
L3OzCGclvS8lQ+ZXAQaMyjshMqMFud3E9RS5EFxpSfk92r+RY7PgaYs9PX7x33zU
k/937nk7sTR5OEKFgxRDx61svk5UJIPQib5SnIDRNAqeKhxg23q5ZqDMBVk1rAhI
xFuX4Hj8VtG89J3DSVJue4psF0wTYceUhUleJCG3gPxAyE2g4ObZZ9mh/gI1KG6v
Np9CFWk9eMSeehEI1YKyPY8Hdv50PmIvN2zgxbo2wccspwCVTrtdKoQebpVAAu3v
tyOci9saPPfI1bNnKD202zsCAwEAAQ==
-----END PUBLIC KEY-----
""",
                             'priv': simplejson.dumps(
                                 {"iv": "z84DFtRURdKFhn3b",
                                  "salt": "57B2Nq/ZToHhVM+1DEq30g==",
                                  "privkey": "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"} # noqa: E501
                             )
                            }
                          )

            dbcon.commit()

        yield True

    finally:
        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM authuser WHERE username='test'" )
            dbcon.commit()


@pytest.fixture( scope="session" )
def dbclient( dbuser ):
    return SNPITDBClient( verify=False, retries=1 )


@pytest.fixture( scope="module" )
def stupid_provenance():
    try:
        with DBCon() as con:
            provid = uuid.uuid4()
            con.execute_nofetch( "INSERT INTO provenance(id,environment,env_major,env_minor,"
                                 "process,major,minor) VALUES (%(provid)s,0,0,0,'foo',0,0)",
                                 { 'provid': provid } )
            con.commit()
            yield provid
    finally:
        with DBCon() as con:
            con.execute_nofetch( "DELETE FROM provenance WHERE id=%(id)s", { 'id': provid } )
            con.commit()



@pytest.fixture( scope="module" )
def stupid_object( stupid_provenance ):
    try:
        objid = uuid.uuid4()
        with DBCon() as con:
            con.execute_nofetch( "INSERT INTO diaobject(id,provenance_id,name,iauname) "
                                 "VALUES(%(id)s,%(provid)s,'foo','SN2025foo')",
                                 { 'id': objid, 'provid': stupid_provenance } )
            con.commit()
        yield objid
    finally:
        with DBCon() as con:
            con.execute_nofetch( "DELETE FROM diaobject WHERE id=%(id)s", { 'id': objid } )
            con.commit()
