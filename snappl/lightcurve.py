import io
import re
import copy
import numbers
import collections.abc
import uuid
import simplejson
from pathlib import Path

import numpy as np
import pandas as pd

from astropy.table import Table, QTable
import astropy.units

from snappl.provenance import Provenance
from snappl.diaobject import DiaObject
from snappl.pathedobject import PathedObject
from snappl.logger import SNLogger
from snappl.utils import asUUID, SNPITJsonEncoder
from snappl.dbclient import SNPITDBClient


class Lightcurve( PathedObject ):
    """A class to store and save lightcurve data across different SNPIT photometry codes.

    Properties include:
      * filepath : pathlib.Path ; path *relative to the base path* of the lightcurve file
      * full_filepath : pathlib.Path ; absolute path on the system to the lightcurve file
      * base_path : base path for lightcurves; usually will be Config value system.paths.lightcurves
      * base_dir : synonym for base_path
      * lightcurve : The actual lightcurve data, an Astropy QTable
                     (see https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve )
      * data : synonm for lightcurve
      * meta : dict, the metadata; synonym for self.lightcurve.meta, or None if the lightcurve data isn't loaded
               (access the lightcurve property to force it to load)

    """

    # I know this dictionary looks stupid, but it might not in the future.
    filename_extensions = { 'parquet': '.parquet',
                            'ecsv': '.ecsv'
                           }

    _base_path_config_item = 'system.paths.lightcurves'


    def __init__(self, id=None, data=None, meta=None, multiband=False,
                 filepath=None, base_dir=None, base_path=None, full_filepath=None, no_base_path=False ):
        """Instantiate a lightcurve.

        Lightcurve file schema are defined here:

          https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve

        Inside the instantiated Lightcurve object, the lightcurve is
        stored as an astropy QTable that may be accessed via the
        lightcurve property of the Lightcurve object.

       FOR LIGHTCURVE FILES THAT WILL BE SAVED TO THE DATABASE: Data can only have a single band.


        Parmeters
        ---------
          id : UUID or str or None
            ID of this lightcurve.  If None, one will be generated, and
            thereafter available in the id property.

          filepath : Path or str, default None
            File path to find the lightcurve, relative to base_dir.  You
            must specify either filepath, or both data and meta.

          base_path : Path or str, default None
            Base directory that filepath is relative to.  If None, will
            use the config value of "system.paths.lightcurves".

          data : dict, astropy.table.Table, astropy.table.QTable, or pandas.DataFrame, default None
            The data.  It must have the following columns, in order, as
            its first columns; additional columns after that are
            allowed.

               * mjd : float (MJD in days of this lightcurve point)
               * flux : float (DN/s in the transient at this point)
               * flux_err : float (uncertainty on flux)
               * zpt : float (mag_ab = -2.5*log10(flux) + zpt)
               * NEA : float (Noise-equivalent area in pixels²)
               * sky_rms : float (sky noise level, not including galaxy, at this image position in DN/s)
               * pointing : int/string (the pointing of this image; WARNING, THIS NAME WILL CHANGE LATER)
               * sca : int (the SCA of this image)
               * pix_x : float (The 0-offset position of the SN on the detector)
               * pix_y : float (The 0-offset position of the SN on the detector)

            If multiband is true, then there needs to be a column band
            (string) after mjd.

            If a dict, must be a dict of lists.  The keys of the dict
            are the columns; they will be sorted as listed above.  There
            is no guarantee as to the sorting of additional columns
            after the required ones.

          meta : dict
            Lightcurve metadata.  Requires the following keys; can have
            additional keys in addition to this metadata.

              * provenance_id : str or UUID (provenance of this lightcuve)
              * diaobject_id : str or UUID (SN this is a lightcurve for)
              * diaobject_position_id : str or UUID (ID of the position in the database used*)
              * iau_name : str or None (TNS/IAU name of this SN)
              * band : string (only required if multiband is False, otherwise prohibited)
              * ra : float (RA used for forced photometry / scene modelling for this lightcurve)
              * ra_err : float (uncertainty on RA)
              * dec : float (dec used for forced photometry /scene modelling for this lightcurve)
              * dec_err : float (uncertainty on dec)
              * ra_dec_covar : float (covariance between ra and dec)
              * local_surface_brightness_{band} : float (galaxy surface brightiness in DN/sec/pixel)

            There must be a local_surface_brightness_{band} for every band that shows up in the data.

            iau_name, ra_err, dec_err, and ra_dec_covar may be None.

            NEA isn't supposed to be None, but may be in the short term.

            If diaobject_position_id is None, it means that the
            lightcurve used the intial object position pulled from the
            diaobject, or got its position somewhere else that is not
            adequately tracked.

            If the lightcurve is not intended to be saved to the
            database, provenance_id and diaobject_id may be none,
            otherwise they are requried.

          multiband : bool, default False
            Lightcurves as saved in the database are stored one band at
            a time.  However, you can write lightcurves that have all
            the bands mixed together if you wish.

            If a lightcurve is going to be saved to the databse, then
            multiband must be False.

            If multiband is True, then:
              * The "band" metadata field is no longer required (and probably shouldn't be there)
              * There is a required string column "band" after "mjd" in the data

        """

        super().__init__( filepath=filepath, base_path=base_path, base_dir=base_dir,
                          full_filepath=full_filepath, no_base_path=no_base_path )

        if ( ( ( data is None ) != ( meta is None ) ) or
             ( ( self._filepath is not None ) and ( data is not None ) )
            ):
            raise ValueError( "Must specify either filepath, xor (data and meta)." )

        if ( id is None ) and ( filepath is not None ):
            match = re.search( r'([0-9a-f])/([0-9a-f])/([0-9a-f])/'
                               r'([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}).ltcv',
                               str(filepath) )
            if match is None:
                SNLogger.warning( "Could not parse filepath to find lightcurve id, assigning a new one." )
            else:
                if any( match.group(1) != match.group(4)[0],
                        match.group(2) != match.group(4)[1],
                        match.group(3) != match.group(4)[2] ):
                    SNLogger.warning( "filepath didn't have consistent directory and filename, cannot parse "
                                      "lightcuve id from it, assigning a new one" )
                else:
                    self.id = match.group(4)
        self.id = asUUID( id ) if id is not None else uuid.uuid4()

        self._multiband = multiband
        self._lightcurve = None

        if self._filepath is None:
            self._set_data_and_meta( data, meta )


    @property
    def lightcurve( self ):
        if self._lightcurve is None and self._filepath is not None:
            self.read()
        return self._lightcurve

    @property
    def data( self ):
        return self._lightcurve

    @property
    def meta( self ):
        return None if self._lightcurve is None else self._lightcurve.meta


    def _set_data_and_meta( self, data, meta ):
        if not ( isinstance(data, dict) or isinstance(data, Table) or isinstance(data, QTable)
                 or isinstance(data, pd.DataFrame) ):
            raise TypeError( "Lightcurve data must be a dict, astropy Table, or pandas DataFrame" )
        if not isinstance(meta, dict):
            raise TypeError( "Lightcurve meta must be a dict" )

        # Verify input data.
        # (The list of required fields and types should match what's on
        # https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve )

        # These should match the wiki: https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        # This is a bit of a moving target, so it's possible the list below is out of date when you are reading this.

        meta_type_dict = {
            "provenance_id": (uuid.UUID, str, type(None)),
            "diaobject_id": (uuid.UUID, str, type(None)),
            "diaobject_position_id": (uuid.UUID, str, type(None)),
            "iau_name": (str, type(None)),
            "band": str,
            "ra": numbers.Real,
            "dec": numbers.Real,
            "ra_err": (numbers.Real, type(None)),
            "dec_err": (numbers.Real, type(None)),
            "ra_dec_covar": (numbers.Real, type(None)),
        }
        if self._multiband:
            del meta_type_dict['band']

        # This list also has the required order.
        # The keys of data_type_dict must match the members of required_data_cols
        required_data_cols = [ 'mjd', 'band', 'flux', 'flux_err', 'zpt', 'NEA', 'sky_rms',
                               'pointing', 'sca', 'pix_x', 'pix_y' ]
        data_type_dict = {
            "mjd": numbers.Real,
            "band": str,
            "flux": numbers.Real,
            "flux_err": numbers.Real,
            "zpt": numbers.Real,
            "NEA": numbers.Real,
            "sky_rms": numbers.Real,
            "pointing": (numbers.Integral, str),
            "sca": numbers.Integral,
            "pix_x": numbers.Real,
            "pix_y": numbers.Real
        }
        if self._multiband:
            if 'band' not in ( data if isinstance(data, dict) else data.columns ):
                raise ValueError( "missing data column band" )
            unique_bands = np.unique(data["band"])
            for b in unique_bands:
                meta_type_dict[f"local_surface_brightness_{b}"] = numbers.Real
        else:
            required_data_cols.remove( 'band' )
            del data_type_dict['band']
            if "band" not in meta:
                raise ValueError( "band is a required metadata keyword" )
            meta_type_dict[f"local_surface_brightness_{meta['band']}"] = numbers.Real
        if list( data_type_dict.keys() ) != required_data_cols:
            raise RuntimeError( "PROGRAMMER ERROR.  This should never happen.  See comments above this exception." )

        meta = copy.deepcopy( meta )

        missing_cols = []
        bad_types = []
        for col, col_type in meta_type_dict.items():
            if col not in meta:
                missing_cols.append( col )

            elif not isinstance(meta[col], col_type):
                bad_types.append( [ col, col_type, type(meta[col]) ] )

            else:
                if ( isinstance(col_type, collections.abc.Sequence) and
                     ( uuid.UUID in col_type ) and
                     ( meta[col] is not None )
                    ):
                    # Make sure that the meta that's supposed to be UUIDs really are
                    _ = asUUID( meta[col] )

                if isinstance(meta[col], uuid.UUID):
                    # parquet can't actually save python UUIDs, so stringify them.
                    meta[col] = str(meta[col])

        if ( len(missing_cols) != 0 ) or ( len(bad_types) != 0 ):
            if len(missing_cols) != 0:
                SNLogger.error( f"Missing the following required metadata columns: {missing_cols}" )
            if len(bad_types) != 0:
                sio = io.StringIO()
                sio.write( "The following metadata had the wrong type:\n" )
                for bad in bad_types:
                    sio.write( f"{bad[0]} needs to be {bad[1]}, but is {bad[2]}\n" )
                SNLogger.error( sio.getvalue() )
            raise ValueError( "Incorrect metadata." )

        data_cols = list(data.keys()) if type(data) is dict else list(data.columns)
        missing_data = []
        bad_data_types = []
        for col, col_type in data_type_dict.items():
            if col not in data_cols:
                missing_data.append( col )
            elif not all( isinstance(item, col_type) for item in data[col] ):
                bad_data_types.append( [ col, col_type ] )

        if ( len(missing_data) != 0 ) or ( len(bad_data_types) != 0 ):
            if len(missing_data) != 0:
                SNLogger.error( f"Missing the following required data columns: {missing_data}" )
            if len(bad_data_types) != 0:
                sio = io.StringIO()
                sio.write( "The following data columns had values of the wrong type:\n" )
                for bad in bad_data_types:
                    sio.write( f"{bad[0]} needs to be {bad[1]}\n" )
                SNLogger.error( sio.getvalue() )
            raise ValueError( "Incorrect or missing data columns." )


        # Create our internal representation in self.lightcurve from the passed data

        # The units are also defined on https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        # TODO : think about if the user has passed in a table that already
        #   has units; we should verify!!!

        units = { "mjd": astropy.units.d,
                  "flux": astropy.units.count / astropy.units.second,
                  "flux_err": astropy.units.count / astropy.units.second,
                  "zpt": astropy.units.mag,
                  "NEA": astropy.units.pix ** 2,
                  "sky_rms": astropy.units.count / astropy.units.second,
                  "pointing": "",
                  "sca": "",
                  "pix_x": astropy.units.pix,
                  "pix_y": astropy.units.pix
                 }

        if isinstance( data, pd.DataFrame ):
            lc = QTable( Table.from_pandas( data ), meta=meta, units=units )
        else:
            lc = QTable( data=data, meta=meta, units=units )
        data_cols = list(lc.columns)
        sorted_cols = required_data_cols + [ col for col in data_cols if col not in required_data_cols ]
        self._lightcurve = lc[sorted_cols]


    def generate_filepath( self, filetype="parquet" ):
        subdir = str(self.id)[0:3]
        basename = f"{self.meta['provenance_id']}/{subdir[0]}/{subdir[1]}/{subdir[2]}/{self.id}"
        if self._multiband:
            self.filepath = Path( f"{basename}.ltcv{self.filename_extensions[filetype]}" )
        else:
            if not re.search( r'^[A-Za-z0-9_:\-\.\+]+$', self.meta['band'] ):
                SNLogger.Warning( f"Lightcurve band is {self.meta['band']}, which may cause filename problems." )
            self.filepath = Path( f"{basename}.{self.meta['band']}.ltcv{self.filename_extensions[filetype]}" )



    def read( self, base_dir=None, filepath=None ):
        """Reads the lightcurve from its filepath."""

        basedir = Path( self.base_dir if base_dir is None else base_dir )
        filepath = Path( self.filepath if filepath is None else filepath )

        self._lightcurve = QTable.read( basedir / filepath )


    def write(self, base_dir=None, filepath=None, filetype="parquet", overwrite=False):
        """Save the lightcurve to a parquet file.

        To save it to the database, you must also call save_to_db after
        calling this function.

        After calling this function, the object's property filepath will
        be set with the output file's path relative to base_dir.

        Parameters
        ----------
          base_dir : str or pathlib.Path, default None
            The base directory where lightcurves are saved.  If None,
            this will use the one set when the Lightcurve was instantiated.

          filepath : str or pathlib.Path, default None
            The path relative to base_dir to write the file.  If None,
            the path will be constructed as

                {provid}/{i0}/{i1}/{i2}/{id}.ltcv.parquet

            where {provid} is the provenance id of the lightcurve, {id}
            is the id of the lightcurve, and {id[012]} are the first
            three characters of the id of the lightcurve.  (This is done
            so that no directory will have too many files; filesystems
            used on HPC clusters often do not want to have too many
            files in one directory.)

          filetype : str, default "parquet"
            Must be either "parquet" or "ecsv".  "parquet" is the
            standard for the SN PIT.

          overwrite: bool, default False
            If the file already exists, raise an Exception, unless this
            is True, in which case overwrite the existing file.

        """

        filetypemap = { 'parquet': 'parquet',
                        'ecsv': 'ascii.ecsv'
                       }
        if filetype not in filetypemap:
            raise ValueError( f"Unknown filetype {filetype}" )

        if ( filepath is None ) and ( self._filepath is None ):
            self.generate_filepath( filetype=filetype )
        filepath = self.filepath if filepath is None else filepath
        base_dir = Path( self.base_dir if base_dir is None else base_dir )

        fullpath = base_dir / filepath
        if fullpath.exists():
            if overwrite:
                if not fullpath.is_file():
                    raise FileExistsError( f"{fullpath} exists, but is not a normal file!  Not overwriting!" )
                fullpath.unlink( missing_ok=True )
            else:
                raise FileExistsError( f"{fullpath} exists and overwrite is False" )

        fullpath.parent.mkdir( parents=True, exist_ok=True )

        SNLogger.info( f"Saving lightcurve to {fullpath}" )
        self.lightcurve.write( fullpath, format=filetypemap[filetype] )

        self.filepath = filepath


    def save_to_db( self, dbclient=None ):
        """Write the existence of this file to the database.

        Note that the database does not store the actual lightcurve
        files!  You must call write() first.

        Parameters
        -----------
          dbclient : SNPITDBClient, default None
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        """

        if self.filepath.name[-8:] != '.parquet':
            raise ValueError( "Can only save lightcurves written as parquet files to the database." )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        data = { 'id': self.id,
                 'provenance_id': self.meta['provenance_id'],
                 'diaobject_id': self.meta['diaobject_id'],
                 'diaobject_position_id': self.meta['diaobject_position_id'],
                 'band': self.meta['band'],
                 'filepath': self.filepath
                }
        senddata = simplejson.dumps( data, cls=SNPITJsonEncoder )

        return dbclient.send( "savelightcurve", data=senddata, headers={'Content-Type': 'application/json'} )


    @classmethod
    def get_by_id( cls, lightcurve_id, dbclient=None ):
        """Get a lightcurve from its ID."""

        dbclient = SNPITDBClient() if dbclient is None else dbclient
        res = dbclient.send( f"getlightcurve/{lightcurve_id}" )

        return Lightcurve( id=res['id'], filepath=res['filepath'] )


    @classmethod
    def find_lightcurves( cls, diaobject=None, provenance=None, provenance_tag=None, process=None,
                          dbclient=None, **kwargs ):
        """Find lightcurves for an object.

        You may get back multiple lightcurves if you don't specify a band.

        If what you want is the combined lightcurve for all bands, call get_combined_lightcurve.

        Parameters
        ----------
          diaobject : DiaObject or UUID or str
            The DiaObject, or the id of the DiaObject, whose lightcurve you want.

          provenance : Provenance or UUID or str, default None
            The Provenance, or the id of the Provenacne, of the
            lightcurve you want.  You must pass either provenance or
            provenance_tag.  (If you pass both, provenance_tag will be
            ignored).

          provenance_tag : str, default None
            The provenance tag used to find the provenance of the
            lightcurves you want.  Ignored if provenance is not None.
            Requires process.

          process : str, default None
            The process used together with provenance_tag to find the
            provenance of the lightcurves you want.  Required if
            provenance_tag is not None.

          band : str, default None
            If given only return the lightcurve for this band.
            Otherwise, return all available bands.

          dbclient : SNPITDBClient, default None
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        Returns
        -------
          List of Lightcurve

        """

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        kwargs = kwargs.copy()
        if provenance is not None:
            if isinstance( provenance, Provenance ):
                kwargs[ 'provenance' ] = provenance.id
            else:
                kwargs[ 'provenance' ] = asUUID( provenance )
        if provenance_tag is not None:
            if process is None:
                raise ValueError( "Must specify process with provenance_tag" )
            kwargs[ 'provenance_tag' ] = provenance_tag
            kwargs[ 'process' ] = process
        if ( 'provenance' in kwargs ) == ( 'provenance_tag' in kwargs ):
            raise ValueError( "Must specify either provenance, or both of provenance_tag and process; "
                              "cannot specify both provenance and provenance_tag" )

        if diaobject is not None:
            kwargs['diaobject_id'] = diaobject.id if isinstance( diaobject, DiaObject ) else asUUID( diaobject )

        senddata = simplejson.dumps( kwargs, cls=SNPITJsonEncoder )
        reses = dbclient.send( "/findlightcurves", data=senddata, headers={'Content-Type': 'application/json'} )

        lightcurves = []
        for res in reses:
            lightcurves.append( Lightcurve( id=res['id'], filepath=res['filepath'] ) )

        return lightcurves


    @classmethod
    def get_combined_lightcurve( cls, diaobject, provenance=None, provenance_tag=None, process=None, dbclient=None ):
        """Return a lightcurve combining together all bands that are available.

        Will raise exceptions if the various lightcurves it's trying to
        combine aren't all self-consistent.  (In that case, it means
        that we did something wrong in generating those files.)

        WARNING : after calling this, do NOT save it to the database.
        You can write the file with write().

        """
        raise NotImplementedError( "Soon." )
