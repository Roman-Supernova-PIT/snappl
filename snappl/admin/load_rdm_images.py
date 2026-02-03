import re
import uuid
import pathlib
import multiprocessing
import functools
import argparse
import hashlib
import os
import shutil

import psycopg

from snappl.image import RomanDatamodelImage
from snappl.logger import SNLogger
from snappl.utils import asUUID
from snappl.provenance import Provenance
import snappl.db.db


# python multiprocesing irritates me; it seems you can't
#   send a class method as the function
def _parse_rdm_file( sourcepath=None, dest_base_path=None, dest_subdir=None, link=False, provid=None, really_do=False ):
    sourcepath = pathlib.Path( sourcepath )
    if not sourcepath.exists():
        raise FileNotFoundError( f"Can't find {sourcepath}" )
    provid = asUUID( provid )
    # TODO : more subdirectories (e.g. by date, filter)
    filepath = pathlib.Path( dest_subdir ) / str(provid) / sourcepath.name
    writepath = pathlib.Path( dest_base_path ) / filepath

    # import random
    # import remote_pdb;
    # remote_pdb.RemotePdb( '127.0.0.1', random.randint( 4000, 5000 ) ).set_trace()
    image = RomanDatamodelImage( sourcepath, no_base_path=True )
    params = { 'id': uuid.uuid4(),
               'provenance_id': provid,
               'observation_id': image.observation_id,
               'sca': image.sca,
               'band': image.band,
               'ra': image.ra,
               'dec': image.dec,
               'ra_corner_00': image.ra_corner_00,
               'ra_corner_01': image.ra_corner_01,
               'ra_corner_10': image.ra_corner_10,
               'ra_corner_11': image.ra_corner_11,
               'dec_corner_00': image.dec_corner_00,
               'dec_corner_01': image.dec_corner_01,
               'dec_corner_10': image.dec_corner_10,
               'dec_corner_11': image.dec_corner_11,
               'filepath': str( filepath ),
               'width': image.image_shape[1],
               'height': image.image_shape[0],
               'format': 100,
               'mjd': image.mjd,
               'position_angle': image.position_angle,
               'exptime': image.exptime,
               'properties': psycopg.types.json.Jsonb( {} )
              }

    # Copy the file if necessary
    if really_do and ( filepath != writepath ):
        if writepath.exists():
            sourcemd5 = hashlib.md5()
            with open( sourcepath, "rb" ) as ifp:
                sourcemd5.update( ifp.read() )
            destmd5 = hashlib.md5()
            with open( writepath, "rb" ) as ifp:
                destmd5.update( ifp.read() )
            if destmd5.hexdigest() == sourcemd5.hexdigest():
                SNLogger.info( f"File {writepath} exists with write md5sum, not copying." )
            else:
                raise ValueError( f"File {writepath} exists but is different from {sourcepath}." )
        else:
            writepath.parent.mkdir( exist_ok=True, parents=True )
            if link:
                linkdest = sourcepath.relative_to( writepath, walk_up=True )
                os.symlink( linkdest, writepath )
            else:
                shutil.copy2( sourcepath, writepath )

    return params


