import pytest
import pathlib
import numbers

import numpy as np
import astropy
import astropy.io.fits
import fitsio.header

import snappl.db.db
from snappl.image import Image, FITSImage
from snappl.wcs import AstropyWCS, GalsimWCS
from snappl.psf import PSF
from snappl.provenance import Provenance
from snappl.config import Config


# ======================================================================
# Image tests

def test_position_angle( ou2024image_module ):
    # Really, this is testing that the position_angle code gives
    # the same answer as the formula Russel harvested from some
    # IDL code.
    hdr = ou2024image_module.get_fits_header()
    det = hdr['CD1_1'] * hdr['CD2_2'] - hdr['CD1_2'] * hdr['CD2_1']
    sgn = -1 if det < 0 else 1
    ang1 = np.arctan2( sgn * hdr['CD1_2'], sgn * hdr['CD1_1'] ) * 180. / np.pi
    ang2 = np.arctan2( -hdr['CD2_1'], hdr['CD2_2'] ) * 180. / np.pi
    assert ang1 == pytest.approx( ang2, abs=0.75 )
    compang = ( ang1 + ang2 ) / 2.
    assert ou2024image_module.position_angle == pytest.approx( compang, abs=0.01 )


def test_get_and_find_image( loaded_ou2024_test_l2images, dbclient ):
    prov = Provenance.get_provs_for_tag( 'dbou2024_test', process='import_ou2024_l2images' )
    with snappl.db.db.DBCon( dictcursor=True ) as dbcon:
        images = dbcon.execute( "SELECT * FROM l2image WHERE provenance_id=%(provid)s", {'provid': prov.id} )

    def check_image( image, imagedict ):
        # Make sure the properties got loaded from the database
        # (This is why we are checking the underscore properties,
        # so the lazy-loading won't get hit.)
        # (sky_level and zeropoint aren't in the database, so don't check those.)
        assert image.id == imagedict['id']
        assert image.full_filepath == ( pathlib.Path( Config.get().value( 'system.ou24.images' ) )
                                        / imagedict['filepath'] )
        for prop in ( 'width', 'height', 'pointing', 'sca', 'ra', 'dec',
                      'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                      'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                      'band', 'mjd', 'position_angle', 'exptime' ):
            if isinstance( imagedict[prop], numbers.Real ) and not isinstance( imagedict[prop], numbers.Integral ):
                assert getattr( image, f'_{prop}' ) == pytest.approx( imagedict[prop], rel=1e-7 )
                assert getattr( image, prop ) == pytest.approx( imagedict[prop], rel=1e-7 )
            else:
                assert getattr( image, f'_{prop}' ) == imagedict[prop]
                assert getattr( image, prop ) == imagedict[prop]

    im = Image.get_image( images[0]['id'] )
    check_image( im, images[0] )

    # Try a bunch of find images combinations

    for provargs in [ { 'provenance': images[0]['provenance_id'] },
                      { 'provenance_tag': 'dbou2024_test', 'process': 'import_ou2024_l2images' } ]:
        ims = Image.find_images( pointing=38645, sca=15, **provargs )
        assert len(ims) == 1
        ims = Image.find_images( pointing=38645, sca=15, band='Y106', **provargs )
        assert len(ims) == 1
        ims = Image.find_images( pointing=38645, sca=15, band='R062', **provargs )
        assert len(ims) == 0
        ims = Image.find_images( band='Y106', **provargs )
        assert len(ims) == 8

        ims = Image.find_images( ra=7.5, dec=-44.92, **provargs )
        assert len(ims) == 1
        assert ims[0].pointing == 13205
        assert ims[0].sca == 1
        ims = Image.find_images( ra=7.50, dec=-44.75, **provargs )
        assert len(ims) == 4
        ims = Image.find_images( ra=7.55, dec=-44.81, **provargs )
        assert len(ims) == 8

        ims = Image.find_images( ra_min=7.52, **provargs )
        assert len(ims) == 5
        assert all( i.ra >= 7.52 for i in ims )
        ims = Image.find_images( ra_min=7.52, ra_max=7.54, **provargs )
        assert len(ims) == 3
        assert all( i.ra >= 7.52 for i in ims )
        assert all( i.ra <= 7.54 for i in ims )
        ims = Image.find_images( ra_min=7.52, ra_max=7.54, dec_min=-44.85, dec_max=-44.8, **provargs )
        assert len(ims) == 1
        assert ims[0].pointing == 19009

        ims = Image.find_images( mjd_min=62450., mjd_max=62470., **provargs )
        assert len(ims) == 2
        assert all( i.mjd >= 62450. and i.mjd <= 62470. for i in ims )

        ims = Image.find_images( position_angle_min=20., position_angle_max=120., **provargs )
        assert len(ims) == 3
        assert all( i.position_angle >= 20. and i.position_angle <= 120. for i in ims )

        # Look at order_by, limit, and offset
        ims = Image.find_images( order_by='mjd', **provargs )
        assert len(ims) == 8
        mjds = [ i.mjd for i in ims ]
        mjds.sort()
        assert mjds == [ i.mjd for i in ims ]
        pas = [ i.position_angle for i in ims ]
        pas.sort()
        assert pas != [ i.position_angle for i in ims ]
        ims = Image.find_images( order_by='position_angle', **provargs )
        assert len(ims) == 8
        pas = [ i.position_angle for i in ims ]
        pas.sort()
        assert pas == [ i.position_angle for i in ims ]
        ims = Image.find_images( order_by='position_angle', limit=2, **provargs )
        assert len(ims) == 2
        assert pas[0:2] == [ i.position_angle for i in ims ]
        ims = Image.find_images( order_by='position_angle', limit=2, offset=2, **provargs )
        assert len(ims) == 2
        assert pas[2:4] == [ i.position_angle for i in ims ]

    with pytest.raises( ValueError, match=( r'Must specify either provenance, or both of provenance_tag and process; '
                                            r'cannot specify both provenance and provenance_tag' ) ):
        Image.find_images( provenance=images[0]['provenance_id'],
                           provenance_tag='dbou2024_test', process='import_ou2024_l2images' )


