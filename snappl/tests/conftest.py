import pytest
import uuid
import pathlib
import subprocess

import simplejson
import numpy as np
import psycopg.types

from astropy.io import fits

import tox # noqa: F401
from tox.pytest import init_fixture # noqa: F401

from snappl.imagecollection import ImageCollection
from snappl.image import FITSImage, FITSImageStdHeaders, RomanDatamodelImage
from snappl.image_simulator import ImageSimulator
from snappl.diaobject import DiaObject
from snappl.lightcurve import Lightcurve
from snappl.segmap import SegmentationMap
from snappl.admin.load_snana_ou2024_diaobject import load_snana_ou2024_diaobject
from snappl.admin.load_ou2024_l2images import OU2024_L2image_loader
from snappl.config import Config
from snappl.dbclient import SNPITDBClient
from snappl.provenance import Provenance
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


def make_provenance_and_tag( process, major, minor, params={}, tag=None, dbcon=None ):
    with DBCon( dbcon ) as dbcon:
        prov = Provenance( process, major, minor, params=params )
        rows, _cols = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': prov.id } )
        if len(rows) == 0:
            dbcon.execute( "INSERT INTO provenance(id,process,major,minor,params) "
                           "VALUES (%(id)s,%(proc)s,%(maj)s,%(min)s,%(params)s)",
                           { 'id': prov.id, 'proc': prov.process, 'maj': prov.major, 'min': prov.minor,
                             'params': psycopg.types.json.Jsonb(prov.params) } )

        if tag is not None:
            rows, _cols = dbcon.execute( "SELECT tag,process,provenance_id FROM provenance_tag "
                                         "WHERE tag=%(tag)s AND process=%(proc)s",
                                         { 'tag': tag, 'proc': prov.process } )
            if len(rows) > 1:
                raise RuntimeError( "This should never happen." )
            elif len(rows) == 1:
                if rows[0][2] != prov.id:
                    raise ValueError( f"Provenance tag {tag} process {prov.process} is in the database with "
                                      f"provenance{rows[0][2]}, but we wanted {prov.id}" )
            else:
                dbcon.execute( "INSERT INTO provenance_tag(tag,process,provenance_id) VALUES (%(tag)s,%(proc)s,%(id)s)",
                               { 'tag': tag, 'proc': prov.process, 'id': prov.id } )
        dbcon.commit()

        return prov


@pytest.fixture( scope="session" )
def test_object_provenance():
    return make_provenance_and_tag( "test_diaobject", 0, 1, tag="test_diaobject_tag" )


@pytest.fixture( scope="module" )
def loaded_ou2024_test_diaobjects():
    prov = None
    posprov= None
    try:
        with DBCon() as dbcon:
            prov = make_provenance_and_tag( 'import_ou2024_diaobjects', 0, 1, tag='dbou2024_test', dbcon=dbcon )

            # Load whatever parquet files are in the ou2024 truth direictory of photometry_test_data
            pqdir = pathlib.Path( "/photometry_test_data/ou2024/snana_truth" )
            pqfiles = pqdir.glob( "snana*.parquet" )
            for pqf in pqfiles:
                load_snana_ou2024_diaobject( prov.id, pqf, dbcon=dbcon )

            posprov = make_provenance_and_tag( 'ou2024_diaobjects_truth_copy', 0, 1, tag='dbou2024_test', dbcon=dbcon )
            dbcon.execute( "INSERT INTO diaobject_position(id, diaobject_id, provenance_id, ra, dec) "
                           "SELECT gen_random_uuid(), o.id, %(provid)s, o.ra, o.dec FROM diaobject o "
                           "WHERE o.provenance_id=%(objprovid)s",
                           { 'provid': posprov.id, 'objprovid': prov.id } )
            dbcon.commit()

        yield True

    finally:
        with DBCon() as dbcon:
            if posprov is not None:
                dbcon.execute( "DELETE FROM diaobject_position WHERE provenance_id=%(id)s", { 'id': posprov.id } )
            if prov is not None:
                dbcon.execute( "DELETE FROM diaobject WHERE provenance_id=%(id)s", { 'id': prov.id } )
            dbcon.execute( "DELETE FROM provenance_tag WHERE tag='dbou2024_test'" )
            dbcon.execute( "DELETE FROM provenance WHERE process='import_ou2024_diaobjects'" )
            dbcon.execute( "DELETE FROM provenance WHERE process='ou2024_diaobjects_truth_copy'" )
            dbcon.commit()


@pytest.fixture( scope="module" )
def loaded_ou2024_test_l2images():
    prov = None
    try:
        with DBCon() as dbcon:
            prov = make_provenance_and_tag( 'import_ou2024_l2images', 0, 1, params={ 'image_class': 'ou2024' },
                                            tag='dbou2024_test', dbcon=dbcon )
            base_path = pathlib.Path( Config.get().value( 'system.ou24.images' ) )
            loader = OU2024_L2image_loader( prov.id, base_path )
            loader( nprocs=4 )

        yield True

    finally:
        if prov is not None:
            with DBCon() as dbcon:
                dbcon.execute( "DELETE FROM l2image WHERE provenance_id=%(id)s", { 'id': prov.id } )
                dbcon.execute( "DELETE FROM provenance_tag WHERE provenance_id=%(id)s", { 'id': prov.id } )
                dbcon.execute( "DELETE FROM provenance WHERE id=%(id)s", { 'id': prov.id } )
                dbcon.commit()


