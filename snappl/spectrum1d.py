import pathlib
import copy
import uuid
import re
import simplejson

import h5py
import numpy as np

from snappl.provenance import Provenance
from snappl.diaobject import DiaObject
from snappl.image import Image
from snappl.pathedobject import PathedObject
from snappl.logger import SNLogger
from snappl.utils import asUUID, SNPITJsonEncoder
from snappl.dbclient import SNPITDBClient


class Spectrum1d( PathedObject ):
    """A class to store and save single-epoch 1d transient spectra.

       Spectrum1d schema are defined here:

          https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/spectrum_1d

       Properties of a Spectrum1d object include:
        * filepath : pathlib.Path ; path *relative to the base path* of the spectrum1d file
        * full_filepath : pathlib.Path ; absolute path on the system to the spectrum1d file
        * base_path : base path for lightcurves; usually will be Config value system.paths.lightcurves
        * base_dir : synonym for base_path

        * data_dict : the full dict described the schema wiki page linked above
        * meta : data_dict['meta']
        * combined: data_dict['combined']
        * combined_meta: data_dict['combined']['meta']
        * combined_data: data_dict['combined']['data']
        * individual: data_dict['indivdual']

        * id : UUID, the id of the spectrum
        * provenance_id : UUID, the id of the spectrum's provenance
        * diaobject_id : UUID, the id of the object for which this is a spectrum
        * diaobject_position_id : UUID or None, the id of the object's improved position if any
        * band : str, the band
        * mjd_start : float, the MJD of the earliest component image
        * mjd_end : float, the MJD + exposure time (in days) of the latest component image
        * epoch : integer, the average MJD in millidays (i.e. MJD * 1000) of the comonent image MJDs
        * images : list of Image, the component images

    """

    _base_path_config_item = 'system.paths.spectra1d'


    def __init__( self,
                  id=None,
                  data_dict=None,
                  provenance=None,
                  diaobject=None,
                  diaobject_position=None,
                  band=None,
                  mjd_start=None,
                  mjd_end=None,
                  epoch=None,
                  no_database=False,
                  dbclient=None,
                  filepath=None,
                  base_dir=None,
                  base_path=None,
                  full_filepath=None,
                  no_base_path=False,
                 ):
        """Instantiate a Spectrum1d

        Parameters
        ----------
          id : UUID or str or NOne
            ID of this lightcurve.  If None, one will be generated, and
            thereafter aavilable in the id property.

          data_dict : dict
            Must follow the format on

              https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/spectrum_1d

            You must give one of data_dict or filepath; it is bad form
            to specify both.

          filepath : Path or str, default None
            File path to find the lightcurve, realtive to base dir.  You
            must specify either data_dict or filepath; it is bad form to
            specify both.

          base_dir: Path or str, default None
            Base directory that filepath is relative to.  If None (which
            is what you want if you're writing things to the database),
            will use the config value of "system.paths.spectra1d".

          provenance: Provenance or UUID or str or None
            The provenance of this lightcurve.  You may also set
            data_dict['meta']['provenance_id'] to the UUID of the
            provenance instead of passing it here.

          diaobject: DiaObject or UUID or str or None
            The DiaObject this is a spectrum for.  You may also set
            data_dict['meta']['diaobject_id'] to the UUID of the
            diaboject instead of passing it here.

          diaobject_position_id: dict or UUID or str or None
            Either the improved position as returned form
            DiaObject.get_position(), or the value of the id from the
            dictionary returned by that call.  You may also set data_dict['meta']['diaobject_position_id']

        """
        super().__init__( filepath=filepath, base_path=base_path, base_dir=base_dir,
                          full_filepath=full_filepath, no_base_path=no_base_path )
        if ( data_dict is None ) and ( self._filepath is None ):
            raise ValueError( "Must specify either data_dict or filepath" )
        if ( data_dict is not None ) and ( self._filepath is not None ):
            SNLogger.warning( "Specifying both data_dict and filepath is bad form." )

        if ( id is None ) and ( self._filepath is not None ):
            match = re.search( r'([0-9a-f])/([0-9a-f])/([0-9a-f])/'
                               r'([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}).1dspec',
                               str(self._filepath) )
            if match is None:
                SNLogger.warning( "Could not parse filepath to find spectrum1d id, assigning a new one." )
            else:
                if any( [ match.group(1) != match.group(4)[0],
                          match.group(2) != match.group(4)[1],
                          match.group(3) != match.group(4)[2] ] ):
                    SNLogger.warning( "filepath didn't have consistent directory and filename, cannot parse "
                                      "spectrum1d id from it, assigning a new one" )
                else:
                    self.id = match.group(4)
        self.id = asUUID( id ) if id is not None else uuid.uuid4()

        self.provenance_id = ( provenance.id if isinstance( provenance, Provenance )
                               else asUUID( provenance, oknone=True ) )
        self.diaobject_id = ( diaobject.id if isinstance( diaobject, DiaObject )
                              else asUUID( diaobject, oknone=True ) )
        self.diaobject_position_id = ( asUUID(diaobject_position['id']) if isinstance( diaobject_position, dict )
                                       else asUUID( diaobject_position, oknone=True ) )
        self.no_database = no_database

        self._band = None
        self._mjd_start = None
        self._mjd_end = None
        self._epoch = None
        self._images = None

        if data_dict is None:
            self._data_dict = None
        else:
            self._set_data_dict( data_dict, dbclient=dbclient )

    @property
    def band( self ):
        if self._band is None:
            self._fill_props()
        return self._band

    @property
    def mjd_start( self ):
        if self._mjd_start is None:
            self._fill_props()
        return self._mjd_start

    @property
    def mjd_end( self ):
        if self._mjd_end is None:
            self._fill_props()
        return self._mjd_end

    @property
    def epoch( self ):
        if self._epoch is None:
            self._fill_props()
        return self.epoch

    @property
    def images( self ):
        if self._images is None:
            self._fill_props()
        return self.images


    def _fill_props( self, dbclient=None ):
        """Fills self.images, self.band, self.mjd_start, self.mjd_end, and self.epoch based on data_dict."""

        imageids = set( str(i['meta']['image_id']) for i in self.individual  )
        if ( self._images is None ) or ( set( str(i.id) for i in self._images ) != imageids ):
            # Have to reload images:
            dbclient = SNPITDBClient.get() if dbclient is None else dbclient
            self._images = []
            for imid in imageids:
                try:
                    image = Image.get_image( imid, dbclient=dbclient )
                    if not isinstance( image, Image ):
                        raise TypeError( "Didn't get an Image back from Image.get_image; this should not happen." )
                except Exception as ex:
                    SNLogger.error( f"Spectrum1d.save_to_db failed to get image {imid} from the database:\n{ex}" )
                    raise
                self._images.append( image )
            self._images.sort( key=lambda x: x.mjd )

        self._mjd_start = self._images[0].mjd
        self._mjd_end = self._images[-1].mjd + self._images[-1].exptime / 3600. / 24.
        self._epoch = int( np.floor( sum([ i.mjd for i in self._images ]) / len(self._images) * 1000 + 0.5 ) )
        if any( i.band != self._images[0].band for i in self._images ):
            raise ValueError( "Images have inconsistent bands!" )
        self._band = self._images[0].band


    @property
    def data_dict( self ):
        if self._data_dict is None:
            if self._filepath is None:
                raise RuntimeError( "Can't find the data" )
            self.read_data()
        return self._data_dict

    @data_dict.setter
    def data_dict( self, val ):
        self._data_dict = val

    @property
    def meta( self ):
        return self.data_dict['meta']

    @property
    def combined( self ):
        return self.data_dict['combined']

    @property
    def combined_meta( self ):
        return self.data_dict['combined']['meta']

    @property
    def combined_data( self ):
        return self.data_dict['combined']['data']

    @property
    def individual( self ):
        return self.data_dict['individual']

    def generate_filepath( self, filetype='hdf5' ):
        suffixdict = { 'hdf5': 'hdf5' }
        if filetype not in suffixdict:
            raise ValueError( f"Unknown filetype {filetype}" )
        subdir = str(self.id)[0:3]
        basename = f'{self.provenance_id}/{subdir[0]}/{subdir[1]}/{subdir[2]}/{self.id}'
        self._filepath = pathlib.Path( f'{basename}_1dspec.{suffixdict[filetype]}' )

    def _set_data_dict( self, data_dict, provenance=None, diaobject=None, diaobject_position=None, dbclient=None ):
        """Verifies and sets the data dict.  Makes a copy, so will not mung the passed object."""

        provenance = provenance.id if isinstance( provenance, Provenance ) else asUUID( provenance, oknone=True )
        diaobject = diaobject.id if isinstance( diaobject, DiaObject) else asUUID( diaobject, oknone=True )
        diaobject_position = ( diaobject_position['id'] if isinstance( diaobject_position, dict )
                               else asUUID( diaobject_position, oknone=True ) )

        provenance = self.provenance_id if provenance is None else provenance
        diaobject = self.diaobject_id if diaobject is None else None
        diaobject_position = self.diaobject_position_id if diaobject_position is None else None

        data_dict = copy.deepcopy( data_dict )

        # Basic type checking

        if not isinstance( data_dict, dict ):
            raise TypeError( f"data_dict must be a dict, not a {type(data_dict)}" )
        if set( data_dict.keys() ) != { 'meta', 'combined', 'individual' }:
            raise ValueError( "data_dict must have keys 'meta', 'combined', and 'individual'" )
        if not isinstance( data_dict['meta'], dict ):
            raise TypeError( f"data_dict['meta'] must be a dict, not a {type(data_dict['meta'])}" )
        if not isinstance( data_dict['combined'], dict ):
            raise TypeError( f"data_dict['combined'] must be a dict, not a {type(data_dict['combined'])}" )
        if set( data_dict['combined'].keys() ) != { 'meta', 'data' }:
            raise ValueError( "data_dict['combined'] must have keys 'meta' and 'data'" )
        if not isinstance( data_dict['individual'], list ):
            raise TypeError( f"data_dict['individual'] must be a list, not a {type(data_dict['individual'])}" )
        for indiv in data_dict['individual']:
            if not isinstance( indiv, dict ):
                raise TypeError( f"elements of the data_dict['individual'] list must be dicts, but at least one is "
                                 f"a {type(indiv)}" )
            if set( indiv.keys() ) != { 'meta', 'data' }:
                raise ValueError( "Each dict in the data_dict['individual'] list must have keys 'meta' and 'data'" )

        # Make sure the ids and provenances are all there

        if not self.no_database:
            for prop, val in zip( [ 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id' ],
                                  [ self.id, provenance, diaobject, diaobject_position ] ):
                if prop not in data_dict['meta']:
                    data_dict['meta'][prop] = val

                try:
                    # This weird way of doing things is so that we will get the same error
                    #   message if there's a uuid mismatch, or if asUUID fails.
                    # diaobject_position_id is the only one that can be None
                    _ok = ( ( ( val is None ) and ( prop == 'diaobject_position_id' ) )
                            or
                            ( asUUID( data_dict['meta'][prop] ) == val )
                           )
                    data_dict['meta'][prop] = asUUID( data_dict['meta'][prop], oknone=True )
                except Exception:
                    raise ValueError( f"Property {prop} in data_dict['meta'] has value {data_dict['meta'][prop]}, "
                                      f"doesn't match expected value {val}" )

            # Make sure the self attributes are set
            self.provenance_id = data_dict['meta']['provenance_id']
            self.diaobject_id = data_dict['meta']['diaobject_id']
            self.diaobject_position_id = data_dict['meta']['diaobject_position_id']

        data_dict['meta']['band'] = data_dict['band'] if 'band' in data_dict else None
        data_dict['meta']['filepath'] = str( self.filepath )

        # Make sure that if there's an nfiles in meta, it is right
        if 'nfiles' in data_dict['combined']['meta']:
            if data_dict['combined']['meta']['nfiles'] != len(data_dict['individual']):
                raise ValueError( f"You have nfiles={data_dict['meta']['nfiles']} in meta, but the individual list "
                                  f"is length {len(data_dict['individual'])}" )
        else:
            data_dict['meta']['combined']['nfiles'] = len( data_dict['individual'] )

        # Make sure that we have an image_id for all the individual files

        if not self.no_database:
            for indiv_dict in data_dict['individual']:
                if 'image_id' not in indiv_dict['meta']:
                    raise ValueError( "All 'individual' dictionaries must have an image_id key" )
                # Make sure it uuidifies
                _ = asUUID( indiv_dict['meta']['image_id'] )

        # TODO VERIFY DATA FORMAT

        self._data_dict = data_dict
        if not self.no_database:
            dbclient = SNPITDBClient.get() if dbclient is None else dbclient
            self._fill_props( dbclient=dbclient )


    def write_file( self, filepath=None ):
        """Writes the file

        Parameters
        ----------
          filepath : str or pathlib.Path, default None
            The full path to write the file to.  If None, then will use
            the base_path and filepath passed at object construction, or
            if those were None, will generate a standard filepath used
            for the database files.  If you're writing to the database,
            you usually want this to be None.

        """

        filepath = pathlib.Path( filepath ) if filepath is not None else self.full_filepath
        filepath.parent.mkdir( exist_ok=True, parents=True )

        with h5py.File( filepath, 'w' ) as h5f:
            topgrp = h5f.create_group( "spectrum1d" )
            for key, val in self.data_dict['meta'].items():
                if isinstance( val, uuid.UUID ):
                    topgrp.attrs[key] = str(val)
                else:
                    topgrp.attrs[key] = val if val is not None else h5py.Empty('i')

            combined = topgrp.create_group( "combined" )
            for key, val in self.data_dict['combined']['meta'].items():
                if isinstance( val, uuid.UUID ):
                    combined.attrs[key] = str( val )
                else:
                    combined.attrs[key] = val if val is not None else h5py.Empty('i')
            combined.create_dataset( 'lamb', data=self.data_dict['combined']['data']['lamb'] )
            combined.create_dataset( 'flam', data=self.data_dict['combined']['data']['flam'] )
            combined.create_dataset( 'func', data=self.data_dict['combined']['data']['func'] )
            combined.create_dataset( 'count', data=self.data_dict['combined']['data']['count'] )

            for dex, indiv in enumerate( self.data_dict['individual'] ):
                indivgrp = topgrp.create_group( f"individual_{dex}" )
                for key, val in indiv['meta'].items():
                    if isinstance( val, uuid.UUID ):
                        indivgrp.attrs[key] = str(val)
                    else:
                        indivgrp.attrs[key] = val if val is not None else h5py.Empty('i')
                indivgrp.create_dataset( 'lamb', data=indiv['data']['lamb'] )
                indivgrp.create_dataset( 'flam', data=indiv['data']['flam'] )
                indivgrp.create_dataset( 'func', data=indiv['data']['func'] )

    def read_data( self, filepath=None, dbclient=None ):
        """Reads the file.

        Populates self._data_dict

        Parameters
        ----------
          filepath : str or pathlib.Path, default None
            The full path to write the file to.  If None, then will use
            the base_path and filepath passed at object construction.

        """

        filepath = pathlib.Path( filepath ) if filepath is not None else self.full_filepath

        self._data_dict = { 'meta': {},
                            'combined': { 'meta': {}, 'data': {} },
                            'individual': [] }

        with h5py.File( filepath, 'r' ) as h5f:
            topgrp = h5f['spectrum1d']
            self._data_dict['meta'] = dict( topgrp.attrs )
            for key in self._data_dict['meta']:
                if self._data_dict['meta'][key] == h5py.Empty('i'):
                    self._data_dict['meta'][key] = None

            combgrp = topgrp['combined']
            self._data_dict['combined']['meta'] = dict( combgrp.attrs )
            tmpd = self._data_dict['combined']['meta']
            for key in tmpd:
                if tmpd[key] == h5py.Empty('i'):
                    tmpd[key] = None
            self._data_dict['combined']['data']['lamb'] = combgrp['lamb'][:]
            self._data_dict['combined']['data']['flam'] = combgrp['flam'][:]
            self._data_dict['combined']['data']['func'] = combgrp['func'][:]
            self._data_dict['combined']['data']['count'] = combgrp['count'][:]

            # Figure out how many individuals there are
            nkeys = 0
            for key in topgrp.keys():
                mat = re.search( r'^individual_(\d+)$', key )
                if mat is not None:
                    nkeys = max( nkeys, int(mat.group(1))+1 )

            for indivdex in range(nkeys):
                indiv = {}
                indivgrp = topgrp[ f'individual_{indivdex}' ]
                indiv['meta'] = dict( indivgrp.attrs )
                for key in indiv['meta']:
                    if indiv['meta'][key] == h5py.Empty('i'):
                        indiv['meta'][key] =  None
                indiv['data'] = { 'lamb': indivgrp['lamb'][:],
                                  'flam': indivgrp['flam'][:],
                                  'func': indivgrp['func'][:] }
                self._data_dict['individual'].append( indiv )

        if not self.no_database:
            dbclient = SNPITDBClient.get() if dbclient is None else dbclient
            self._fill_props( dbclient=dbclient )


    def save_to_db( self, write=False, dbclient=None ):
        """Save spectrum to db.

        Parmaters
        ---------
          write : bool, default False
            If write=True, then also write the file.  If not, then you
            must call write_file() first.  (If you call write() and then
            call this with write=True, you'll get a file exists error.)

          dbclient : SNPITDBClient, default None
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        Returns
        -------
          dict : the row of the database saved, for informational purposes


        """
        if self.no_database:
            raise RuntimeError( "Can't save a no_database spectrum to the database." )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        self._fill_props( dbclient=dbclient )
        if write:
            self.write_file()

        data = { 'id': self.id,
                 'provenance_id': self.provenance_id,
                 'diaobject_id': self.diaobject_id,
                 'diaobject_position_id': self.diaobject_position_id,
                 'band': self._images[0].band,
                 'filepath': self.filepath,
                 'mjd_start': self._mjd_start,
                 'mjd_end': self._mjd_end,
                 'epoch': self._epoch }

        return dbclient.send( "savespectrum1d", data=simplejson.dumps( data, cls=SNPITJsonEncoder ),
                              headers={'Content-Type': 'application/json'} )

    @classmethod
    def get_spectrum1d( cls, spectrum1d_id, dbclient=None ):
        """Get a Specrum1d from the database.

        Parameters
        ----------
          spectrum1d_id : UUID or str that can be converted to a UUID
            The id of the spectrum to fetch.

          dbclient : SNPITDBClient or None
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        Returns
        -------
          Spectrum1d

        """
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        result = dbclient.send( f"getspectrum1d/{spectrum1d_id}" )
        # Adjust the return dict to what's expected by Spectrum1d.__init__()
        result['provenance'] = result['provenance_id']
        result['diaobject'] = result['diaobject_id']
        result['diaobject_position'] = result['diaobject_position_id']
        del result['provenance_id']
        del result['diaobject_id']
        del result['diaobject_position_id']
        del result['created_at']
        return Spectrum1d( **result )

    @classmethod
    def find_spectra( cls, provenance=None, provenance_tag=None, process=None, dbclient=None,
                      diaobject=None, **kwargs ):
        """Search the database for spectra.

        Must pass either provenance, or both of (provenance_tag and
        process).  All the rest are optional; omitted parameters will
        just not be used to filter the list of returned spectra.

        Parameters
        -----------
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

          dbclient : SNPITDBClient or None
            The connection to the database (optional).  If you don't
            pass one, will use the cached connection, or will make a new
            one based on what's in the config.

          diaobject : DiaObject or UUID or str or None
            The DiaObject, or the ID of the object, you want spectra for.

          band : str
            The band of the images that went into the spectrum

          mjd_start, mjd_end : float The earliesr mjd, and latest mjd,
            of the individual images that went into the exposure.
            (mjd_end is actually the mjd of the final image, plus it's
            exposure time converted to days).

          mjd_start_min, mjd_start_max, mjd_end_min, mjd_end_max : float
            Use these if you want to search a range of times.

          order_by: str or list, default None
            By default, the returned images are not sorted in any
            particular way.  Put a keyword here to sort by that value
            (or by those values).  Options include 'id',
            'provenance_id', 'pointing', 'sca', 'ra', 'dec', 'filepath',
            'width', 'height', 'mjd', 'exptime'.  Not all of these are
            necessarily useful, and some of them may be null for many
            objects in the database.

          limit : int, default None
            Only return this many objects at most.

          offset : int, default None
            Useful with limit and order_by ; offset the returned value
            by this many entries.  You can make repeated calls to
            find_objects to get subsets of objects by passing the same
            order_by and limit, but different offsets each time, to
            slowly build up a list.

        Returns
        -------
          List of spectra

        """

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        params = kwargs

        if provenance is not None:
            if isinstance( provenance, Provenance ):
                params['provenance'] = provenance.id
            else:
                params['provenance'] = asUUID( provenance )
        else:
            if ( provenance_tag is None ) or ( process is None ):
                raise ValueError( "You must pass either provenance, or both of provenance_tag and process" )
            params['provenance_tag'] = provenance_tag
            params['process'] = process

        if diaobject is not None:
            params['diaobject_id'] = diaobject.id if isinstance( diaobject, DiaObject ) else asUUID( diaobject )

        reses = dbclient.send( "/findspectra1d", data=simplejson.dumps( params, cls=SNPITJsonEncoder ),
                               headers={'Content-Type': 'application/json'} )
        spectra1d = []
        for res in reses:
            # Worm things around to work for kwargs to __init__
            res['provenance'] = res['provenance_id']
            res['diaobject'] = res['diaobject_id']
            res['diaobject_position'] = res['diaobject_position_id']
            del res['provenance_id']
            del res['diaobject_id']
            del res['diaobject_position_id']
            del res['created_at']
            spectra1d.append( Spectrum1d( **res ) )

        return spectra1d