# ======================================================================
# FITSImage tests
# Note that some of these tests use the ou2024image fixtures.
#   The reason is that the functions we're testing requires some
#   stuff that isn't defined in FITSImage.  However, all the
#   tests in this section tests the functions which themselves
#   are defined in FITSImage.

def test_fits_fitsio_header_to_astropy_header():
    hdr = fitsio.header.FITSHDR()
    hdr.add_record( fitsio.header.FITSRecord( { 'name': 'TEST1', 'value': 1, 'comment': 'testing 1' } ) )
    hdr.add_record( "TEST2   =                 42.0 / testing 2" )
    hdr.add_record( fitsio.header.FITSRecord( { 'name': 'TEST3', 'value': 'kittens', 'comment': 'testing 3' } ) )
    # hdr.add_record( fitsio.header.FITSRecord( { 'name': 'COMMENT', 'value': 'this is the first comment' } ) )
    # hdr.add_record( fitsio.header.FITSRecord( { 'name': 'COMMENT', 'value': 'this is the second comment' } ) )
    hdr.add_record( 'COMMENT this is the first comment' )
    hdr.add_record( 'COMMENT this is the second comment' )

    ahdr = FITSImage._fitsio_header_to_astropy_header( hdr )

    for i, (kw, val, com, rec) in enumerate( zip( [ 'TEST1', 'TEST2', 'TEST3', 'COMMENT', 'COMMENT' ],
                                                  [ 1, 42.0, 'kittens',
                                                    'this is the first comment', 'this is the second comment'],
                                                  [ 'testing 1', 'testing 2', 'testing 3', '', '' ],
                                                  ahdr ) ):
        assert ahdr[i] == val
        assert ahdr.comments[i] == com
        if kw != 'COMMENT':
            assert ahdr[rec] == val
            assert ahdr.comments[rec] == com


