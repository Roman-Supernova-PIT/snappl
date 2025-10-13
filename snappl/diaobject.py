__all__ = [ 'DiaObject', 'DiaObjectOU2024', 'DiaObjectManual' ]

import inspect

from snappl.config import Config
from snappl.http import retry_post
from snappl.provenance import Provenance
from snappl.dbclient import SNPITDBClient


class DiaObject:
    """Encapsulate a single supernova (or other transient).

    Standard properties:

    ra : ra in degrees (ICRS)
    dec : dec in degrees (ICRS)

    mjd_discovery : when the object was first discovered; may be None if unknown (float MJD)
    mjd_peak : peak of the object's lightcurve; may be None if unknown (float MJD)

    mjd_start : MJD when the lightcurve first exists.  Definition of this
                is class-dependent; it may be when it was actively
                simulated, but it may be when the lightcurve is above some
                cutoff.  May be None if unknown.

    mjd_end : MJD when the lightcurve stops existing.  Definition like
              mjd_start.  May be None if unknown.

    properties : dictionary of additional properties.  DO NOT RELY ON
                 THIS HAVING ANY PARTICULAR KEYS.  Different
                 provenances, and maybe even different objects within
                 the same provenance, may have different keys in this
                 dictionary.  This is more to be used for debugging
                 purposes.  (If there is an additional key that every
                 object should have, we should add it as a top-level
                 property, and add that column to the database.)

    Don't instantiate one of these directly.  Instead, use
    DiaObject.get_object or DiaObject.find_objects.  If you're trying to
    get a manual object, use provenance_tag 'manual' with
    DiaObject.get_object.

    """

    def __init__( self, id=None, provenance_id=None, ra=None, dec=None, name=None, iauname=None,
                  mjd_discovery=None, mjd_peak=None, mjd_start=None, mjd_end=None,
                  properties={}, _called_from_find_objects=False ):
        """Don't call a DiaObject or subclass constructor.  Use DiaObject.find_objects."""
        if not _called_from_find_objects:
            raise RuntimeError( "Don't call a DiaObject or subclass constructor.  "
                                "Use DiaObject.find_objects or DiaObject.get_object." )
        self.id = id
        self.provenance_id = provenance_id
        self.ra = float( ra ) if ra is not None else None
        self.dec = float( dec ) if dec is not None else None
        self.name = str( name ) if name is not None else None
        self.iauname = str( iauname ) if iauname is not None else None
        self.mjd_discovery = float( mjd_discovery ) if mjd_discovery is not None else None
        self.mjd_peak = float( mjd_peak ) if mjd_peak is not None else None
        self.mjd_start = float( mjd_start ) if mjd_start is not None else None
        self.mjd_end = float( mjd_end ) if mjd_end is not None else None
        self.properties = properties

    @classmethod
    def _parse_tag_and_process( cls, provenance_tag, process=None, provenance_id=None,
                                multiple_ok=False, nosubclass=False, dbclient=None ):
        """Convert a collection and subset to a provenance a process, OR to a DiaObject subclass.

        Parameters
        ----------
          proveneance_tag: str

          process: str, default None
            Must be None if provenance_tag corresponds to a DiaObject
            subclass.  Otherwise, if multiple_ok is False, then process is
            required; if multiple_ok is True, you'll get back a list of
            all provenences for all processes with the requested tag.

          provenance_id: UUID or str, default None
            If given, verify that the returned process is what's
            expected.  Must be None if process is None.

          multiple_ok: bool, default False

          nosubclass: bool, default False
            If True, then we are saying that we know that provenance_tag
            is something in the database.

          dbclient: SNPITDBClient

        Returns
        -------
          If provenance_tag corresponds to something that yields a
          DiaObject subclass, then you get that subclass back.

          Otherwise:
            If process is None and multiple_ok is False, that's an error.

            If process is None and multiple_ok is True, you get back a list of Provenance.

            Otherwise: you get back a Provenance

        """

        subclassmap = { 'ou2024': DiaObjectOU2024,
                        'manual': DiaObjectManual }

        if ( provenance_tag in subclassmap ) and ( not nosubclass ):
            if process is not None:
                raise ValueError( f"process must be None for provenance tag {provenance_tag} and nosubclass=False" )
            if provenance_id is not None:
                raise ValueError( f"provenence tag {provenance_tag} with nosubclass=False does not support "
                                  f"passing provenance_id" )
            return subclassmap[ provenance_tag ]

        # If we get here, we know we're searching the database

        if process is None:
            if not multiple_ok:
                raise ValueError( "Process must be None unless multiple_ok is True" )
            if provenance_id is not None:
                raise ValueError( "Cannot specify a provenance_id when process is None" )

        provs = Provenance.get_provs_for_tag( provenance_tag, process, dbclient=dbclient )
        if provenance_id is not None:
            if str(provs.id) != str(provenance_id):
                raise ValueError( f"Provenance tag {provenance_tag} and process {process} is provenance "
                                  f"{provs.id} in the database, but you expected {provenance_id}" )
        return provs


    @classmethod
    def get_object( cls, provenance=None, provenance_tag=None, process=None,
                    name=None, iauname=None, diaobject_id=None,
                    multiple_ok=False, dbclient=None ):
        """Get a DiaObject. from the database.

        You must pass at most one of:
          * provenance_id
          * provenance_tag and process

        Specify the object with exactly one of:
          * diaobject_id
          * name
          * iauname

        If you pass diaobject_id, then it's optional to pass one either
        provenance_id or (provenance_tag and process).  If you do pass
        one of those, then you will get an error of the diaobject_id
        you asked for isn't in the set you asked for.

        Note that if you ask for "name", there might be multiple objects
        in the database with the same name for a given provenance,
        because the database does not enforce uniqueness.  (It does for
        iauname.)  "name" is really more of an advisory field.  If
        multiple_ok is False (the default), this is an error; if
        multiple_ok is True, you'll get a list back.

        NOTE : in the future we will add the concept of "root diaobject"
        so that we can identify when the same objects show up in
        different provenances.  This method will change when that
        happens.

        Parameters
        ----------
         provenance: Provenance, UUID, or UUIDifiable str
            The provenance of the object you're looking for.  You don't
            need this if you pass provenance_tag and process.

         provenance_tag : str
           The human-readable provenance tag for the provenance of
           objects you want to dig through.  Usually requires 'process'.
           provenance_tag is required if you dont pass provenance_id,
           otherwise it's optional.

         process : str
           The process associated with the provenance_tag (needed to
           determine a unique provenance id).

         name : str (usually; might be an int for some provenance_tags)
           The name of the object as determined by whoever it was that
           was making the mess when loading objects into the database.
           This is not guaranteed to be unique.  However, if you know
           what you're doing, it may be useful.  If you are happy
           receiving all the objects for a given provenance with the
           same name, set multiple_ok to True; otherwise, it'll be an
           error if more than one object has the same name.

         iauname : str
           The iau/tns name of the object you want to find.  These are
           guaranteed to be unique within a given provenance.

         diaobject_id : UUID or str or maybe something else
           The Romamn SNPIT internal database id of the object you want.
           If you specify this, you don't need anything else.  If you
           also give one of (provenance_id, provenance_tag and process,
           collection and subset), then this method will verify that the
           object_id you're looking for is within the right provenance.

         multiple_ok : bool, default False
           Only matters if you specify name instead of object_id or
           iauname.  Ignored if you don't specify name.  See Returns.

         dbclient : SNPITDBClient, default None
           The database web api connection object to use.  If you don't
           specify one, a new one will be made based on what's in your
           configuration.

        Returns
        -------
          DiaObject or list of DiaObject

          If you specify name and you set multiple_ok=True, then you get
          a list of DiaObject back.  Otherwise, you get a single one.
          If no object is found with your criteria, a RuntimeError
          exception will be raised.

        """

        provenance_id = provenance.id if isinstance( provenance, Provenance ) else provenance

        if ( provenance_id is None ) and ( provenance_tag is None ) and ( diaobject_id is None ):
            raise ValueError( "Must specify a either a provenance or a provenance_tag "
                              "if you don't pass a diaobject_id" )

        dbclient = SNPITDBClient() if dbclient is None else dbclient

        if provenance_tag is not None:
            prov = cls._parse_tag_and_process( provenance_tag, process, provenance_id=provenance_id,
                                               multiple_ok=False, dbclient=dbclient )
            if isinstance( prov, Provenance ):
                provenance_id = prov.id
            elif inspect.isclass( prov ) and issubclass( prov, DiaObject ):
                # EARLY RETURN -- This is a "fake" provenance_tag that doesn't
                #   refer to a provenance_tag in the database, but rather
                #   something that uses one of the subclasses below.
                return prov._get_object( diaobject_id=diaobject_id, name=name, iauname=iauname,
                                         multiple_ok=multiple_ok )
            else:
                raise TypeError( f"Unexpected type return {type(prov)} from _parse_tag_and_process; "
                                 f"this shouldn't happen." )

        if diaobject_id is not None:
            kwargs = dbclient.send( f"getdiaobject/{diaobject_id}" )
            if len(kwargs) == 0:
                raise RuntimeError( f"Could not find diaobject {diaobject_id}" )
            else:
                if ( provenance_id is not None ) and ( str(kwargs['provenance_id']) != str(provenance_id) ):
                    raise ValueError( f"Error, you asked for object {diaobject_id} in provenance "
                                      f"{provenance_id}, but that object is actually in provenance "
                                      f"{kwargs['provenance_id']}" )

                return DiaObject( _called_from_find_objects=True, **kwargs  )

        else:
            if ( name is None ) and ( iauname is None ):
                raise ValueError( "Must give one of diaobject_id, name, or iauname" )
            subdict = {}
            if name is not None:
                subdict['name'] = name
            if iauname is not None:
                subdict['iauname'] = iauname
            res = dbclient.send( f"/finddiaobjects/{provenance_id}", subdict )
            if len(res) == 0:
                # TODO : make this error message more informative.  (Needs lots of logic
                #   based on what was passed... should probably construct the string
                #   at the top of the function.)
                raise RuntimeError( "Found no objects that match your criteria." )

            if ( name is not None ) and multiple_ok:
                return [ DiaObject( _called_from_find_objects=True, **r ) for r in res ]

            elif len(res) > 1:
                # Another error message that needs to be made more informative
                raise RuntimeError( "More than one object matched your criteria." )

            else:
                return DiaObject( _called_from_find_objects=True, **(res[0]) )



    @classmethod
    def _get_object( cls, name=None, iauname=None, diaobject_id=None, multiple_ok=False ):
        raise NotImplementedError( f"{cls.__name__} isn't able to do _get_object" )


    @classmethod
    def find_objects( cls, provenance=None, provenance_tag=None, process=None, dbclient=None, **kwargs ):
        """Find objects.

        Parameters
        ----------
          provenance : Provenance, UUID, or UUIDifiable str
            The provenance to search.  Must specify either this or
            provenance_tag.  If you specify both, it will verify
            consistency.

          provenance_tag : str
            The provenance tag to search.  For some provenance tags,
            this goes to a specific subclass (and in that case,
            provenance_id must be None), but for most, it queries the
            Roman SNPIT itnernal database.  Optional if you specify
            provenance_id.

          process : str, default None
            Usually required; can be None only if provenance_tag is one
            of the few that go to a specific subclass.

          dbclient : SNPITDBClient, default None
            The database web api connection object to use.  If you don't
            specify one, a new one will be made based on what's in your
            configuration.

          diaobject_id : <something>, default None
            The optional ID of the object.  A str will usually work.  For
            provenance_tags that go to the Roman SNPIT internal
            database, this needs to be something that can be converted
            to a UUID.  For provenance_tags that correspond to a
            specific subclass, exactly what this is depends on the
            subclass.

          name : str
            The optional name of the object.  May not be implemented for
            all provenance tags.

          iauname : str
            The TNS/IAU name of the object.  May not be implemented for
            all provenance_tags.

          ra: float
            RA in degrees to search.

          dec: float
            Dec in degrees to search.

          radius: float, default 1.0
            Radius in arcseconds to search.  Ignored unless ra and dec are given.

          mjd_peak_min, mjd_peak_max: float
            Only return objects whose mjd_peak is between these limits.
            Specify as MJD.  Will not return any objects with unknown
            mjd_peak.

          mjd_discovery_min, mjd_discovery_max: float
            Only return objects whose mjd_discovery is between these
            limits.  Specify as MJD.  Wil not return any objects with
            unknown mjd_discovery.

          mjd_start_min, mjd_start_max: float

          mjd_end_min, mjd_end_max: float


        Returns
        -------
          list of DiaObject

          In reality, it may be a list of objects of a subclass of
          DiaObject, but the calling code should not know or depend on
          that, it should treat them all as just DiaObject objects.

        """

        provenance_id = provenance.id if isinstance( provenance, Provenance ) else provenance

        if ( provenance_id is None ) and ( provenance_tag is None ):
            raise ValueError( "Must specify at least one of provenance and provenance_tag" )

        dbclient = SNPITDBClient() if dbclient is None else dbclient

        if provenance_tag is not None:
            prov = cls._parse_tag_and_process( provenance_tag, process=process, provenance_id=provenance_id,
                                               multiple_ok=False, dbclient=dbclient )
            if isinstance( prov, Provenance ):
                provenance_id = prov.id
            elif inspect.isclass( prov ) and issubclass( prov, DiaObject ):
                return prov._find_objects( **kwargs )
            else:
                raise TypeError( f"Unexpected type return {type(prov)} from _parse_tag_and_process; "
                                 f"this shouldn't happen." )

        res = dbclient.send( f"finddiaobjects/{provenance_id}", kwargs )
        return [ DiaObject( **r, _called_from_find_objects=True ) for r in res ]


    @classmethod
    def _find_objects( cls, subset=None, **kwargs ):
        """Class-specific implementation of find_object.

        The implementation here assumes it's a collection that's in the
        Roman SNPIT database.  Other classes might want to implement
        their own version (e.g. DiaObjectOU2024 and DiaObjectManual).

        """
        raise NotImplementedError( f"{cls.__name__} needs to implement _find_objects" )