# IMPORTANT : if you use this fixture, use it *before* loaded_ou2024_test_l2images
#   Otherwise, there will be databsae conflicts.  (This fixture should
#   ideally only be used in
#   test_dbimagecollection.py::test_load_ou2024_l2images_1proc ;
#   otherwise, just use the loaded_ou2024_test_l2images )
@pytest.fixture
def loaded_ou2024_test_l2images_1proc():
    prov = None
    try:
        with DBCon() as dbcon:
            prov = make_provenance_and_tag( 'import_ou2024_l2images_1proc', 0, 1, params={ 'image_class': 'ou2024' },
                                            tag='dbou2024_test', dbcon=dbcon )
            base_path = pathlib.Path( Config.get().value( 'system.ou24.images' ) )
            loader = OU2024_L2image_loader( prov.id, base_path )
            loader( nprocs=1 )

        yield True

    finally:
        if prov is not None:
            with DBCon() as dbcon:
                dbcon.execute( "DELETE FROM l2image WHERE provenance_id=%(id)s", { 'id': prov.id } )
                dbcon.execute( "DELETE FROM provenance_tag WHERE provenance_id=%(id)s", { 'id': prov.id } )
                dbcon.execute( "DELETE FROM provenance WHERE id=%(id)s", { 'id': prov.id } )
                dbcon.commit()


@pytest.fixture( scope="module" )
def ou2024_test_lightcurve( loaded_ou2024_test_diaobjects, loaded_ou2024_test_l2images, dbclient ):
    try:
        dobj = DiaObject.find_objects( provenance_tag='dbou2024_test', process='import_ou2024_diaobjects',
                                       name='20172782', dbclient=dbclient )
        dobj = dobj[0]
        imcol = ImageCollection.get_collection( provenance_tag='dbou2024_test', process='import_ou2024_l2images',
                                                dbclient=dbclient )
        images = imcol.find_images( ra=dobj.ra, dec=dobj.dec, order_by='mjd', dbclient=dbclient )
        bands = set( i.band for i in images )
        if len(bands) != 1:
            raise RuntimeError( "I am surprised, there are multiple bands of test images." )

        prov = make_provenance_and_tag( 'ou2024_test_lightcurve', 0, 1, tag='dbou2024_test' )

        # The fluxes aren't going to be right because we don't have the machinery to do
        #   differnce imaging and measurement, so just making stuff up here.
        # Making some other stuff up too.
        data = { 'mjd': [ i.mjd for i in images ],
                 'flux': [ 0., 0., 5., 30., 50., 40., 20., 10. ],
                 'flux_err': [ 0.1 ] * 8,
                 'zpt': [ i.zeropoint for i in images ],
                 'NEA': [ 5. ] * 8,
                 'sky_rms': [ 10. ] * 8,
                 'pointing': [ i.pointing for i in images ],
                 'sca': [ i.sca for i in images ],
                 'pix_x': [ 128. ] * 8,
                 'pix_y': [ 128. ] * 8
                }
        meta = { 'provenance_id': prov.id,
                 'diaobject_id': dobj.id,
                 'diaobject_position_id': None,
                 'iau_name': None,
                 'band': images[0].band,
                 'ra': dobj.ra,
                 'dec': dobj.dec,
                 'ra_err': None,
                 'dec_err': None,
                 'ra_dec_covar': None,
                 f'local_surface_brightness_{images[0].band}': 1.
                }

        ltcv = Lightcurve( data=data, meta=meta )

        yield ltcv

    finally:
        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM provenance_tag "
                           "WHERE tag='dbou2024_test' AND process='ou2024_test_lightcurve'" )
            dbcon.execute( "DELETE FROM provenance WHERE process='ou2024_test_lightcurve'" )
            dbcon.commit()


@pytest.fixture( scope="module" )
def ou2024_test_lightcurve_saved( ou2024_test_lightcurve, dbclient ):
    try:
        ou2024_test_lightcurve.write()
        ou2024_test_lightcurve.save_to_db( dbclient=dbclient )

        yield ou2024_test_lightcurve

    finally:
        ( ou2024_test_lightcurve.base_dir / ou2024_test_lightcurve.filepath ).unlink( missing_ok=True )
        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM lightcurve WHERE id=%(id)s", { 'id': ou2024_test_lightcurve.id } )
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


