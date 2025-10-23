import io
import re
import copy
import numbers
import collections.abc
from pathlib import Path
import uuid

import numpy as np
import pandas as pd

from astropy.table import Table, QTable
import astropy.units

from snappl.logger import SNLogger
from snappl.utils import asUUID, SNPITJsonEncoder
from snappl.config import Config
from snappl.dbclient import SNPITDBClient
from snappl.diaobject import DiaObject

class Lightcurve:
    """A class to store and save lightcurve data across different SNPIT photometry codes."""

    def __init__(self, id=None, data=None, meta=None, filepath=None, base_dir=None ):
        """Instantiate a lightcurve.

        Lightcurve file schema are defined here:

          https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve

        Inside the instantiated Lightcurve object, the lightcurve is
        stored as an astropy QTable that may be accessed via the
        lightcurve property of the Lightcurve object.

        Parmeters
        ---------
          id : UUID or str or None
            ID of this lightcurve.  If None, one will be generated, and
            thereafter available in the id property.

          filepath : Path or str, default None
            File path to find the lightcurve, relative to base_dir.  You
            must specify either filepath, or both data and meta.

          base_dir : Path or str, default None
            Base directory that filepath is relative to.  If None, will
            use the config value of "system.paths.lightcurves".

          data : dict, astropy.table.Table, astropy.table.QTable, or pandas.DataFrame, default None
            The data.  It must have the following columns, in order, as
            its first columns; additional columns after that are
            allowed.

               * mjd : float (MJD in days of this lightcurve point)
               * band : string (filter of this point)
               * flux : float (DN/s in the transient at this point)
               * flux_err : float (uncertainty on flux)
               * zpt : float (mag_ab = -2.5*log10(flux) + zpt)
               * NEA : float (Noise-equivalent area in pixels²)
               * sky_rms : float (sky noise level, not including galaxy, at this image position in DN/s)
               * pointing : int/string (the pointing of this image; WARNING, THIS NAME WILL CHANGE LATER)
               * sca : int (the SCA of this image)
               * pix_x : float (The 0-offset position of the SN on the detector)
               * pix_y : float (The 0-offset position of the SN on the detector)

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

        """

        if ( filepath is None ) != ( ( data is None ) and ( meta is None ) ):
            raise ValueError( "Must specify filepath, or both of data and meta, but not both." )

        if ( id is None ) and ( filepath is not None ):
                match = re.search( r'([0-9a-f])/([0-9a-f])/([0-9a-f])/'
                                   r'([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}).ltcv' )
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
        id = asUUID( id ) if id is not None else uuid.uuid4()

        self.base_dir = Config.get().value('system.paths.lightcurves') if base_dir is None else base_dir

        self._lightcurve = None
        self._filepath = filepath

        if filepath is None:
            self._set_data_and_meta( data, meta )


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
            "iau_name": (str, None),
            "ra": numbers.Real,
            "dec": numbers.Real,
            "ra_err": (numbers.Real, type(None)),
            "dec_err": (numbers.Real, type(None)),
            "ra_dec_covar": (numbers.Real, type(None)),
        }

        # This list also has the required order.
        # The keys of data_unit_dict must match the members of required_data_cols
        required_data_cols = [ 'mjd', 'band', 'flux', 'flux_err', 'zpt', 'NEA', 'sky_rms',
                               'pointing', 'sca', 'pix_x', 'pix_y' ]
        data_unit_dict = {
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
        if list( data_unit_dict.keys() ) != required_data_cols:
            raise RuntimeError( "PROGRAMMER ERROR.  This should never happen.  See comments above this exception." )

        unique_bands = np.unique(data["band"])
        for b in unique_bands:
            meta_type_dict[f"local_surface_brightness_{b}"] = numbers.Real

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
        for col, col_type in self.required_data_cols.items():
            if col not in data_cols:
                missing_data.append( col )
            elif not all( isinstance(item, coltype) for item in data[col] ):
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


        # Create our internal representation in self.lightcurve from the passed data

        # The units are also defined on https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        # TODO : think about if the user has passed in a table that already
        #   has units; we should verify!!!

        units = { "mjd": astropy.units.d,
                  "band": "",
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

        lc = QTable( data=data, meta=meta, units=units )
        data_cols = list(lc.columns)
        sorted_cols = required_data_cols + [ col for col in data_cols if col not required_data_cols ]
        self._lightcurve = lc[sorted_cols]


    def read( self ):
        """Reads the lightcurve from its filepath."""
        raise NotImplementedError( "Soon." )

    @property lightcurve
    def lightcurve( self ):
        return self._lightcurve

    @property filepath
    def filepath( self ):
        return self._filepath

    @filepath.setter
    def filepath( self, val ):
        self._filepath = val


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
                        'ecsv': 'ascii.escv'
                       }
        if filetype not in filetypemap:
            raise ValueError( f"Unknown filetype {filetype}" )

        base_dir = Path( self.base_dir if base_dir is None else base_dir )

        if filepath is None:
            subdir = str(self.id)[0:2]
            filepath = Path( f"{str(self.lightcurve.meta['provenance_id']}/{subdir[0]}/{subdir[1]}/{subdir[2]}/"
                             f"{str(self.id)}.ltcv.parquet" )

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

        if self.filepath is None:
            raise ValueError( f"Cannot save lightcurve to database, filepath is None.  Call write() first." )

        dbclient = SNPITDBClient() if dbclient is None else dbclient

        bands = list( np.unique( self.lightcurve["band"] ) )
        bands.sort()

        data = { 'id': self.id,
                 'provenance_id': self.lightcurve.meta['provenance_id'],
                 'diaobject_id': self.lightcurve.meta['diaobject_id'],
                 'diaobject_position_id': self.lightcurve.meta['diaobject_position_id'],
                 'bands': bands,
                 'filepath': self.filepath }
        senddata = simplejson.dumps( data, cls=SNPITJsonEncoder )

        return dbclient.send( "savelightcurve", data=senddata, headers={'Content-Type': 'application/json'} )


    @classmethod
    def find_lightcurves( self, diaobject, provenance=None, provenance_tag=None, process=None, dbclient=None ):
        """Find lightcurves for an object.

        You may get back multiple lightcurves because the bands may be saved to different files.

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

          dbclient : SNPITDBClient, default None
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        Returns
        -------
          List of Lightcurve

        """
        raise NotImplementedError( "Soon." )

    @classmethod
    def get_combined_lightcurve( self, diaobject, provenance=None, provenance_tag=None, process=None, dbclient=None ):
        """Return a lightcurve combining together all bands that are available.

        Will raise exceptions if the various lightcurves it's trying to
        combine aren't all self-consistent.  (In that case, it means
        that we did something wrong in generating those files.)

        WARNING : after calling this, do NOT save it to the database.
        You can write the file with write().

        """
        raise NotImplementedError( "Soon." )
