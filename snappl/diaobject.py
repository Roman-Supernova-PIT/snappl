__all__ = [ 'DiaObject', 'DiaObjectOU2024', 'DiaObjectManual' ]

import uuid
import inspect
import simplejson

from snappl.config import Config
from snappl.http import retry_post
from snappl.provenance import Provenance
from snappl.dbclient import SNPITDBClient
from snappl.logger import SNLogger
from snappl.utils import SNPITJsonEncoder, asUUID


class DiaObject:
    """Encapsulate a single supernova (or other transient).

    Standard properties:

    id : UUID; the id of the object if it is in the SNPIT Internal database (or intended to be)
    provenance_id : UUID; the provenance of the object if it is in the SNPIT Internal database (or intended to be)

    name : str; some name assigned by the thing that found it.  These
           will be heterogeneous, may be duplciated for different
           objects, and may be None, so don't rely on this property as
           an identifier.  View it as more a comment field.
    iauname : str; the IAU or TNS name for the object, if know, and if the field has been populated.
              Will be None for most objects.

    ra : ra in degrees (ICRS)
    dec : dec in degrees (ICRS)
          The ra/dec position should be considered an _approximate_
          position only.  It's the position that was saved when the
          object was first found, which means it was probably well
          before peak and likely a low S/N detection.  Use
          get_position() with an appropriate provenance to find a better
          position for an object (if we've calcaulted one).

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

    Usually, don't instantiate one of these directly.  Instead, use
    DiaObject.get_object or DiaObject.find_objects.  If you're trying to
    get a manual object, use provenance_tag 'manual' with
    DiaObject.get_object.  Only instantiate a DiaObject if you're
    writing discovery software and want to create a new one to save to
    the database.

    """

    def __init__( self, id=None, provenance_id=None, ra=None, dec=None, name=None, iauname=None,
                  mjd_discovery=None, mjd_peak=None, mjd_start=None, mjd_end=None, ndetected=1,
                  properties={} ):
        """Only call this constructor if you're making a brand new object.

        If you want to get an existing object, call either DiaObject.get_object or
        DiaObject.find_objects.

        Properties
        ----------
          id : UUID or str, default None.
            The id of the diaobject.  If you leave this as None
            (recommended), a new one will be assigned.

          provenance_id : UUID or str
            The provenance of the object. Required if you're going to save
            this to the database later.

          ra : float
            Decimal degrees.

          dec : float
            Decimal degrees.

          name : str, defanot None
            A name for the object.  These aren't strictly required to be
            unique, but you should strive to make them unique.
            Normally, saving them will raise an error if you end up with
            more than one object in the same provenance with the same
            name.  Ideally, this is something digestable for humans, but
            if you're lazy, you can make this a string version of id and
            then you can be sure it will be unique.  You may also just
            leave it at Hone.

          iauname : str, default None
            The IAU / TNS name for the object.  If given, this must be
            unique within a given provenance, though it's OK if it's
            None.

          mjd_discovery : float
            MJD when the object was found.  Required.

          mjd_peak : float, default None
            MJD when the object is at peak.  Optional

          mjd_start : float, default None
            MJD when the transient starts.  This means that any images
            from an earlier MJD are suitable for use as a template.  Optional.

          mjd_end : float, default None
            MJD when the tranient "ends".  Physically, this is
            meaningless, but practically, it means that any images from
            a later MJD are suitable for use as a template.  Optional.

          ndetected : int, default 1
            The number of times this object has been detected.  When
            creating a new DiaObject, you usually want this to be 1 (the
            default) unless you really know what you're doing.  When a
            DiaObject has been loaded from the database, this will have
            the number in the corresponding database column.

          properties : dict, default {}
            Any optional properties you want to save with the object.

        """
        self.id = asUUID(id) if id is not None else uuid.uuid4()
        self.provenance_id = asUUID(provenance_id) if provenance_id is not None else None
        self.ra = float( ra ) if ra is not None else None
        self.dec = float( dec ) if dec is not None else None
        self.name = str( name ) if name is not None else None
        self.iauname = str( iauname ) if iauname is not None else None
        self.mjd_discovery = float( mjd_discovery ) if mjd_discovery is not None else None
        self.mjd_peak = float( mjd_peak ) if mjd_peak is not None else None
        self.mjd_start = float( mjd_start ) if mjd_start is not None else None
        self.mjd_end = float( mjd_end ) if mjd_end is not None else None
        self.ndetected = int( ndetected ) if ndetected is not None else None
        self.properties = properties


    def save_object( self, association_radius=1.0, dbclient=None ):
        """Save an object to the database.

        Properties
        ----------
          association_radius : float, default 1.0
            If an object of the right provenance already exists in the
            database within this many arcseconds of the object being
            saved, then the new object is not saved.  Make this None
            to never associate, but always save new objects.  (This
            is probably a bad idea.)

          dbclient : SNPITDBClient, default None
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.  If you're going to be saving multiple objects, it's
            more efficient to make one of these once and pass it to each
            call to save_object than it is to let save_object make a new
            one each time.

        Returns
        -------
          dict

          Either the row from the database of the pre-existing object
          (if there was one within association_radius), or the row
          inserted into the database.

        """
        data = { 'association_radius': association_radius }
        for prop in [ 'id', 'provenance_id', 'ra', 'dec', 'name', 'iauname', 'mjd_discovery',
                      'mjd_peak', 'mjd_start', 'mjd_end', 'properties' ]:
            if getattr( self, prop ) is not None:
                data[prop] = getattr( self, prop )

        # Make sure the dict is encoded the way we want
        if 'properties' in data:
            data['properties'] = simplejson.dumps( data['properties'], cls=SNPITJsonEncoder, sort_keys=True )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        senddata = simplejson.dumps( data, cls=SNPITJsonEncoder )
        return dbclient.send( "savediaobject", data=senddata, headers={'Content-Type': 'application/json'} )


    def get_position( self, position_provenance=None, provenance_tag=None, process=None, dbclient=None ):
        """Get updated diaobject position.

        Parameters
        ----------
          position_provenance : UUID or str, default None
            The Provenance of the position (*not* of the object).  Must
            specify either this, or provenance_tag and process, not
            both.

          provenance_tag : str, default None
            The provenance tag for the *position* (not the object).
            Must specify either this or position_provenance.
            provenance_tag requires process.  (If you specify
            position_provenance, this is ignored.)

          process : str, default None
            The process to go with provenance_tag to get the position
            provenance.

          dbclient : SNPITDBClient, default None.
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        Returns
        -------
          dict

          Keys are : id, diaobject_id, provenance_id, ra, ra_err, dec, dec_err, ra_dec_covar, calculated_at

          Note that ra_err, dec_err, and ra_dec_covar might be None.

        """
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        provid = Provenance.get_provenance_id( position_provenance, provenance_tag, process, dbclient=dbclient )
        return dbclient.send( f"getdiaobjectposition/{provid}/{self.id}" )


    @classmethod
    def get_diaobject_positions( cls, diaobject_ids=[], position_provenance=None, provenance_tag=None, process=None,
                                 dbclient=None ):
        """Get updated positions for a list of diaobjects.

        Parameters
        ----------
          diaobject_ids : list of DiaObject, UUID, or str
            The DiaObject (or the ids of same) of the objects whose positions you want.

          position_provenance : UUID or str, default None
            The Provenance of the position (*not* of the object).  Must
            specify either this, or provenance_tag and process, not
            both.

          provenance_tag : str, default None
            The provenance tag for the *position* (not the object).
            Must specify either this or position_provenance.
            provenance_tag requires process.  (If you specify
            position_provenance, this is ignored.)

          process : str, default None
            The process to go with provenance_tag to get the position
            provenance.

          dbclient : SNPITDBClient, default None.
            The connection to the database web server.  If None, a new
            one will be made that logs you in using the information in
            Config.

        Returns
        -------
          dict of diaobjectid: dict

          Each sub-dict has keys id, diaobject_id, provenance_id, ra, ra_err, dec, dec_err, ra_dec_covar, calcualted_at

          Note that ra_err, dec_err, and ra_dec_covar might be None.

        """
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        provid = Provenance.get_provenance_id( position_provenance, provenance_tag, process, dbclient=dbclient )

        objlist = [ o.id if isinstance( o, DiaObject ) else o for o in diaobject_ids ]
        senddata = simplejson.dumps( { 'diaobject_ids': objlist }, cls=SNPITJsonEncoder )
        result = dbclient.send( f"getdiaobjectposition/{provid}", data=senddata,
                                headers={'Content-Type': 'application/json'} )

        return { r['diaobject_id']: r for r in result }


    def save_updated_position( self, position_provenance=None, provenance_tag=None, process=None,
                               ra=None, dec=None, ra_err=None, dec_err=None, ra_dec_covar=None,
                               dbclient=None ):
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        provid = Provenance.get_provenance_id( position_provenance, provenance_tag, process, dbclient=dbclient )

        if ( ra is None ) or ( dec is None ):
            raise ValueError( "ra and dec are required" )

        data = { 'provenance_id': provid,
                 'diaobject_id': self.id,
                 'ra': float(ra),
                 'dec': float(dec),
                 'ra_err': float(ra_err) if ra_err is not None else None,
                 'dec_err': float(dec_err) if dec_err is not None else None,
                 'ra_dec_covar': float(ra_dec_covar) if ra_dec_covar is not None else None
                }
        senddata = simplejson.dumps( data, cls=SNPITJsonEncoder )
        return dbclient.send( "savediaobjectposition", data=senddata, headers={'Content-Type': 'application/json'} )


    @classmethod
    def _parse_tag_and_process( cls, collection='snpitdb', provenance_tag=None, process=None, provenance=None,
                                dbclient=None ):

        """Figure out either the DiaObject subclass, or the Provenance, as appropraite.

        Parameters
        ----------
          collection : str, default 'snpitdb'
            Which collection of objects to search.  Options are:
              * snpitdb : use the Roman SNPIT Internal DB as defined in Config
              * ou2024 : use OpenUniverse2024 truth tables
              * manual : manually create objects

          provenance_tag: str
            The provenance tag to use for objects if collection is
            'snpitdb'.  Invalid if collection is not 'snpitdb'.

          process: str, default None
            The process to use for objects if collection is 'snpitdb'.
            Required if provenance_tag is not None.  Invalid if
            collecton is not 'snpitdb'.

          provenanced: Provenance or UUID or str, default None
            The provenance to use for objects if collection is
            'snpitdb'.  If you specify both provenance_tag and process,
            you don't need to specify this.  You can pass either
            a Provenance object, or just the id.

          dbclient: SNPITDBClient

        Returns
        -------
          If collection is 'snpit', you get back a Provenance if you
          gave one of (provenance_id) or (provenanace_tag and process),
          or None if you didn't.

          Otherwise, you get back a DiaObject subclass.

        """

        subclassmap = { 'ou2024': DiaObjectOU2024,
                        'manual': DiaObjectManual }

        if collection in subclassmap:
            if any( i is not None for i in [ provenance_tag, process, provenance ] ):
                raise ValueError( f"provenance_tag, process, and provenance are all invalid for "
                                  f"collection {collection}" )
            return subclassmap[ collection ]
        elif collection != 'snpitdb':
            raise ValueError( f"Unknown DiaObject collection {collection}" )

        # If we get here, we know we're searching the database

        provid = provenance.id if isinstance( provenance, Provenance ) else provenance

        if ( provenance_tag is None ) != ( process is None ):
            raise ValueError( "Either both or neither of provenance_tag and process must be given with "
                              "collection='snpitdb'." )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        if provenance_tag is not None:
            prov = Provenance.get_provs_for_tag( provenance_tag, process, dbclient=dbclient )
            if ( provid is not None ) and ( str(prov.id) != str(provid) ):
                raise ValueError( f"Provenance tag {provenance_tag} and process {process} returned "
                                  f"provenance {prov.id}, but you specified {provid}" )
        elif isinstance( provenance, Provenance ):
            prov = provenance
        elif provenance is not None:
            prov = Provenance.get_by_id( provid, dbclient=dbclient )
        else:
            prov = None

        return prov


    @classmethod
    def get_object( cls, collection='snpitdb', provenance=None, provenance_tag=None, process=None,
                    name=None, iauname=None, diaobject_id=None,
                    multiple_ok=False, dbclient=None ):
        """Get a DiaObject. from the database.

        RECOMMENDATION: only call this when you know the diaobject_id.
        In that case, pass the diaobject_id, optionally pass a dbclient,
        and optionally pass either provenance, or provenance_tag and
        process.  If you pass provenance info, this function will verify
        that the object you asked for is in that provenance; if you
        don't, it will just return the object you asked for.

        While you can use the name= and iauname= parameters, I recommend
        you don't use this function.  Instead, use find_objects.

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
         collection : str, default 'snpitdb'
            Which collection of objects to search.  Options are:
              * snpitdb : use the Roman SNPIT Internal DB as defined in Config
                          This requires either provenance_id, or provenance_tag and process
              * ou2024 : use OpenUniverse2024 truth tables
              * manual : manually create objects

         provenance: Provenance, UUID, or UUIDifiable str, default None
            The provenance of the object you're looking for.  You don't
            need this if you pass provenance_tag and process, or if you
            pass diaobject_id.  Invalid if collection is not 'snpitdb'.

         provenance_tag : str, default None
           The human-readable provenance tag for the provenance of objects
           you want to dig through.  Requires 'process'.  You must
           specify at least one of provenance_Tag or provenance.
           Invalid if collection is not 'snpitdb'.

         process : str, default None
           The process associated with the provenance_tag (needed to
           determine a unique provenance id).  Needed if provenance_tag
           is not None.

         diaobject_id : UUID or str, default None
           The diaobject_id of the object to get.  Invalid if collection
           is not 'snpitdb'.

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

        prov = cls._parse_tag_and_process( collection=collection, provenance_tag=provenance_tag, process=process,
                                           provenance=provenance, dbclient=dbclient )

        # First see if we're dealing with a subclass
        if inspect.isclass( prov ) and ( issubclass( prov, DiaObject ) ):
            if diaobject_id is not None:
                raise ValueError( f"diaobject_id is invalid for collection {collection}" )
            return prov._get_object( diaobject_id=diaobject_id, name=name, iauname=iauname,
                                     multiple_ok=multiple_ok )

        # If not, then we know we're dealing with the database

        if ( prov is None ) and ( diaobject_id is None ):
            raise ValueError( "Must give one of diaobject_id, provenance_id, or (provenance_tag and process)" )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        if diaobject_id is not None:
            kwargs = dbclient.send( f"getdiaobject/{diaobject_id}" )
            if len(kwargs) == 0:
                raise RuntimeError( f"COuld not find diaobject {diaobject_id}" )
            else:
                if ( prov is not None ) and ( str(kwargs['provenance_id']) != str( prov.id ) ):
                    raise ValueError( f"Error, you asked for object {diaobject_id} in provenance "
                                      f"{prov.id}, but that object is actually in provenance "
                                      f"{kwargs['provenance_id']}" )

                return DiaObject( **kwargs )

        else:
            if ( name is None ) and ( iauname is None ):
                raise ValueError( "Must give one of diaobject_id, name, or iauname" )
            subdict = {}
            if name is not None:
                subdict['name'] = name
            if iauname is not None:
                subdict['iauname'] = iauname
            res = dbclient.send( f"/finddiaobjects/{prov.id}", subdict )
            if len(res) == 0:
                # TODO : make this error message more informative.  (Needs lots of logic
                #   based on what was passed... should probably construct the string
                #   at the top of the function.)
                raise RuntimeError( "Found no objects that match your criteria." )

            if ( name is not None ) and multiple_ok:
                return [ DiaObject( **r ) for r in res ]

            elif len(res) > 1:
                # Another error message that needs to be made more informative
                raise RuntimeError( "More than one object matched your criteria." )

            else:
                return DiaObject( **(res[0]) )



    @classmethod
    def _get_object( cls, name=None, iauname=None, multiple_ok=False ):
        raise NotImplementedError( f"{cls.__name__} isn't able to do _get_object" )


    @classmethod
    def find_objects( cls, collection='snpitdb', provenance=None, provenance_tag=None, process=None,
                      dbclient=None, **kwargs ):
        """Find objects.

        Parameters
        ----------
         collection : str, default 'snpitdb'
            Which collection of objects to search.  Options are:
              * snpitdb : use the Roman SNPIT Internal DB as defined in Config
                          This requires either provenance_id, or provenance_tag and process
              * ou2024 : use OpenUniverse2024 truth tables
              * manual : manually create objects

          provenance : Provenance, UUID, or UUIDifiable str
            The provenance to search.  Must specify either this or
            provenance_tag.  If you specify both, it will verify
            consistency.  Invalid if collection is not 'snpitdb'.

          provenance_tag : str
            The provenance tag to search.  For some provenance tags,
            this goes to a specific subclass (and in that case,
            provenance_id must be None), but for most, it queries the
            Roman SNPIT itnernal database.  Optional if you specify
            provenance.  Invalid if collection is not 'snpitdb'.

          process : str, default None
            The process associated with the provenacne_tag that allows
            the code to determine a unique provenance.  Needed if
            provenance_tag is not None.

          dbclient : SNPITDBClient, default None
            The database web api connection object to use.  If you don't
            specify one, a new one will be made based on what's in your
            configuration.

          diaobject_id : <something>, default None
            The diaobject_id of the object to find.  Only valid if
            collection is 'snpitdb'.

          name : str
            The optional name of the object.  May not be implemented for
            all collections.

          iauname : str
            The TNS/IAU name of the object.  May not be implemented for
            all collections.

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

          order_by: str, default None
            By default, the returned objects are not sorted in any
            particular way.  Put a keyword here to sort by that value.
            Options include 'id', 'provenance_id', 'name', 'iauname',
            'ra', 'dec', 'mjd_discovery', 'mjd_peak', 'mjd_start',
            'mjd_end'.  Not all of these are necessarily useful, and
            some of them may be null for many objects in the database.

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
          list of DiaObject

          In reality, it may be a list of objects of a subclass of
          DiaObject, but the calling code should not know or depend on
          that, it should treat them all as just DiaObject objects.

        """

        prov = cls._parse_tag_and_process( collection=collection, provenance_tag=provenance_tag, process=process,
                                           provenance=provenance, dbclient=dbclient )

        # First see if we're dealing with a subclass
        if inspect.isclass( prov ) and ( issubclass( prov, DiaObject ) ):
            return prov._find_objects( **kwargs )

        # Otherwise, we know we're dealing with the database

        # Do the radius default
        if ( 'ra' in kwargs ) and ( 'radius' not in kwargs ):
            kwargs['radius'] = 1.0

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        res = dbclient.send( f"finddiaobjects/{prov.id}", kwargs )
        return [ DiaObject( **r ) for r in res ]


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
        """Don't call this constructor directly.  Use DiaObject.find_objects."""
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
                       diaobject_id=None,
                      ):
        if any( i is not None for i in [ mjd_peak_min, mjd_peak_max, mjd_discovery_min, mjd_discovery_max ] ):
            raise NotImplementedError( "DiaObjectOU2024 doesn't support searching on mjd_peak or mjd_discovery" )

        if diaobject_id is not None:
            SNLogger.warning("DiaObject OU2024 ignoring diaobject_id parameter in find_objects")

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

        simdex = Config.get().value( 'system.ou24.simdex_server' )
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
                                      properties=props )
            diaobjects.append( diaobj )

        return diaobjects


# ======================================================================

class DiaObjectManual( DiaObject ):
    """A manually-specified object that's not saved anywhere."""

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )


    @classmethod
    def _find_objects( cls, collection=None, subset=None, **kwargs ):
        if any( ( i not in kwargs ) or ( kwargs[i] is None ) for i in ('name', 'ra', 'dec') ):
            raise ValueError( "finding a manual DiaObject requires all of name, ra, and dec" )

        return [ DiaObjectManual( ra=kwargs["ra"], dec=kwargs["dec"], name=kwargs["name"] ) ]