def test_fits_astropy_header_to_fitsio_header():
    ahdr = astropy.io.fits.header.Header()
    ahdr.append( ('TEST1', 1, 'testing 1') )
    ahdr.append( ('TEST2', 42.0, 'testing 2') )
    ahdr.append( ('TEST3', 'kittens', 'testing 3') )
    ahdr.append( ('COMMENT', 'this is the first comment') )
    ahdr.append( ('COMMENT', 'this is the second comment') )

    hdr = FITSImage._astropy_header_to_fitsio_header( ahdr )

    for i, (kw, val, com, rec) in enumerate( zip( [ 'TEST1', 'TEST2', 'TEST3', 'COMMENT', 'COMMENT' ],
                                                  [ 1, 42.0, 'kittens',
                                                    'this is the first comment', 'this is the second comment'],
                                                  [ 'testing 1', 'testing 2', 'testing 3', '', '' ],
                                                  ahdr ) ):
        assert hdr.records()[i]['name'] == kw
        assert hdr.records()[i]['value'] == val
        if 'comment' in hdr.records()[i]:
            assert hdr.records()[i]['comment'] == com
        if kw != 'COMMENT':
            assert hdr[kw] == val


def test_fits_get_wcs( ou2024image, fitsimage_module, check_wcs ):
    assert isinstance( fitsimage_module._wcs, AstropyWCS )
    assert fitsimage_module.get_wcs() is fitsimage_module._wcs
    assert ou2024image._wcs is None
    wcs = ou2024image.get_wcs()
    assert isinstance( wcs, AstropyWCS )
    assert wcs is ou2024image._wcs
    check_wcs( wcs )

    apwcs = ou2024image.get_wcs( wcsclass="AstropyWCS" )
    assert apwcs is wcs
    assert apwcs is ou2024image._wcs

    gswcs = ou2024image.get_wcs( wcsclass="GalsimWCS" )
    assert isinstance( gswcs, GalsimWCS )
    assert gswcs is ou2024image._wcs
    check_wcs( gswcs )

    # Make sure it's not recreated if we get the same class again
    newgswcs = ou2024image.get_wcs( wcsclass="GalsimWCS" )
    assert newgswcs is gswcs
    assert newgswcs is ou2024image._wcs


def test_fits_get_cutout( ou2024image_module ):
    image = ou2024image_module
    assert image.image_shape == ( 4088, 4088 )
    cutout = image.get_cutout( 200, 400, 11 )
    assert isinstance( cutout, FITSImage )
    assert isinstance( cutout._data, np.ndarray )
    assert cutout.image_shape == ( 11, 11 )
    # Remember numpy arrays are indexed y, x
    assert np.all( cutout._data == image._data[ 395:406, 195:206  ] )
    assert np.all( cutout._noise == image._noise[ 395:406, 195:206 ] )
    assert np.all( cutout._flags == image._flags[ 395:406 , 195:206 ] )

    with pytest.raises( astropy.nddata.utils.PartialOverlapError ):
        _ = image.get_cutout( 5, 2048, 21 )

    with pytest.raises( astropy.nddata.utils.PartialOverlapError ):
        _ = image.get_cutout( 2048, 4085, 21 )

    with pytest.raises( astropy.nddata.utils.NoOverlapError ):
        _ = image.get_cutout( 2048, 4200, 21 )

    # Repeat the above but now with mode='partial'
    cutout = image.get_cutout( 5, 2048, 21, mode='partial', fill_value=np.nan )
    np.testing.assert_equal( cutout._data[:, 0:5], np.nan )


    cutout2 = image.get_cutout( 2048, 4085, 21, mode='partial', fill_value=np.nan)
    np.testing.assert_equal( cutout2._data[-8:, :], np.nan )
    with pytest.raises( astropy.nddata.utils.NoOverlapError ):
        _ = image.get_cutout( 2048, 4200, 21, mode='partial', fill_value=np.nan)