class RDM_L2image_loader:
    def __init__( self, provid=None, source_path=None, dest_path=None, dest_subdir=None,
                  regex_image=None, symlink=False, really_do=False ):
        if any( i is None for i in [ provid, source_path, dest_path, dest_subdir, regex_image ] ):
            raise ValueError( "Must provide all of provid, source_path, dest_path, dest_subdir, and regex_image" )

        self.provid = provid.id if isinstance( provid, Provenance ) else provid
        self.source_path = pathlib.Path( source_path )
        self.dest_path = pathlib.Path( dest_path )
        self.dest_subdir = pathlib.Path( dest_subdir )
        self.regex_image = re.compile( regex_image )
        self.symlink = symlink
        self.really_do = really_do
        self.dbcon = None



    def collect_image_paths( self, relpath ):
        subdirs = []
        imagefiles = []

        SNLogger.debug( f"trolling directory {pathlib.Path(relpath).resolve()}" )

        for fullpath in ( self.source_path / relpath ).iterdir():
            fullpath = fullpath.resolve()
            if fullpath.is_dir():
                subdirs.append( fullpath.relative_to( self.source_path ) )
            if self.regex_image.search( fullpath.name ):
                imagefiles.append( fullpath.relative_to( self.source_path ) )

        for subdir in subdirs:
            imagefiles.extend( self.collect_image_paths(subdir) )

        return imagefiles

    def save_to_db( self ):
        if len( self.copydata ) > 0:
            SNLogger.info( f"Loading {len(self.copydata)} images to database..." )
            if self.really_do:
                snappl.db.db.L2Image.bulk_insert_or_upsert( self.copydata, dbcon=self.dbcon )
            self.totloaded += len( self.copydata )
            self.copydata = []

    def append_to_copydata( self, relpath ):
        self.copydata.append( relpath )
        if len(self.copydata) % self.loadevery == 0:
            self.save_to_db()

    def omg( self, e ):
        self.errors.append( e )

    def __call__( self, dbcon=None, loadevery=1000, nprocs=1, filelist=None ):
        SNLogger.info( f"Collecting images underneath {self.source_path}" )
        toload = self.collect_image_paths( "." )

        self.totloaded = 0
        self.copydata = []
        self.loadevery = loadevery
        self.errors = []

        SNLogger.info( f"Loading {len(toload)} files in {nprocs} processes...." )
        do_parse_rdm_file = functools.partial( _parse_rdm_file,
                                               provid=self.provid,
                                               dest_base_path=self.dest_path,
                                               dest_subdir=self.dest_subdir,
                                               link=self.symlink )

        with snappl.db.db.DBCon( dbcon ) as self.dbcon:
            if nprocs > 1:
                with multiprocessing.Pool( nprocs ) as pool:
                    for path in toload:
                        pool.apply_async( do_parse_rdm_file,
                                          args=[ str( self.source_path / path ) ],
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
                    self.append_to_copydata( do_parse_rdm_file( self.source_path / path ) )

            else:
                raise ValueError( "Dude, nprocs needs to be positive, not {nprocs}" )

            # Get any residual ones that didn't pass the "send to db" threshold
            self.save_to_db()

            SNLogger.info( f"Loaded {self.totloaded} of {len(toload)} images to database." )

        self.dbcon = None

        return toload


# ======================================================================

def main():
    parser = argparse.ArgumentParser( 'load_ou2024_l2images',
                                      description='Load roman datamodel image files below a directory.',
                                      formatter_class=argparse.ArgumentDefaultsHelpFormatter )
    parser.add_argument( '-p', '--provid', required=True, help="Provenance id" )
    parser.add_argument( '-n', '--nprocs', type=int, default=20,
                         help="Number of processes to run at once [default: 20]" )
    parser.add_argument( '-s', '--sourcedir', default='/data/images/SOC-HLTDS-sims-v0.1',
                         help="Where to find the images to load." )
    parser.add_argument( '-d', '--destdir', default='/data/images',
                         help=( "Base directory to copy images to.  Must be the same physical position as "
                                "config value system.paths.images" ) )
    parser.add_argument( '--subdir', default='',
                         help="Subdirectory under destdir to move images to if appropriate" )
    parser.add_argument( '-r', '--regex-image', default=".*_cal\\.asdf$",
                         help="Regex that filename must match to be considerd an image file we want to load" )
    parser.add_argument( '-l', '--link', default=False, action='store_true',
                         help=( "Don't copy files, instead put in relative symbolic links, "
                                "if you know what you're doing" ) )
    parser.add_argument( '--do', action='store_true', default=False,
                         help="Really do (otherwise, just try to read the files)." )

    args = parser.parse_args()

    with snappl.db.db.DBCon( dictcursor=True ) as dbcon:
        rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': args.provid } )
        if len(rows) == 0:
            raise ValueError( "Invalid provenance {args.provid}" )
        SNLogger.info( f"Loading with provenance for process {rows[0]['process']} "
                       f"{rows[0]['major']}.{rows[0]['minor']}" )


    loader = RDM_L2image_loader( provid=args.provid,
                                 source_path=args.sourcedir,
                                 dest_path=args.destdir,
                                 dest_subdir=args.subdir,
                                 regex_image=args.regex_image,
                                 symlink=args.link,
                                 really_do=args.do )
    loader( nprocs=args.nprocs )

    SNLogger.info( "All done." )


# ======================================================================
if __name__ == "__main__":
    main()
