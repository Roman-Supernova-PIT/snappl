__all__ = [ 'Provenance' ]

import base64
import hashlib
import json
import uuid

from snappl.config import Config
from snappl.utils import SNPITJsonEncoder, asUUID
from snappl.dbclient import SNPITDBClient


class Provenance:
    def __init__( self, process, major, minor, params={}, environment=None, env_major=None, env_minor=None,
                  omitkeys=['system'], keepkeys=None, upstreams=[] ):
        """Instantiate a Provenance

        Once instantiated, will have a property id that holds the UUID
        for this provenance.  This UUID is defined from a md5 hash of
        all the arguments, so will be the same every time you pass the
        same arguments.  (It's convenient that md5sums and UUIDs are
        both 128-bit numbers.)

        Parmaeters
        ----------
          process : str
            The name of the process, e.g. "phrosty", "campari", "import_rapid_alert", etc.

          major : int
            Semantic major version of the code described by process.

          minor : int
            Semantic minor version of the code described by process.

          params : Config or dict, default {}
            Parameters that uniquely define process. This should include
            all parameters that would be the same for all runs on one
            set of data.  So, for instance, for difference imaging
            transient detection software, you would *not* include the
            name of the science image or the name of the transient.
            However, you would include things like configuration
            parameters to SFFT, detection thresholds, and the name and
            parameters of however you decided to figure out which
            template image to use.

            You can also pass a snappl.config.Config object, in which
            case the parameters will be extracted from that.  This
            assumes that the "system" top level key of that Config has
            all, but only, the system-specific stuff.

          environment : int, default None
            Which SNPIT environment did the process use?  TODO: this
            still need to be defined.

          env_major : int, default None
            Semantic major version of environment.

          env_minor : int, default None
            Semantic minor version of environment.

          upstreams : list of Provenance
            Upstream provenances to this provenance.  Only include immediate upstreams;
            no need for upstreams of upstreams, as those will be tracked by the immedaite
            upstreams.  Can also send a single Provenance.

          omitkeys : list of str, default ['system']
            Ignored unless params is a Config object.  In this case,
            these are the keys from the Config to omit and not include
            in the parameters dictionary.  Only one of omitkeys or
            keepkeys can be non-None.

          keepkeys : list of str, default None
            Ignored unless params is a Config object.  In this case,
            only include the specified keys from the Config.

        """
        self.process = str( process )
        self.major = int( major )
        self.minor = int( minor )
        self.environment = int( environment ) if environment is not None else None
        self.env_major = int( env_major ) if env_major is not None else None
        self.env_minor = int( env_minor ) if env_minor is not None else None
        self.upstreams = list( upstreams ) if upstreams is not None else []
        if not all( isinstance( u, Provenance ) for u in self.upstreams ):
            raise TypeError( "upstream must be a list of Provenance" )
        # Sort upstreams by id so they are in a reproducible order
        self.upstreams.sort( key=lambda x: x.id )

        if isinstance( params, Config ):
            self.params = params.dump_to_dict_for_params( omitkeys=omitkeys, keepkeys=keepkeys )
        elif isinstance( params, dict ):
            self.params = params
        else:
            raise TypeError( f"params must be a Config or a dict, not a {type(params)}" )

        self.update_id()

    def spec_dict( self ):
        return { 'process': self.process,
                 'major': self.major,
                 'minor': self.minor,
                 'environment': self.environment,
                 'env_major': self.env_major,
                 'env_minor': self.env_minor,
                 'params': self.params,
                 'upstream_ids': [ str(u.id) for u in self.upstreams ]
                }

    def recursive_dict( self, dbclient=None ):
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        rval = self.spec_dict()
        del rval['upstream_ids']
        rval['upstreams'] = [ u.recursive_dict( dbclient=dbclient ) for u in self.upstreams ]

        return rval

    def update_id( self ):
        """Update self.id based on stored properties.

        If you change any of the properties of the object that define
        the Provenance, you must call this to make the id property
        correct.  Probably this is a bad idea; you should view
        Provenance objects as immutable and not change them after you
        make them.

        """
        # Note : we need the sort_keys here, because while python dictionaries are
        #   ordered, json dictionaries are NOT.  This means that the key order is
        #   going to get munged somewhere along the line.  (If not in our string
        #   encoding, then when saved to PostgreSQL JSONB objects.)  So that the id
        #   is reproducible, we have to punt on the ordering of the params, and
        #   sort the keys when writing out the JSON string so that they always come
        #   in the same order regardless of whether it came from an initial python
        #   dict, or if it came through JSON with unordered dictionaries.
        spec = json.dumps( self.spec_dict(), cls=SNPITJsonEncoder, sort_keys=True ).encode( "utf-8" )
        barf = base64.standard_b64encode( spec )
        md5sum = hashlib.md5( barf )
        self.id = uuid.UUID( md5sum.hexdigest() )


    def save_to_db( self, tag=None, replace_tag=False, exists=None, dbclient=None ):
        """Save this provenance to the database.

        Will call self.update_id() as a side effect, just to make sure
        the right ID is saved to the database.

        If you save a provenance with upstreams, those upstreams must
        have previously been saved themselves.  (So, you can't create
        a whole provenance tree and have the whole thing saved in
        one call; it doesn't recurse.)

        Parmaeters
        ----------
          tag : str, default None
            Add this provenance to this provenance tag for this process.

          replace_tag : bool, default False
            Ignored if tag is None.  If tag is set, but a provenance
            already exists for this process and tag, then normally
            that's an error.  If replace_tag is True, delete the old
            provenance associated with the tag and set the new
            provenance.

          exists : bool, default None
            If None, and the provenance already exists in the database,
            do nothing.  If False, and the provenance already exists in
            the database, raise an exception.  If True, and the
            provenance doesn't already exist in the database, raise an
            exception.  It doesn't make a lot of sense, usually, to call
            this method with exists=True.

          dbclient: snappl.dbclient.SNPITDBClient
            This is needed to talk to the Roman SNPIT database web
            server.  If not given, will construct one based on config.

        """

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        self.update_id()
        savedprov = self.get_by_id( self.id, dbclient=dbclient, return_none_if_not_exists=True )

        if ( savedprov is None ) and ( exists is not None ) and exists:
            raise RuntimeError( f"Provenance {self.id} doesn't exist in the database, and exists is True; "
                                f"why are you calling save_to_db???" )
        if ( savedprov is not None ) and ( exists is not None ) and ( not exists ):
            raise RuntimeError( f"Error saving provenance {self.id}; it already exists in the database." )

        if ( savedprov is None ) or ( tag is not None ):
            res = dbclient.send( "createprovenance",
                                 { 'id': str(self.id),
                                   'process': self.process,
                                   'major': self.major,
                                   'minor': self.minor,
                                   'environment': self.environment,
                                   'env_major': self.env_major,
                                   'env_minor': self.env_minor,
                                   'params': self.params,
                                   'upstream_ids': [ str(u.id) for u in self.upstreams ],
                                   'tag': tag,
                                   'exist_ok': True,
                                   'replace_tag': replace_tag } )
            if res['status'] != 'ok':
                raise RuntimeError( f"Something went wrong saving provenance {self.id} to the databse." )


    @classmethod
    def get( cls, process, major, minor, params={}, environment=None, env_major=None, env_minor=None,
             upstreams=[], exists=None, savetodb=False, dbclient=None ):
        """Get a Provenance based on properties.

        Arguments are the same as are passed to the Provenance constructor, plus:

        Parameters
        ----------
          process, major, minor, params, environment, env_major, env_minor : varied
            These are the same as what's passed to the Provenance constructor

          exists : bool, default None
            Normally, you get back the provenance you ask for.  (This
            is, depending on savetodb, just the same as instantiating a
            Provenance object.)  However, if exists is True, then it
            will raise an exception if the provenance isn't already
            saved to the database.  If exists is False, then it will
            raise an exception if the provenance *is* already saved to
            the database.  (Setting exists=False mostly only makes sense
            when setting savetodb to True.)

          savetodb : bool, default False
            By default, you get the Provenance you ask for, but
            thedatabse is not changed.  Set this to True to save the
            provenance to the database.  If savetodb is True and exists
            is True, then nothing is saved, because either the
            provenance already exists, or an exception was raised.  If
            savetodb is True and exists is None, then the provenance
            will be saved to the database if it doesn't already exist.
            If savetodb is True and exists is False, an exception will
            be raised if the provenance is already in the database,
            otherwise the new provenance will be saved.

          dbclient: snappl.dbclient.SNPITDBClient
            This is needed to talk to the Roman SNPIT database web
            server.  If not given, will construct one based on config.

        """

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        prov = cls( process, major, minor, params=params, environment=environment,
                    env_major=env_major, env_minor=env_minor, upstreams=upstreams )
        if exists:
            try:
                existing = cls.get_by_id( prov.id, dbclient=dbclient )
            except Exception:
                raise RuntimeError( f"Requested provenance {prov.id} does not exist in the database." )

            existing.update_id()
            if existing.id != prov.id:
                raise RuntimeError( "Existing provenance id is wrong in the database!  This should not happen!" )

        if savetodb:
            try:
                prov.save_to_db( exists=exists, dbclient=dbclient )
            except Exception:
                if ( exists is not None ) and ( not exists ):
                    raise
                # Otherwise, the exception just means it was already there, so we don't care

        return prov

    @classmethod
    def parse_provenance( cls, provdict ):
        kwargs = { k: provdict[k] for k in [ 'process', 'major', 'minor', 'params',
                                             'environment', 'env_major', 'env_minor' ]
                  }
        kwargs[ 'upstreams' ] = [ cls.parse_provenance(p) for p in provdict['upstreams'] ]
        prov = cls( **kwargs )
        if str(prov.id) != provdict['id']:
            raise ValueError( f"Got provenance {provdict['id']} back from the database, but when I rebuilt it, "
                              f"I got {prov.id}.  This is bad." )
        return prov


    @classmethod
    def get_by_id( cls, provid, dbclient=None, return_none_if_not_exists=False ):
        """Return a Provenance pulled from the database.

        Raises an exception if it does not exist.

        Parameters
        ----------
          provid: UUID
             The ID to fetch

          dbclient: snappl.dbclient.SNPITDBClient
            This is needed to talk to the Roman SNPIT database web
            server.  If not given, will construct one based on config.

          return_none_if_not_exists : bool, default False

        Returns
        -------
          Provenance

          If return_none_if_not_exists is True, then None will be
          returned if the provenance does not exist in the database.  If
          return_none_if_not_exists is False (the default), then an
          exception will be raised if the provenance does not exist in
          the database.

        """

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        rval = dbclient.send( f"getprovenance/{provid}" )
        if ( 'status' in rval ) and ( rval['status'] == f'No such provenance {provid}' ):
            if return_none_if_not_exists:
                return None
            else:
                raise ValueError( f"No such provenance {provid}" )
        else:
            return cls.parse_provenance( rval )



    @classmethod
    def get_provs_for_tag( cls, tag, process=None, dbclient=None ):
        """Get the Provenances for a given provenance tag.

        Parameters
        ----------
          tag : str
            The provenance tag to search

          process : str, default None
            The process to get provenances for.  If None, will get all
            provenances associated with the tag.

          dbclient: snappl.dbclient.SNPITDBClient
            This is needed to talk to the Roman SNPIT database web
            server.  If not given, will construct one based on config.

        Returns
        -------
          Provenance or list of Provenance

          If process is not None, you get back a Provenance (or an
          exception is raised if the provenance wasn't found).  If
          process is None, you get back a list of Provenance.

        """
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        if process is not None:
            result = dbclient.send( f"/getprovenance/{tag}/{process}" )
            if 'status' in result:
                raise ValueError( result['status'] )
            return cls.parse_provenance( result )
        else:
            return [ cls.parse_provenance(p) for p in dbclient.send( f"/provenancesfortag/{tag}" ) ]


    @classmethod
    def get_provenance_id( cls, provenance, provenance_tag, process, dbclient=None ):
        """Return a Provenance ID from either a provenance, or a provenance_tag and process.

        Parameters
        ----------
          provenance: Provenance, str, or None
            If a Provenance, then this provenance's ID is returned.
            Otherwise, if this is not None, return this.  If None, then
            fall back to looking at provenance_tag and process.

          provenance_tag : str or None

          process: str or None

        Returns
        -------
          UUID

        """

        if isinstance( provenance, Provenance ):
            return provenance.id

        if provenance is not None:
            return asUUID( provenance )

        if provenance_tag is None:
            raise ValueError( "Must pass either provenacne or provenance_tag" )

        if process is None:
            raise ValueError( "provenance_tag requires process" )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        prov = Provenance.get_provs_for_tag( provenance_tag, process, dbclient=dbclient )
        return prov.id