# ======================================================================

class DiaObjectOU2024( DiaObject ):
    """A transient from the OpenUniverse 2024 sims."""

    def __init__( self, *args, **kwargs ):
        """Don't call a DiaObject or subclass constructor.  Use DiaObject.find_objects."""
        super().__init__( *args, **kwargs )

        # Non-standard fields
        self.host_id = None
        self.gentype = None
        self.model_name = None
        self.start_mjd = None
        self.end_mjd = None
        self.z_cmb = None
        self.mw_ebv = None
        self.mw_extinction_applied = None
        self.av = None
        self.rv = None
        self.v_pec = None
        self.host_ra = None
        self.host_dec = None
        self.host_mag_g = None
        self.host_mag_i = None
        self.host_mag_f = None
        self.host_sn_sep = None
        self.peak_mag_g = None
        self.peak_mag_i = None
        self.peak_mag_f = None
        self.lens_dmu = None
        self.lens_dmu_applied = None
        self.model_params = None

    @classmethod
    def _find_objects( cls, subset=None,
                       name=None,
                       ra=None,
                       dec=None,
                       radius=1.0,
                       mjd_peak_min=None,
                       mjd_peak_max=None,
                       mjd_discovery_min=None,
                       mjd_discovery_max=None,
                       mjd_start_min=None,
                       mjd_start_max=None,
                       mjd_end_min=None,
                       mjd_end_max=None,
                      ):
        if any( i is not None for i in [ mjd_peak_min, mjd_peak_max, mjd_discovery_min, mjd_discovery_max ] ):
            raise NotImplementedError( "DiaObjectOU2024 doesn't support searching on mjd_peak or mjd_discovery" )

        params = {}

        if ( ra is None ) != ( dec is None ):
            raise ValueError( "Pass both or neither of ra/dec, not just one." )

        if ra is not None:
            if radius is None:
                raise ValueError( "ra/dec requires a radius" )
            params['ra'] = float( ra )
            params['dec'] = float( dec )
            params['radius'] = float( radius )

        if name is not None:
            params['id'] = int( name )

        if mjd_start_min is not None:
            params['mjd_start_min'] = float( mjd_start_min )

        if mjd_start_max is not None:
            params['mjd_start_max'] = float( mjd_start_max )

        if mjd_end_min is not None:
            params['mjd_end_min'] = float( mjd_end_min )

        if mjd_end_min is not None:
            params['mjd_end_max'] = float( mjd_end_max )

        simdex = Config.get().value( 'photometry.snappl.simdex_server' )
        res = retry_post( f'{simdex}/findtransients', json=params )
        objinfo = res.json()

        diaobjects = []
        for i in range( len( objinfo['id'] ) ):
            props = { prop: objinfo[prop][i] for prop in
                      [ 'healpix', 'host_id', 'gentype', 'model_name', 'z_cmb', 'mw_ebv', 'mw_extinction_applied',
                        'av', 'rv', 'v_pec', 'host_ra', 'host_dec', 'host_mag_g', 'host_mag_i', 'host_mag_f',
                        'host_sn_sep', 'peak_mag_g', 'peak_mag_i', 'peak_mag_f', 'lens_dmu',
                        'lens_dmu_applied', 'model_params' ] }

            diaobj = DiaObjectOU2024( name=str( objinfo['id'][i] ),
                                      ra=objinfo['ra'][i],
                                      dec=objinfo['dec'][i],
                                      mjd_peak=objinfo['peak_mjd'][i],
                                      mjd_start=objinfo['start_mjd'][i],
                                      mjd_end=objinfo['end_mjd'][i],
                                      properties=props,
                                      _called_from_find_objects=True )
            diaobjects.append( diaobj )

        return diaobjects


# ======================================================================

class DiaObjectManual( DiaObject ):
    """A manually-specified object that's not saved anywhere."""

    def __init__( self, *args, **kwargs ):
        """Don't call a DiaObject or subclass constructor.  Use DiaObject.find_objects."""
        super().__init__( *args, **kwargs )


    @classmethod
    def _find_objects( cls, collection=None, subset=None, **kwargs ):
        if any( ( i not in kwargs ) or ( kwargs[i] is None ) for i in ('name', 'ra', 'dec') ):
            raise ValueError( "finding a manual DiaObject requires all of name, ra, and dec" )

        return [ DiaObjectManual( _called_from_find_objects=True, ra=kwargs["ra"], dec=kwargs["dec"],
                                  name=kwargs["name"] ) ]
