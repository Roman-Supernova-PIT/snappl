import pathlib
import copy

from snappl.provenance import Provenance
from snappl.diaobject import DiaObject
from snappl.logger import SNLogger
from snappl.util import asUUID


class Spectrum1d:
    """A class to store and save single-epoch 1d transient spectra."""

    def __init__( self, id=None, data_dict=None, filepath=None, base_dir=None,
                  provenance=None, diaobject=None, diaobject_position=None, no_database=False ):
        """Instantiate a Spectrum1d

        Spectrum1d schema are defined here:

           https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/spectrum_1d

        Inside the object, you can get access to parts of the spectrum
        with the following properties:

           * data_dict : the full dict described on that page
           * meta : data_dict['meta']
           * combined: data_dict['combined']
           * combined_meta: data_dict['combined']['meta']
           * combined_data: data_dict['combined']['data']
           * individual: data_dict['indivdual']

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
            Base directory that filepath is relative to.  If None, will
            use the config value of "system.paths.spectra1d".

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
        if ( data_dict is None ) and ( filepath is None ):
            raise ValueError( "Must specify either data_dict or filepath" )
        if ( data_dict is not None ) and ( filepath is not None ):
            SNLogger.warning( "Specifying both data_dict and filepath is bad form." )

        if ( id is None ) and ( filepath is not None ):
            match = re.search( r'([0-9a-f])/([0-9a-f])/([0-9a-f])/'
                               r'([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}).1dspec',
                               str(filepath) )
            if match is None:
                SNLogger.warning( "Could not parse filepath to find spectrum1d id, assigning a new one." )
            else:
                if any( match.group(1) != match.group(4)[0],
                        match.group(2) != match.group(4)[1],
                        match.group(3) != match.group(4)[2] ):
                    SNLogger.warning( "filepath didn't have consistent directory and filename, cannot parse "
                                      "spectrum1d id from it, assigning a new one" )
                else:
                    self.id = match.group(4)
        self.id = asUUID( id ) if id is not None else uuid.uuid4()

        self.base_dir = Config.get().value('system.paths.lightcurves') if base_dir is None else base_dir
        self._data_dict = self._set_data_dict( data_dict ) if data_dict is not None else None
        self._filepath = pathlib.Path( filepath ) if filepath is not None else None
        self.no_database = no_database
        
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
    def individual( sellf ):
        returns self.data_dict['individual']

    @property
    def filepath:
        if self._filepath is None:
            self.generate_filepath()
        return self._filepath
        
    @property
    def full_filepath:
        if self._filepath is None:
            self.generate_filepath()
        return self.base_dir / self._filepath

    def _set_data_dict( self, data_dict, provenance, diaobject, diaobject_position ):
        """Verifies and sets the data dict.  Makes a copy, so will not mung the passed object."""
        
        provenance = provenance.id if isinstance( provenance, Provenance ) else asUUID( provenance, oknone=True )
        diaobject = diaobject.id if isinstance( diaobject, DiaObject) else asUUID( diaobject, oknone=True )
        diaobject_position = ( diaobject_position['id'] if isinstance( diaobject_position, dict )
                               else asUUID( diaobject_position, oknone=True ) )
        
        data_dict = copy.deepcopy( data_dict )
        
        if not isinstance( data_dict, dict ):
            raise TypeError( f"data_dict must be a dict, not a {type(data_dict)}" )

        if set( data_dict.keys() ) != { 'meta', 'combined', 'individual' }:
            raise ValueError( f"data_dict must have keys 'meta', 'combined', and 'individual'" )

        if not isinstance( data_dict['meta'], dict ):
            raise TypeError( f"data_dict['meta'] must be a dict, not a {type(data_dict['meta'])}" )
        
        if not self.no_database:
            for prop, val in zip( [ 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id',
                                    self.id, provenance, diaobject, diaobject_position ] ):
                if prop not in data_dict['meta']:
                    data_dict['meta'] == val
                else:
                    try:
                        # This weird way of doing things is so that we will get the same error
                        #   message if there's a uuid mismatc, or if asUUID fails.
                        _ok = ( ( asUUID( data_dict['meta'][prop], oknone=True ) == val )
                                or
                                ( val is None ) )
                        data_dict['meta'][prop] = asUUID( data_dict['meta'][prop] )
                    except Exception:
                        raise ValueError( f"Property {prop} in data_dict['meta'] has value {data_dict['meta'][prop]}, "
                                          f"doesn't match expected value {val}" )

        data_dict['band'] = data_dict['band'] if 'band' in data_dict else None
        data_dict['filepath'] = str( self.filepath )
        
        

        
        