@pytest.fixture( scope="module" )
def sim_image_and_segmap( stupid_provenance, dbclient ):
    base_image_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
    base_segmap_path = pathlib.Path( Config.get().value( 'system.paths.segmaps' ) )
    imageid = uuid.uuid4()
    segmapid = uuid.uuid4()

    fnamebase = 'sim_image_and_segmap'
    fname = f'{fnamebase}_60030.0'
    fullbase = base_image_path / fname
    fullbase.parent.mkdir( parents=True, exist_ok=True )
    base_segmap_path.mkdir( parents=True, exist_ok=True )
    segmappath = f'{fname}_segmap.fits'
    fullsegmappath = base_segmap_path / segmappath

    try:
        kwargs = {
            "seed": 64738,
            "star_center": (120.0, -13.0),
            "star_sky_radius": 20.,
            "alpha": 1.0,
            "nstars": 50,
            "psf_class": "gaussian",
            "psf_kwargs": ["sigmax=1.0", "sigmay=1.0", "theta=0."],
            "basename": str( base_image_path / fnamebase ),
            "width": 256,
            "height": 256,
            "pixscale": 0.11,
            "mjds": [60030.0],
            "image_centers": [120.0, -13.0],
            "image_rotations": [0.0],
            "zeropoints": [33.0],
            "sky_noise_rms": [100.0],
            "sky_level": [0.0],
            "transient_peak_mag": 21.0,
            "transient_peak_mjd": 60030.0,
            "transient_start_mjd": 60010.0,
            "transient_end_mjd": 60060.0,
            "transient_ra": 120.0,
            "transient_dec": -13.0,
            "numprocs": 1,
        }
        sim = ImageSimulator( **kwargs )
        sim()

        image = FITSImageStdHeaders( base_image_path / fname, std_imagenames=True )

        wcs = image.get_wcs()
        ra00, dec00 = wcs.pixel_to_world( 0, 0 )
        ra10, dec10 = wcs.pixel_to_world( 255, 0 )
        ra01, dec01 = wcs.pixel_to_world( 0, 255 )
        ra11, dec11 = wcs.pixel_to_world( 255, 0 )

        with DBCon() as dbcon:
            dbcon.execute( "INSERT INTO l2image(id,provenance_id, pointing, sca, band, ra, dec, "
                           "  ra_corner_00, ra_corner_01, ra_corner_10, ra_corner_11, "
                           "  dec_corner_00, dec_corner_01, dec_corner_10, dec_corner_11, "
                           "  filepath, width, height, format, mjd, exptime) "
                           "VALUES(%(id)s, %(provid)s, %(point)s, %(sca)s, %(band)s, %(ra)s, %(dec)s, "
                           "       %(ra00)s, %(ra01)s, %(ra10)s, %(ra11)s, %(dec00)s, %(dec01)s, %(dec10)s, %(dec11)s, "
                           "       %(path)s, %(w)s, %(h)s, %(format)s, %(mjd)s, %(texp)s)",
                           { 'id': imageid,
                             'provid': stupid_provenance,
                             'point': 0,
                             'sca': 1,
                             'band': 'R062',
                             'ra': 120.,
                             'dec': -13.,
                             'ra00': ra00,
                             'ra01': ra01,
                             'ra10': ra10,
                             'ra11': ra11,
                             'dec00': dec00,
                             'dec01': dec01,
                             'dec10': dec10,
                             'dec11': dec11,
                             'path': str( fname ),
                             'w': 256,
                             'h': 256,
                             'format': 1,
                             'mjd': 60030.,
                             'texp': 60.
                            } )
            dbcon.commit()

        args = [ 'sextractor', f'{fullbase}_image.fits',
                 '-WEIGHT_TYPE', 'MAP_RMS',
                 '-WEIGHT_IMAGE', f'{fullbase}_noise.fits',
                 '-RESCALE_WEIGHTS', 'N',
                 '-WEIGHT_GAIN', 'N',
                 '-GAIN', '1.0',
                 '-PIXEL_SCALE', '0.0',
                 '-SEEING_FWHM', '2.35',
                 '-CATALOG_NAME', '/tmp/cat',
                 '-BACK_TYPE', 'MANUAL',
                 '-BACK_VALUE', '0.0',
                 '-CHECKIMAGE_TYPE', 'SEGMENTATION',
                 '-CHECKIMAGE_NAME', str( fullsegmappath ),
                 '-PARAMETERS_NAME', '/home/snappl/snappl/tests/default.param',
                 '-FILTER', 'Y',
                 '-FILTER_NAME', '/usr/share/source-extractor/default.conv',
                 '-STARNNW_NAME', '/usr/share/source-extractor/default.nnw'
                ]
        res = subprocess.run( args, capture_output=True )
        if res.returncode:
            raise RuntimeError( res.stderr.decode("utf-8") )

        segmap = SegmentationMap( id=segmapid, provenance_id=stupid_provenance, format=2,
                                  filepath=segmappath, l2image_id=imageid )
        segmap.save_to_db( dbclient=dbclient )

        yield image, segmap

    finally:
        for which in [ 'image', 'noise', 'flags', 'segmap' ]:
            ( base_image_path / f'{fname}_{which}.fits' ).unlink( missing_ok=True )
        pathlib.Path( '/tmp/cat' ).unlink( missing_ok=True )

        with DBCon() as dbcon:
            dbcon.execute( "DELETE FROM segmap WHERE id=%(id)s", { 'id': segmapid } )
            dbcon.execute( "DELETE FROM l2image WHERE id=%(id)s", { 'id': imageid } )
            dbcon.commit()