def test_fits_get_ra_dec_cutout( ou2024image_module ):
    image = ou2024image_module
    # Choose the ra, dec around the SN in the test images
    ra, dec = 7.551093401915147, -44.80718106491529

    wcs = image.get_wcs()
    x, y = wcs.world_to_pixel( ra, dec )
    x = int( np.floor( x + 0.5 ) )
    y = int( np.floor( y + 0.5 ) )

    cutout = image.get_ra_dec_cutout(ra, dec, 5)
    # assert isinstance( cutout, FITSImage )    # Won't work because we didn't pass a FITSImage...
    assert cutout.image_shape == ( 5, 5 )

    assert np.all( cutout.data == image.data[ y-2:y+3, x-2:x+3 ] )

    # Now we intentionally try to get a no overlap error.
    with pytest.raises(astropy.nddata.utils.NoOverlapError):
        ra, dec = 7.7, -45.0
        cutout = image.get_ra_dec_cutout(ra, dec, 5)

    # Now we intentionally try to get a partial overlap error.
    with pytest.raises(astropy.nddata.utils.PartialOverlapError):
        ra, dec = 7.6186202,-44.8483766
        cutout = image.get_ra_dec_cutout(ra, dec, 55)

    # Now try with mode='partial'
    cutout = image.get_ra_dec_cutout(ra, dec, 55, mode='partial', fill_value=np.nan)
    np.testing.assert_equal(np.sum(np.isnan(cutout.data)), 1485)


# Also incidentally tests Numpy2dImage.free
# TODO : test that loading data loads header
def test_fits_get_data( unloaded_fitsimage ):
    im = unloaded_fitsimage

    assert im._data is None
    assert im._noise is None
    assert im._flags is None

    # Accessing one of data, noise, or flags should only load that one
    assert im.data.shape == ( 1024, 1024 )
    assert im._data.shape == ( 1024, 1024 )
    assert im._noise is None
    assert im._flags is None
    im.free()
    assert im.noise.shape == ( 1024, 1024 )
    assert im._noise.shape == ( 1024, 1024 )
    assert im._data is None
    assert im._flags is None
    im.free()
    assert im.flags.shape == ( 1024, 1024 )
    assert im._flags.shape == ( 1024, 1024 )
    assert im._data is None
    assert im._noise is None

    # Clear
    im.free()
    assert im._data is None
    assert im._noise is None
    assert im._flags is None

    # Try loading without caching
    data, noise, flags = im.get_data()
    assert data.shape == ( 1024, 1024 )
    assert noise.shape == ( 1024, 1024 )
    assert flags.shape == ( 1024, 1024 )
    assert im._data is None
    assert im._noise is None
    assert im._flags is None

    # Try loading with caching
    data, noise, flags = im.get_data( cache=True )
    assert data.shape == ( 1024, 1024 )
    assert noise.shape == ( 1024, 1024 )
    assert flags.shape == ( 1024, 1024 )
    assert im._data is data
    assert im._noise is noise
    assert im._flags is flags

    # Try loading the cached data
    data, = im.get_data( which='data' )
    assert data is im._data
    noise, = im.get_data( which='noise' )
    assert noise is im._noise
    flags, = im.get_data( which='flags' )
    assert flags is im._flags
    data, noise, flags = im.get_data()
    assert im._data is data
    assert im._noise is noise
    assert im._flags is flags

    # Try always reloading
    data, = im.get_data( which='data', always_reload=True )
    assert data is not im._data
    noise, = im.get_data( which='noise', always_reload=True )
    assert noise is not im._noise
    flags, = im.get_data( which='flags', always_reload=True )
    assert flags is not im._flags
    data, noise, flags = im.get_data( always_reload=True )
    assert im._data is not data
    assert im._noise is not noise
    assert im._flags is not flags

    # Always reloading with cache
    origdata = im._data
    orignoise = im._noise
    origflags = im._flags
    data, noise, flags = im.get_data( always_reload=True, cache=True )
    assert data is im._data
    assert data is not origdata
    assert noise is im._noise
    assert noise is not orignoise
    assert flags is im._flags
    assert flags is not origflags


