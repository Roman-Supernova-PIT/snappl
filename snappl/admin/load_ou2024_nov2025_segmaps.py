import re
import uuid
import pathlib
import multiprocessing
import functools
import argparse

from snappl.image import FITSImage
from snappl.logger import SNLogger
from snappl.utils import asUUID
from snappl.provenance import Provenance
import snappl.db.db


# python multiprocesing irritates me; it seems you can't
#   send a class method as the function
def _parse_fits_file( relpath, base_path=None, provid=None ):
    relpath = pathlib.Path( relpath )
    base_path = pathlib.Path( base_path )
    provid = asUUID( provid )
    # import random
    # import remote_pdb;
    # remote_pdb.RemotePdb( '127.0.0.1', random.randint( 4000, 5000 ) ).set_trace()
    image = FITSImage( path=base_path / relpath )
    header = image.get_fits_header()
    wcs = image.get_wcs()

    width = int( header['NAXIS2'] )
    height = int( header['NAXIS1'] )
    ra, dec = wcs.pixel_to_world( width / 2., height / 2. )
    ra_corner_00, dec_corner_00 = wcs.pixel_to_world( 0., 0. )
    ra_corner_10, dec_corner_10 = wcs.pixel_to_world( width-1, 0. )
    ra_corner_01, dec_corner_01 = wcs.pixel_to_world( 0., height-1 )
    ra_corner_11, dec_corner_11 = wcs.pixel_to_world( width-1, height-1 )

    sca = int( header['SCA_NUM'] )
    band = header['FILTER'].strip()
    # rage alert.  pointing not in header.  Have to parse filename for
    #   pointing
    match = re.search( r'^[^_]+_(\d+)_\d+_segm.fits$', relpath.name )
    if match is None:
        raise RuntimeError( f"Failed to parse {relpath.name} to get pointing" )
    pointing = match.group(1)

    with snappl.db.db.DBCon() as dbcon:
        # WARNING, not looking at provenance because this whole code is written for a specific
        #   database that's in a specific state
        rows, _cols = dbcon.execute( "SELECT id FROM l2image WHERE pointing=%(p)s AND sca=%(s)s AND band=%(b)s",
                                     {'p': pointing, 's': sca, 'b': band } )
        if len(rows) == 0:
            raise ValueError( f"Could not find image in database for pointing {pointing}, sca {sca}, "
                              f"and band {band}" )
        l2image_id = rows[0][0]

    params = { 'id': uuid.uuid4(),
               'provenance_id': provid,
               'band': band,
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
               'position_angle': image.position_angle,
               'format': 1,
               'l2image_id': l2image_id
              }
    return params


class OU2024_segmap_loader:
    def __init__( self, provid, base_path ):
        self.provid = provid.id if isinstance( provid, Provenance ) else provid
        self.base_path = pathlib.Path( base_path )
        self.dbcon = None


    def collect_ou2024_segmap_paths( self, relpath ):
        subdirs = []
        imagefiles = []

        SNLogger.debug( f"trolling directory {relpath}" )

        for fullpath in ( self.base_path / relpath ).iterdir():
            fullpath = fullpath.resolve()
            if fullpath.is_dir():
                subdirs.append( fullpath.relative_to( self.base_path ) )
            elif ( fullpath.name[-5:] == '.fits' ) or ( fullpath.name[-8:] == '.fits.gz' ):
                imagefiles.append( fullpath.relative_to( self.base_path ) )

        for subdir in subdirs:
            imagefiles.extend( self.collect_ou2024_segmap_paths(subdir) )

        return imagefiles

    def save_to_db( self ):
        if len( self.copydata ) > 0:
            SNLogger.info( f"Loading {len(self.copydata)} images to database..." )
            snappl.db.db.SegMap.bulk_insert_or_upsert( self.copydata, dbcon=self.dbcon )
            self.totloaded += len( self.copydata )
            self.copydata = []

    def append_to_copydata( self, relpath ):
        self.copydata.append( relpath )
        if len(self.copydata) % self.loadevery == 0:
            self.save_to_db()

    def omg( self, e ):
        SNLogger.error( f"Error processing FITS file: {e}" )
        self.errors.append( e )

    def __call__( self, dbcon=None, loadevery=1000, nprocs=1, filelist=None ):
        if filelist is None:
            SNLogger.info( f"Collecting images underneath {self.base_path}" )
            toload = self.collect_ou2024_segmap_paths( '.' )
        else:
            toload = filelist

        self.totloaded = 0
        self.copydata = []
        self.loadevery = loadevery
        self.errors = []

        SNLogger.info( f"Loading {len(toload)} files in {nprocs} processes...." )
        do_parse_fits_file = functools.partial( _parse_fits_file,
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

        return toload


# ======================================================================

def main():
    parser = argparse.ArgumentParser( 'load_ou2024_nov2025_segmaps',
                                      description='Load fits files below a directory.' )
    parser.add_argument( '-p', '--provid', required=True, help="Provenance id" )
    parser.add_argument( '-n', '--nprocs', type=int, default=20,
                         help="Number of processes to run at once [default: 20]" )
    parser.add_argument( '-b', '--basedir', default='/ou2024/RomanTDS/images/simple_model',
                         help='Base directory.' )
    parser.add_argument( '-j', '--just-get-filenames', default=False, action='store_true',
                         help="Don't actually load files to the database, just generate a file list." )
    parser.add_argument( '-s', '--save-file-list', default=None,
                         help="Write the file list to this file." )
    parser.add_argument( '-l', '--load-file-list', default=None,
                         help="Instead of crawling the filesystem, load the file list from this file." )
    args = parser.parse_args()

    with snappl.db.db.DBCon( dictcursor=True ) as dbcon:
        rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': args.provid } )
        if len(rows) == 0:
            raise ValueError( "Invalid provenance {args.provid}" )
        SNLogger.info( f"Loading with provenance for process {rows[0]['process']} "
                       f"{rows[0]['major']}.{rows[0]['minor']}" )


    loader = OU2024_segmap_loader( args.provid, args.basedir )

    if args.just_get_filenames:
        if args.load_file_list is not None:
            raise ValueError( "Can't give a load_file_list with just_get_filenames" )
        if args.save_file_list is None:
            raise ValueError( "You really want to give save_file_list when using just_get_filenames" )

        imagefiles = loader.collect_ou2024_segmap_paths( '.' )
        with open( args.save_file_list, 'w' ) as ofp:
            for f in imagefiles:
                ofp.write( str(f) )
                ofp.write( '\n' )

    else:
        filelist = None
        if args.load_file_list:
            with open( args.load_file_list ) as ifp:
                SNLogger.info( f"Reading files to load from {args.load_file_list}..." )
                filelist = [ pathlib.Path(f.strip()) for f in ifp.readlines() ]

        loader( nprocs=args.nprocs, filelist=filelist )

    SNLogger.info( "All done." )


# ======================================================================
if __name__ == "__main__":
    main()
