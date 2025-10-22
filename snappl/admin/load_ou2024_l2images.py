import uuid
import pathlib
import multiprocessing
import functools

import psycopg

from snappl.image import OpenUniverse2024FITSImage
from snappl.logger import SNLogger
from snappl.utils import asUUID
from snappl.provenance import Provenance
import snappl.db.db


# python multiprocesing irritates me; it seems you can't
#   send a class method as the function
def parse_fits_file( relpath, base_path=None, provid=None ):
    base_path = pathlib.Path( base_path )
    provid = asUUID( provid )
    # import random
    # import remote_pdb;
    # remote_pdb.RemotePdb( '127.0.0.1', random.randint( 4000, 5000 ) ).set_trace()
    image = OpenUniverse2024FITSImage( path=base_path / relpath )
    header = image.get_fits_header()
    wcs = image.get_wcs()

    width = int( header['NAXIS2'] )
    height = int( header['NAXIS1'] )
    ra, dec = wcs.pixel_to_world( width / 2., height / 2. )
    ra_corner_00, dec_corner_00 = wcs.pixel_to_world( 0., 0. )
    ra_corner_10, dec_corner_10 = wcs.pixel_to_world( width-1, 0. )
    ra_corner_01, dec_corner_01 = wcs.pixel_to_world( 0., height-1 )
    ra_corner_11, dec_corner_11 = wcs.pixel_to_world( width-1, height-1 )
    exptime = float( header['EXPTIME'] )

    params = { 'id': uuid.uuid4(),
               'provenance_id': provid,
               'pointing': image.pointing,
               'sca': image.sca,
               'filter': image.band,
               'ra': ra,
               'dec': dec,
               'ra_corner_00': ra_corner_00,
               'ra_corner_01': ra_corner_01,
               'ra_corner_10': ra_corner_10,
               'ra_corner_11': ra_corner_11,
               'dec_corner_00': dec_corner_00,
               'dec_corner_01': dec_corner_01,
               'dec_corner_10': dec_corner_10,
               'dec_corner_11': dec_corner_11,
               'filepath': str( relpath ),
               'width': width,
               'height': height,
               'format': 1,
               'mjd_start': image.mjd,
               'exptime': exptime,
               'properties': psycopg.types.json.Jsonb( {} )
              }
    return params


class OU2024_L2image_loader:
    def __init__( self, provid, base_path ):
        self.provid = provid.id if isinstance( provid, Provenance ) else provid
        self.base_path = pathlib.Path( base_path )
        self.dbcon = None


    def collect_ou2024_l2image_paths( self, relpath ):
        subdirs = []
        imagefiles = []

        for fullpath in ( self.base_path / relpath ).iterdir():
            fullpath = fullpath.resolve()
            if fullpath.is_dir():
                subdirs.append( fullpath.relative_to( self.base_path ) )
            elif ( fullpath.name[-5:] == '.fits' ) or ( fullpath.name[-8:] == '.fits.gz' ):
                imagefiles.append( fullpath.relative_to( self.base_path ) )

        for subdir in subdirs:
            imagefiles.extend( self.collect_ou2024_l2image_paths(subdir) )

        return imagefiles


    def save_to_db( self ):
        if len( self.copydata ) > 0:
            SNLogger.info( f"Loading {len(self.copydata)} images to database..." )
            snappl.db.db.L2Image.bulk_insert_or_upsert( self.copydata, dbcon=self.dbcon )
            self.totloaded += len( self.copydata )
            self.copydata = []

    def append_to_copydata( self, relpath ):
        self.copydata.append( relpath )
        if len(self.copydata) % self.loadevery == 0:
            self.save_to_db()

    def omg( self, e ):
        self.errors.append( e )

    def __call__( self, dbcon=None, loadevery=1000, nprocs=1 ):
        toload = self.collect_ou2024_l2image_paths( '.' )
        self.totloaded = 0
        self.copydata = []
        self.loadevery = loadevery
        self.errors = []

        SNLogger.info( f"Loading {len(toload)} files in {nprocs} processes...." )
        do_parse_fits_file = functools.partial( parse_fits_file,
                                                base_path=self.base_path,
                                                provid=self.provid )

        with snappl.db.db.DBCon( dbcon ) as self.dbcon:
            if nprocs > 1:
                with multiprocessing.Pool( nprocs ) as pool:
                    for path in toload:
                        pool.apply_async( do_parse_fits_file,
                                          args=[ str(path) ],
                                          callback=self.append_to_copydata,
                                          error_callback=self.omg
                                         )
                    pool.close()
                    pool.join()
                if len( self.errors ) > 0:
                    nl = "\n"
                    SNLogger.error( f"Got errors loading FITS files:\n{nl.join(str(e) for e in self.errors)}" )
                    raise RuntimeError( "Massive failure." )

            elif nprocs == 1:
                for path in toload:
                    self.append_to_copydata( do_parse_fits_file( path ) )

            else:
                raise ValueError( "Dude, nprocs needs to be positive, not {nprocs}" )

            # Get any residual ones that didn't pass the "send to db" threshold
            self.save_to_db()

            SNLogger.info( f"Loaded {self.totloaded} of {len(toload)} images to database." )

        self.dbcon = None