def test_fits_set_data( unloaded_fitsimage ):
    image = unloaded_fitsimage

    origim = image.data
    orignoi = image.noise
    origfl = image.flags
    try:
        image.data = origim + 1
        assert np.all( origim + 1 == image.data )
        image.noise = orignoi + 1
        assert np.all( orignoi + 1 == image.noise )
        image.flags = origfl + 1
        assert np.all( origfl + 1 == image.flags )

        with pytest.raises( TypeError, match="Data must be a 2d numpy array of floats." ):
            image.data = 'cheese'
        with pytest.raises( TypeError, match="Data must be a 2d numpy array of floats." ):
            image.data = origfl
        with pytest.raises( TypeError, match="Data must be a 2d numpy array of floats." ):
            image.data = np.array( [1., 2., 3.] )
        with pytest.raises( TypeError, match="Flags must be a 2d numpy array of integers." ):
            image.flags = origim
        with pytest.raises( TypeError, match="Flags must be a 2d numpy array of integers." ):
            image.flags = np.array( [1, 2, 3] )

    finally:
        # Gotta restore the module-scope fixture's data!
        image._data = origim
        image._noise = orignoi
        image._flags = origfl


def test_fits_std_imagenames( unloaded_fitsimage_basepath ):
    base = unloaded_fitsimage_basepath
    im = FITSImage( base, std_imagenames=True )
    assert isinstance( im.get_fits_header(), astropy.io.fits.header.Header )
    assert im.path == pathlib.Path( f'{base}_image.fits' )
    assert im.noisepath == pathlib.Path( f'{base}_noise.fits' )
    assert im.flagspath == pathlib.Path( f'{base}_flags.fits' )

    assert im.data.shape == (1024, 1024)
    assert im.noise.shape == (1024, 1024)
    assert im.flags.shape == (1024, 1024)

    bpath = 'test_fits_std_imagenames'
    ipath = pathlib.Path( f"{bpath}_image.fits" )
    npath = pathlib.Path( f"{bpath}_noise.fits" )
    fpath = pathlib.Path( f"{bpath}_flags.fits" )
    try:
        assert not ipath.exists()
        assert not npath.exists()
        assert not fpath.exists()

        rng = np.random.default_rng()
        data = np.float32( rng.uniform( size=(256, 256) ) )
        noise = np.float32( rng.uniform( size=(256, 256) ) )
        flags = np.int16( rng.integers( 2, size=(256, 256) ) )
        newim = FITSImage( path='test_fits_std_imagenames', std_imagenames=True,
                           data=data, noise=noise, flags=flags, header=im.get_fits_header() )
        assert newim._data is data
        assert newim._noise is noise
        assert newim._flags is flags

        newim.save()
        assert ipath.is_file()
        assert npath.is_file()
        assert fpath.is_file()

        testim = FITSImage( path=bpath, std_imagenames=True )
        assert np.all( testim.data == data )
        assert np.all( testim.noise == noise )
        assert np.all( testim.flags == flags )

        # Make sure we can't overwrite
        with pytest.raises( RuntimeError, match=( r"FITSImage.save: overwrite is False, but "
                                                  r"image file\(s\) already exist" ) ):
            newim.save()

        # Make sure we can overwrite
        newim._data = data + 1.
        newim._noise = noise + 1.
        newim._flags = flags + 1
        newim.save( overwrite=True )
        testim = FITSImage( path=bpath, std_imagenames=True )
        assert np.allclose( testim.data, data + 1., atol=1e-6 )
        assert np.allclose( testim.noise, noise + 1., atol=1e-6 )
        assert np.all( testim.flags == flags + 1 )

    finally:
        ipath.unlink( missing_ok=True )
        npath.unlink( missing_ok=True )
        fpath.unlink( missing_ok=True )

# TODO : test saving with WCS


# ======================================================================
# ManualFITSImage tests


def test_manual_fits_image( manual_fits_image ):
    assert isinstance( manual_fits_image._data, np.ndarray )
    assert manual_fits_image._data.shape == ( 25, 25 )
    assert manual_fits_image._data.dtype == np.float32
    assert np.all( manual_fits_image._data == 1.0 )
    assert isinstance( manual_fits_image._noise, np.ndarray )
    assert manual_fits_image._noise.shape == ( 25, 25 )
    assert manual_fits_image._noise.dtype == np.float32
    assert np.all( manual_fits_image._noise == 0.0 )
    assert isinstance( manual_fits_image._flags, np.ndarray )
    assert manual_fits_image._flags.shape == ( 25, 25 )
    assert manual_fits_image._flags.dtype == np.uint32
    assert np.all( manual_fits_image._flags == 0 )


    # Test the data setter
    manual_fits_image._data = np.ones((25, 25), dtype=np.float32) * 2.0
    assert np.all( manual_fits_image._data == 2.0 )

    # Test the noise setter
    manual_fits_image._noise = np.ones((25, 25), dtype=np.float32) * 3.0
    assert np.all( manual_fits_image._noise == 3.0 )

    # Test the flags setter
    manual_fits_image._flags = np.zeros((25, 25), dtype=np.uint32) + 1
    assert np.all( manual_fits_image._flags == 1 )

    # Test the header
    hdr = manual_fits_image.get_fits_header()
    assert isinstance(hdr, astropy.io.fits.header.Header)
    assert hdr is manual_fits_image._header


@pytest.mark.xfail( reason="Issue #50" )
def test_ou2024_compare_zeropoints( ou2024image ):
    zp1 = ou2024image._get_zeropoint()
    psf = PSF.get_psf_object( 'A25ePSF', band=ou2024image.band, sca=ou2024image.sca, x=1277.5, y=1277.5 )
    zp2 = ou2024image._get_zeropoint_the_hard_way( psf, ap_r=9 )
    assert zp1 == pytest.approx( zp2, abs=0.01 )


def test_ou2024_compare_zeropoints_with_not_enough_precision( ou2024image ):
    zp1 = ou2024image.zeropoint
    assert zp1 is not None
    psf = PSF.get_psf_object( 'A25ePSF', band=ou2024image.band, sca=ou2024image.sca, x=1277.5, y=1277.5 )
    zp2 = ou2024image._get_zeropoint_the_hard_way( psf, ap_r=9 )
    assert zp1 == pytest.approx( zp2, abs=0.1 )


# ======================================================================
# FITSImageOnDisk tests
#
# TODO

# ======================================================================
# FITSImageStdHeaders tests
#
# TODO

# ======================================================================
# OpenUniverse2024FITSImage tests

def test_ou2024_get_data( ou2024image ):
    try:
        # Notice the types are explicitly called out as big-endian below, even
        #   if the architecture of the system  is little-endian.  This is because
        #   FITS files are defined to be big-endian, and astropy reads them
        #   straight.  (...except that the integer flags don't seem to
        #   be big-endian, so I am confused as to what astropy and/or fitsio
        #   and/or numpy really does.)
        #
        # ... but now that we're using FITSIO, it looks like it byte swaps,
        #   so everything changed below.

        # I choose an area around a nice galaxy to sum
        data, = ou2024image.get_data( 'data' )
        assert isinstance( data, np.ndarray )
        assert data.shape == ( 4088, 4088 )
        # assert data.dtype == ">f8"
        assert data.dtype == np.dtype('float64')
        assert data[2300:2336, 2482:2589].sum() == pytest.approx( 429719.0, rel=1e-5 )

        noise, = ou2024image.get_data( 'noise' )
        assert isinstance( noise, np.ndarray )
        assert noise.shape == ( 4088, 4088 )
        # assert noise.dtype == ">f4"
        assert noise.dtype == np.dtype('float32')
        assert noise[2300:2336, 2482:2589].sum() == pytest.approx( 427641, rel=1e-5 )

        flags, = ou2024image.get_data( 'flags' )
        assert isinstance( flags, np.ndarray )
        assert flags.shape == ( 4088, 4088 )
        assert flags.dtype == "uint32"
        assert flags[2300:2336, 2482:2589].sum() == 0

        assert ou2024image._data is None
        assert ou2024image._noise is None
        assert ou2024image._flags is None

        data2, noise2, flags2 = ou2024image.get_data()
        assert data2 is not data
        assert noise2 is not noise
        assert flags2 is not flags
        assert np.all( data2 == data )
        assert np.all( noise2 == noise )
        assert np.all( flags2 == flags )
        assert ou2024image._data is None
        assert ou2024image._noise is None
        assert ou2024image._flags is None

        props = [ 'data', 'noise', 'flags' ]
        for prop in props:
            res = ou2024image.get_data( prop, cache=True )
            assert isinstance( res, list )
            assert len(res) == 1
            assert isinstance( res[0], np.ndarray )
            assert res[0].shape == ( 4088, 4088 )
            assert res[0] is getattr( ou2024image, f"_{prop}" )
            if prop == 'data':
                assert isinstance( ou2024image._header, astropy.io.fits.header.Header )
            else:
                assert ou2024image._header is None
            for otherprop in props:
                if otherprop == prop:
                    continue
                assert getattr( ou2024image, f"_{otherprop}" ) is None
            setattr( ou2024image, f"_{prop}", None)
            setattr( ou2024image, "_header", None )

        data3, noise3, flags3 = ou2024image.get_data( cache=True )
        assert isinstance( ou2024image._header, astropy.io.fits.header.Header )
        assert np.all( data3 == data )
        assert np.all( noise3 == noise )
        assert np.all( flags3 == flags )
        assert data3 is not data
        assert noise3 is not noise
        assert flags3 is not flags
        assert data3 is ou2024image._data
        assert noise3 is ou2024image._noise
        assert flags3 is ou2024image._flags

        data4, noise4, flags4 = ou2024image.get_data( always_reload=True )
        assert data3 is ou2024image._data
        assert noise3 is ou2024image._noise
        assert flags3 is ou2024image._flags
        assert data4 is not data3
        assert noise4 is not noise3
        assert flags4 is not flags3
        assert np.all( data4 == data )
        assert np.all( noise4 == noise )
        assert np.all( flags4 == flags )
    finally:
        # ...I don't think there's anything needing cleaning up
        # We didn't use the module-scope fixture
        pass


def test_ou2024_properties( ou2024image ):
    im = ou2024image

    assert im.pointing == 13205
    assert im.sca == 1
    assert im.ra == pytest.approx( 7.42991, abs=1e-5 )
    assert im.dec == pytest.approx( -44.8697, abs=1e-5 )
    assert im.ra_corner_00 == pytest.approx( 7.49436, abs=1e-4 )
    assert im.ra_corner_01 == pytest.approx( 7.42167, abs=1e-4 )
    assert im.ra_corner_10 == pytest.approx( 7.65462, abs=1e-4 )
    assert im.ra_corner_11 == pytest.approx( 7.58169, abs=1e-4 )
    assert im.dec_corner_00 == pytest.approx( -44.95508, abs=1e-4 )
    assert im.dec_corner_01 == pytest.approx( -44.84399, abs=1e-4 )
    assert im.dec_corner_10 == pytest.approx( -44.90312, abs=1e-4 )
    assert im.dec_corner_11 == pytest.approx( -44.79213, abs=1e-4 )
    assert im.band == 'Y106'
    assert im.mjd == pytest.approx( 62170.424, abs=1e-3 )
    assert im.position_angle == pytest.approx( -24.75, abs=0.01 )
    assert im.exptime == pytest.approx( 302.275, abs=1e-3 )
    assert im.sky_level == pytest.approx( 112.0, abs=0.1 )
    assert im.zeropoint == pytest.approx( 32.6617, abs=1e-4 )

    # Setting updates properties, but not the header

    im.pointing = 5
    assert im.pointing == 5

    im.sca = 42
    assert im.sca == 42
    assert im.get_fits_header()['SCA_NUM'] == 1

    im.ra = 128.
    assert im.ra == 128.
    assert im.get_fits_header()['RA_TARG'] == pytest.approx( 7.42991, abs=1e-5 )

    im.dec = -13.
    assert im.dec == -13.
    assert im.get_fits_header()['DEC_TARG'] == pytest.approx( -44.8697, abs=1e-5 )

    im.band = 'foo'
    assert im.band == 'foo'
    assert im.get_fits_header()['FILTER'].strip() == 'Y106'
    # Gotta reset it or _get_zeropoint below fails
    im._get_band()

    im.mjd = 60000.
    assert im.mjd == 60000.
    assert im.get_fits_header()['MJD-OBS'] == pytest.approx( 62170.424, abs=1e-3 )

    im.position_angle = 66.
    assert im.position_angle == 66.
    im._get_position_angle()
    assert im.position_angle == pytest.approx( -24.75, abs=0.01 )

    im.exptime = 23.
    assert im.exptime == 23.
    assert im.get_fits_header()['EXPTIME'] == pytest.approx( 302.275, abs=1e-3 )

    im.sky_level = 666.
    assert im.sky_level == 666.
    assert im.get_fits_header()['SKY_MEAN'] == pytest.approx( 112.0, abs=0.1 )

    im.zeropoint = 1.
    assert im.zeropoint == 1.
    im._get_zeropoint()
    assert im.zeropoint == pytest.approx( 32.6617, abs=1e-4 )

    for axis in [ 'ra', 'dec' ]:
        for corner in [ '00', '01', '10', '11' ]:
            orig = getattr( im, f'_{axis}_corner_{corner}' )
            setattr( im, f'{axis}_corner_{corner}', 0. )
            assert getattr( im, f'{axis}_corner_{corner}' ) == 0.
            im._get_corners()
            assert getattr( im, f'{axis}_corner_{corner}' ) == orig


def test_ou2024_get_fits_header( ou2024image, ou2024image_module ):
    assert isinstance( ou2024image_module._header, astropy.io.fits.header.Header )
    assert ou2024image_module._header == ou2024image_module.get_fits_header()
    assert ou2024image._header is None
    hdr = ou2024image.get_fits_header()
    assert isinstance( hdr, astropy.io.fits.header.Header )
    assert hdr is ou2024image._header


# ======================================================================
# RomanDatamodelImage tests

def test_romandatamodel_image( romandatamodel_image ):
    im = romandatamodel_image
    # These tests will fail right now.  We're hoping that
    #  duck typing will be good enough.  If not, uncomment
    #  these tests, and edit RomanDatamodelImage to do something else
    # assert isinstance( im.data, np.ndarray )
    # assert isinstance( im.noise, np.ndarray )
    # assert isinstance( im.flags, np.ndarray )

    assert im.band == 'F106'
    assert im.mjd == pytest.approx( 60627.50030, abs=1e-5 )

    assert im.data.shape == ( 4088, 4088 )
    # Looks like they're coming in little-endian.  (Really maybe native
    # type?  If tests are failing for you on a big-endian machine, then
    # probably replace all the < below with =.)
    assert im.data.dtype == "<f4"

    assert im.noise.shape == im.data.shape
    assert im.noise.dtype == "<f4"

    assert im.flags.shape == im.data.shape
    assert im.flags.dtype == "<u4"

    assert im.data[1896:1932, 3800:3835].sum() == pytest.approx( 1053.467, rel=1e-5 )
    assert im.noise[1896:1932, 3800:3835].sum() == pytest.approx( 210.87682, rel=1e-5 )

    data, noise, flags = im.get_data()
    assert data is not im.data
    assert noise is not im.noise
    assert flags is not im.flags
    assert isinstance( data, np.ndarray )
    np.testing.assert_allclose( data, im.data, rtol=1e-5 )
    np.testing.assert_allclose( noise, im.noise, rtol=1e-5 )
    assert np.all( flags == im.flags )

    props = [ 'data', 'noise', 'flags' ]
    for prop in props:
        res = im.get_data( prop )[0]
        assert res is not getattr( im, prop )
        assert isinstance( res, np.ndarray )
        if prop == 'flags':
            assert np.all( res == im.flags )
        else:
            np.testing.assert_allclose( res, getattr(im, prop), rtol=1e-5 )
