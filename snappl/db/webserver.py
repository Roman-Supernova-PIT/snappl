__all__ = [ 'setup_flask_app' ]

import io
import re
import uuid
import pathlib
import textwrap

import flask
import flask_session
from psycopg import sql
import numpy as np

from rkwebutil import rkauth_flask

from snappl.config import Config
from snappl.db import db
from snappl.db.baseview import BaseView
from snappl.logger import SNLogger
from snappl.utils import asUUID


# ======================================================================

def setup_flask_app( application ):
    global urls

    application.config.from_mapping(
        SECRET_KEY=Config.get().value( 'system.webserver.flask_secret_key' ),
        SESSION_COOKIE_PATH='/',
        SESSION_TYPE='filesystem',
        SESSION_PERMANENT=True,
        SESSION_USE_SIGNER=True,
        SESSION_FILE_DIR=Config.get().value( 'system.webserver.sessionstore' ),
        SESSION_FILE_THRESHOLD=1000,
    )

    _server_session = flask_session.Session( application )

    dbhost, dbport, dbname, dbuser, dbpasswd = db.get_connect_info()
    rkauth_flask.RKAuthConfig.setdbparams(
        db_host=dbhost,
        db_port=dbport,
        db_name=dbname,
        db_user=dbuser,
        db_password=dbpasswd,
        email_from = Config.get().value( 'system.webserver.emailfrom' ),
        email_subject = 'roman-snpit-db password reset',
        email_system_name = 'roman-snpit-db',
        smtp_server = Config.get().value( 'system.webserver.smtpserver' ),
        smtp_port = Config.get().value( 'system.webserver.smtpport' ),
        smtp_use_ssl = Config.get().value( 'system.webserver.smtpusessl' ),
        smtp_username = Config.get().value( 'system.webserver.smtpusername' ),
        smtp_password = Config.get().value( 'system.webserver.smtppassword' )
    )
    application.register_blueprint( rkauth_flask.bp )

    usedurls = {}
    for url, cls in urls.items():
        if url not in usedurls.keys():
            usedurls[ url ] = 0
            name = url
        else:
            usedurls[ url ] += 1
            name = f'{url}.{usedurls[url]}'

        application.add_url_rule (url, view_func=cls.as_view(name), methods=['GET', 'POST'], strict_slashes=False )


# ======================================================================

class MainPage( BaseView ):
    def dispatch_request( self ):
        return flask.render_template( "romansnpitdb.html" )


# ======================================================================

class TestEndpoint( BaseView ):
    # This one is used in one of the snappl tests

    def dispatch_request( self, param=None ):
        resp = { 'param': param }
        if flask.request.is_json:
            resp['json'] = flask.request.json
        return resp


# ======================================================================

class BaseProvenance( BaseView ):
    def get_upstreams( self, prov, dbcon ):
        rows, cols = dbcon.execute( "SELECT p.* FROM provenance p "
                                    "INNER JOIN provenance_upstream u ON u.upstream_id=p.id "
                                    "WHERE u.downstream_id=%(id)s",
                                    { 'id': prov['id'] } )
        if ( rows is None ) or ( len(rows) == 0 ):
            prov[ 'upstreams' ] = []
        else:
            prov[ 'upstreams' ] = [ { cols[i]: row[i] for i in range( len(cols) ) } for row in rows ]
            for prov in prov[ 'upstreams' ]:
                self.get_upstreams( prov, dbcon )
            # Sort prov['upstreams'] by id, because that's the standard we use to make it reproducible
            prov[ 'upstreams' ].sort( key=lambda x: x['id'] )


    def tag_provenance( self, dbcon, tag, process, provid, replace=False ):
        rows, cols = dbcon.execute( "SELECT * FROM provenance_tag WHERE tag=%(tag)s AND process=%(process)s",
                                    { 'tag': tag, 'process': process } )
        if len(rows) > 0:
            if len(rows) > 1:
                raise RuntimeError( f"Database corruption error!  >1 entry with tag {tag} "
                                    f"and process {process}" )
            cols = { c: i for i, c in enumerate(cols) }
            if str(rows[0][cols['provenance_id']]) == str(provid):
                # Hey, right thing is already tagged!
                return
            else:
                if replace:
                    dbcon.execute( "DELETE FROM provenance_tag WHERE tag=%(tag)s AND process=%(process)s",
                                   { 'tag': tag, 'process': process } )
                else:
                    raise RuntimeError( f"Error, there already exists a provenance for tag {tag} and "
                                        f"process {process}" )

        dbcon.execute( "INSERT INTO provenance_tag(tag, process, provenance_id) "
                       "VALUES (%(tag)s, %(proc)s, %(id)s)",
                       { 'tag': tag, 'proc': process, 'id': provid } )
        dbcon.commit()



# ======================================================================

class GetProvenance( BaseProvenance ):
    def do_the_things( self, provid, process=None ):
        with db.DBCon() as con:
            if process is None:
                rows, cols = con.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': provid } )
            else:
                rows, cols = con.execute( "SELECT p.* FROM provenance p "
                                          "INNER JOIN provenance_tag t ON p.id=t.provenance_id "
                                          "WHERE t.process=%(process)s AND t.tag=%(tag)s",
                                          { 'process': process, 'tag': provid } )
            if len(rows) == 0:
                if process is None:
                    return { 'status': f'No such provenance {provid}' }
                else:
                    return { 'status': f'No provenance for tag {provid} and process {process}' }
            if len(rows) > 1:
                return ( f"Database corruption!  More than one provenance {provid}"
                         f"{'' if process is None else f' for process {process}'}!" ), 422
            prov = { cols[i]: rows[0][i] for i in range( len(cols) ) }
            self.get_upstreams( prov, con )

        return prov


# ======================================================================

class CreateProvenance( BaseProvenance ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected JSON payoad", 422
        data = flask.request.json

        if 'upstreams' in data:
            upstream_ids = [ p['id'] for p in data['upstreams'] ]
            del data['upstreams']
        elif 'upstream_ids' in data:
            upstream_ids = data['upstream_ids']
            del data['upstream_ids']
        else:
            upstream_ids = []

        tag = None
        replace_tag = None
        if 'tag' in data:
            tag = data['tag']
            del data['tag']
        if 'replace_tag' in data:
            replace_tag = data['replace_tag']
            del data['replace_tag']

        existok = False
        if 'exist_ok' in data:
            existok = data['exist_ok']
            del data['exist_ok']

        prov = db.Provenance( **data )
        with db.DBCon() as dbcon:
            rows, _cols = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': data['id'] } )
            if len(rows) == 0:
                prov.insert( dbcon=dbcon.con, nocommit=True, refresh=False )
                for uid in upstream_ids:
                    dbcon.execute( "INSERT INTO provenance_upstream(downstream_id,upstream_id) "
                                   "VALUES (%(down)s,%(up)s)",
                                   { 'down': prov.id, 'up': uid } )
            elif not existok:
                return f"Error, provenance {data['id']} already exists", 422

            if tag is not None:
                self.tag_provenance( dbcon, tag, data['process'], data['id'], replace=replace_tag )

            dbcon.commit()

        return { "status": "ok",
                 "provenance_id": str( prov.id ) }


# ======================================================================

class TagProvenance( BaseProvenance ):
    def do_the_things( self, tag, process, provid, replace=0 ):
        with db.DBCon() as dbcon:
            self.tag_provenance( dbcon, tag, process, provid, replace )
        return { "status": "ok" }


# ======================================================================

class ProvenancesForTag( BaseProvenance ):
    def do_the_things( self, tag ):
        with db.DBCon() as dbcon:
            rows, cols = dbcon.execute( "SELECT p.* FROM provenance p "
                                        "INNER JOIN provenance_tag t ON p.id=t.provenance_id "
                                        "WHERE t.tag=%(tag)s",
                                        { 'tag': tag } )
            provs = [ { cols[i]: row[i] for i in range( len(cols) ) } for row in rows ]
            for prov in provs:
                self.get_upstreams( prov, dbcon )

        return provs


# ======================================================================

class GetDiaObject( BaseView ):
    def do_the_things( self, diaobjectid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM diaobject WHERE id=%(id)s", { 'id': diaobjectid } )

        if len(rows) > 1:
            return f"Database corruption; multiple diaobjects with id {diaobjectid}", 422
        elif len(rows) == 0:
            return f"Object not found: {diaobjectid}", 422
        else:
            return rows[0]


# ======================================================================

class FindDiaObjects( BaseView ):
    def do_the_things( self, provid=None ):
        equalses = { 'id', 'name', 'iauname' }
        minmaxes = { 'ra', 'dec', 'ndetected', 'mjd_discovery', 'mjd_peak', 'mjd_start', 'mjd_end' }
        allowed_keys = { 'provenance', 'provenance_tag', 'process', 'radius', 'order_by', 'limit', 'offset' }
        allowed_keys = allowed_keys.union( equalses )
        allowed_keys = allowed_keys.union( minmaxes )
        data = self.check_json_keys( set(), allowed_keys, minmax_keys=minmaxes )

        q = sql.SQL( "SELECT * FROM diaobject WHERE " )

        with db.DBCon( dictcursor=True ) as dbcon:
            if provid is not None:
                if any( i in data for i in [ 'provenance', 'provenance_tag', 'process' ] ):
                    return ( "Error, cannot pass provenance information in POST data when passing a "
                             "provenance id in the URL." )
            else:
                data, provid = self.get_provenance_id( data, dbcon=dbcon )

            conditions = [ sql.SQL( "provenance_id=%(provid)s" ) ]
            subdict = { 'provid': provid }

            ( data,
              conditions,
              subdict,
              finalclause ) = self.make_sql_conditions( data,
                                                        equalses=equalses,
                                                        minmaxes=minmaxes,
                                                        q3ctriplets=[ ('ra', 'dec', 'radius') ],
                                                        conditions=conditions,
                                                        subdict=subdict
                                                       )
            if len(data) != 0:
                return f"Error, unknown parameters: {list(data.keys())}", 422

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class SaveDiaObject( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected diaobject data in json POST data, didn't get any.", 422

        data = flask.request.json
        needed_keys = { 'provenance_id', 'ra', 'dec', 'mjd_discovery' }
        allowed_keys = { 'id', 'iauname', 'name', 'mjd_peak', 'mjd_start',
                         'mjd_end', 'properties', 'association_radius' }.union( needed_keys )
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( allowed_keys ):
            return f"Unknown keys: {passed_keys - allowed_keys}", 422
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {needed_keys - passed_keys}", 422
        if any( data[i] is None for i in needed_keys ):
            return f"None of the necessary keys can be None: {needed_keys}"

        if 'id' not in data:
            data['id'] = uuid.uuid4()

        association_radius = None
        if 'association_radius' in data:
            association_radius = data['association_radius']
            del data['association_radius']

        duplicate_ok = False
        if 'dupliate_ok' in data:
            duplicate_ok = data['duplicate_ok']
            del data['duplicate_ok']

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM diaobject WHERE id=%(id)s", { 'id': data['id'] } )
            if len(rows) != 0:
                return f"diaobject id {data['id']} already exists!", 422

            dbcon.execute( "LOCK TABLE diaobject" )

            # Check to see if there's an existing object (oldobj) within
            #   association_radius of this new object.  If so,
            #   dont' make a new object, just return the old object.
            oldobj = None
            if association_radius is not None:
                rows = dbcon.execute( "SELECT * FROM ("
                                      "  SELECT o.*,q3c_dist(%(ra)s,%(dec)s,o.ra,o.dec) AS dist "
                                      "  FROM diaobject o "
                                      "  WHERE o.provenance_id=%(prov)s "
                                      "  AND q3c_radial_query(o.ra,o.dec,%(ra)s,%(dec)s,%(rad)s) "
                                      ") subq "
                                      "ORDER BY dist LIMIT 1",
                                      { 'prov': data['provenance_id'], 'ra': data['ra'], 'dec': data['dec'],
                                        'rad': association_radius / 3600. } )
                if len(rows) > 0:
                    oldobj = rows[0]
                    del oldobj['dist']

            if ( oldobj is None ) and ( 'name' in data ) and ( not duplicate_ok ):
                rows = dbcon.execute( "SELECT * FROM diaobject WHERE name=%(name)s AND provenance_id=%(prov)s",
                                      { 'name': data['name'], 'prov': data['provenance_id'] } )
                if len(rows) > 0:
                    return ( f"diaobject with name {data['name']} in provenance {data['provenance_id']} "
                             f"already exists!", 422 )

            if oldobj is not None:
                # TODO THIS IS TERRIBLE RIGHT NOW!
                # We need more database structure to do this right.  We want
                #   to make sure that this isn't a detection from the same image
                #   that was one of the previous detections.  For now, though,
                #   just do this as the simplest stupid thing to do.
                oldobj['ndetected'] += 1
                dbcon.execute( "UPDATE diaobject SET ndetected=%(ndet)s WHERE id=%(id)s",
                               { 'id': oldobj['id'], 'ndet': oldobj['ndetected'] } )
                dbcon.commit()
                return oldobj

            else:
                # Although this looks potentially Bobby Tablesish, the fact that we made
                #   sure that data only included allowed keys above makes this not subject
                #   to SQL injection attacks.
                varnames = ','.join( str(k) for k in data.keys() )
                varvals = ','.join( f'%({k})s' for k in data.keys() )
                q = f"INSERT INTO diaobject({varnames}) VALUES ({varvals})"
                dbcon.execute( q, data )
                rows = dbcon.execute( "SELECT * FROM diaobject WHERE id=%(id)s", { 'id': data['id'] } )
                if len(rows) == 0:
                    return f"Error, saved diaobject {data['id']}, but it's not showing up in the database", 422
                elif len(rows) > 1:
                    return f"Database corruption, more than one diaobject with id={data['id']}", 422
                else:
                    dbcon.commit()
                    return rows[0]


# ======================================================================

class GetDiaObjectPosition( BaseView ):
    def do_the_things( self, provid, diaobjectid=None ):
        with db.DBCon( dictcursor=True ) as dbcon:
            if diaobjectid is not None:
                rows = dbcon.execute( "SELECT * FROM diaobject_position "
                                      "WHERE provenance_id=%(provid)s AND diaobject_id=%(objid)s",
                                      { 'provid': provid, 'objid': diaobjectid } )
                if len(rows) == 0:
                    return "No postion for diaobject {diaobjectid} in with position provenance {provid}", 422
                return rows[0]

            if not flask.request.is_json:
                return "getdiaobjectposition/<provid> requires JSON POST data", 422
            data = flask.request.json
            if 'diaobject_ids' not in data:
                return "getdiaobjectposition/<provid> requres diaobject_ids in POST JSON dict", 422

            rows = dbcon.execute( "SELECT * FROM diaobject_position "
                                  "WHERE provenance_id=%(provid)s AND diaobject_id=ANY(%(objids)s)",
                                  { 'provid': provid, 'objids': data['diaobject_ids'] } )
            return rows


# ======================================================================

class SaveDiaObjectPosition( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected diaobject position data in json POST data, didn't get any.", 422

        data = flask.request.json
        needed_keys = { 'provenance_id', 'diaobject_id', 'ra', 'dec' }
        allowed_keys = { 'id', 'ra_err', 'dec_err', 'ra_dec_covar' }.union( needed_keys )
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( allowed_keys ):
            return f"Unknown keys: {passed_keys - allowed_keys}", 422
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {passed_keys - needed_keys}", 422
        if any( data[i] is None for i in needed_keys ):
            return f"None of the necessary keys can be None: {needed_keys}"

        if ( 'id' not in data ) or ( data['id'] is None ):
            data['id'] = uuid.uuid4()

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': data['provenance_id'] } )
            if len(rows) == 0:
                return f"Unknown provenance {data['provenance_id']}", 422

            dbcon.execute( "LOCK TABLE diaobject_position" )

            rows = dbcon.execute( "SELECT * FROM diaobject_position "
                                  "WHERE diaobject_id=%(objid)s AND provenance_id=%(provid)s",
                                  { 'objid': data['diaobject_id'], 'provid': data['provenance_id'] } )
            if len(rows) != 0:
                return ( f"Object {data['diaobject_id']} already has a position "
                         f"with provenance {data['provenance_id']}" ), 422

            pos = db.DiaObjectPosition( dbcon=dbcon, **data )
            # This insert will commit, which will end the transaction
            pos.insert( dbcon=dbcon )

            return pos.to_dict( dbcon=dbcon )


# ======================================================================

class GetL2Image( BaseView ):
    def do_the_things( self, imageid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM l2image WHERE id=%(id)s", { 'id': imageid } )

        if len( rows ) > 1:
            return f"Database corruption: multiple l2image with id {imageid}", 422
        elif len( rows ) == 0:
            return f"L2image not found: {imageid}", 422
        else:
            return rows[0]


# ======================================================================

class FindL2Images( BaseView ):
    def do_the_things( self ):
        equalses = { 'id', 'observation_id', 'sca', 'band', 'filepath', 'format', 'processing_status',
                     'program' }
        minmaxes = { 'ra', 'dec', 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                     'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                     'width', 'height', 'mjd', 'exptime', 'position_angle' }
        allowed_keys = { 'provenance', 'provenance_tag', 'process', 'order_by', 'limit', 'offset' }
        allowed_keys = allowed_keys.union( equalses )
        allowed_keys = allowed_keys.union( minmaxes )
        data = self.check_json_keys( set(), allowed_keys, minmax_keys=minmaxes )

        with db.DBCon( dictcursor=True ) as dbcon:
            conditions = []
            subdict = {}
            if ( 'provenance' in data ) or ( 'provenance_tag' in data ):
                data, provid = self.get_provenance_id( data, dbcon=dbcon )
                conditions = [ sql.SQL( "provenance_id=%(provid)s" ) ]
                subdict = { 'provid': provid }
            elif 'process' in data:
                return "process needs provenance_tag", 422
            # With no provenance given, the images of every provenance are searched.

            ( data,
              conditions,
              subdict,
              finalclause ) = self.make_sql_conditions( data,
                                                        equalses=equalses,
                                                        minmaxes=minmaxes,
                                                        cornerpolypairs=[ ('ra', 'dec') ],
                                                        conditions=conditions,
                                                        subdict=subdict
                                                       )
            if len(data) != 0:
                return f"Error, unknown parameters: {data.keys()}", 422

            q = sql.SQL( "SELECT * FROM l2image" )
            if conditions != sql.SQL( "" ):
                q += sql.SQL( " WHERE " ) + conditions
            return dbcon.execute( q + finalclause, subdict )


# ======================================================================

class SaveL2Image( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected image info in json POST; didn't get any.", 422

        needed_keys = { 'id', 'provenance_id', 'band', 'ra', 'dec',
                        'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                        'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                        'filepath', 'format', 'mjd', 'exptime' }
        allowed_keys = needed_keys.union( { 'observation_id', 'sca', 'extension', 'width', 'height',
                                            'properties', 'position_angle', 'processing_status',
                                            'program', 'filedate' } )
        data = self.check_json_keys( needed_keys, allowed_keys )
        keysql, subs = self.build_sql_insert( data.keys() )
        q = sql.SQL( "INSERT INTO l2image(" ) + keysql + sql.SQL( ") VALUES (" ) + sql.SQL( subs ) + sql.SQL( ")" )

        with db.DBCon( dictcursor=True ) as dbcon:
            dbcon.execute( q, data )
            row = dbcon.execute( "SELECT * FROM l2image WHERE id=%(id)s", { 'id': data['id'] } )
            dbcon.commit()

        return row


# ======================================================================

class BulkSaveL2Images( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected image info in json POST; didn't get json.", 422

        needed_keys = { 'id', 'provenance_id', 'band', 'ra', 'dec',
                        'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                        'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                        'filepath', 'format', 'mjd', 'exptime' }
        allowed_keys = needed_keys.union( { 'observation_id', 'sca', 'extension', 'width', 'height',
                                            'properties', 'position_angle', 'processing_status',
                                            'program', 'filedate' } )
        data = self.check_json_keys( needed_keys, allowed_keys )

        # ?ignore_conflicts=1 skips the images whose id is already in the table instead of
        #   failing the whole batch, so that a caller can send the same images again.
        ignore_conflicts = flask.request.args.get( 'ignore_conflicts', '' ).lower() in ( '1', 'true', 'yes' )

        try:
            if ignore_conflicts:
                # ON CONFLICT (id) DO NOTHING; returns the number of rows that were inserted.
                ninserted = db.L2Image.bulk_insert_or_upsert( data )
                return { "status": "ok", "inserted": ninserted }
            # Passing assume_no_conflict=True here.  That's a poorly named parameter.
            #   What we want is for it to error out if there is a conflict.
            db.L2Image.bulk_insert_or_upsert( data, assume_no_conflict=True )
        except Exception as ex:
            return f"Got an exception trying to bulk insert images: {ex}", 422

        return { "status": "ok" }


# ======================================================================

class SetL2ImageStatus( BaseView ):
    """Move l2images from one processing_status to another.

    Only the listed images that are currently in from_status change, so a caller that is too
    late (the image has already moved on) does not overwrite the newer status.  Returns the
    ids that did change.
    """

    _statuses = ( 'standby', 'ingested', 'queued', 'processing', 'done', 'failed' )

    def do_the_things( self ):
        data = self.check_json_keys( { 'ids', 'from_status', 'to_status' },
                                     { 'ids', 'from_status', 'to_status' } )
        for key in [ 'from_status', 'to_status' ]:
            if data[key] not in self._statuses:
                return f"Unknown {key} {data[key]!r}; must be one of {self._statuses}", 422
        if not isinstance( data['ids'], list ):
            return "ids must be a list of l2image ids", 422
        if len( data['ids'] ) == 0:
            return { 'updated': [] }

        q = ( "UPDATE l2image SET processing_status=%(to_status)s, status_updated_at=NOW(), "
              "  queued_at=CASE WHEN %(to_status)s='queued' THEN NOW() ELSE queued_at END "
              "WHERE id=ANY(%(ids)s::uuid[]) AND processing_status=%(from_status)s "
              "RETURNING id" )
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( q, data )
            dbcon.commit()

        return { 'updated': [ str( row['id'] ) for row in rows ] }


# ======================================================================

class SaveSegmentationMap( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected segmap info in json POST; didn't get any.", 422

        needed_keys = { 'id', 'provenance_id', 'band', 'ra', 'dec', 'filepath', 'format' }
        for which in [ 'ra', 'dec' ]:
            for corner in [ '00', '01', '10', '11' ]:
                needed_keys.add( f"{which}_corner_{corner}" )
        allowed_keys = { 'width', 'height', 'l2image_id' }.union( needed_keys )
        data = self.check_json_keys( needed_keys, allowed_keys )

        keysql, subs = self.build_sql_insert( data.keys() )
        q = sql.SQL( "INSERT INTO segmap(" ) + keysql + sql.SQL( ") VALUES (" ) + sql.SQL( subs ) + sql.SQL( ")" )

        with db.DBCon( dictcursor=True ) as dbcon:
            dbcon.execute( q, data )
            row = dbcon.execute( "SELECT * FROM segmap WHERE id=%(id)s", {'id': data['id']} )
            dbcon.commit()

        return row


# ======================================================================

class GetSegmentationMap( BaseView ):
    def do_the_things( self, segmapid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM segmap WHERE id=%(id)s", {'id': segmapid} )

        if len(rows) == 0:
            return f"Segmentation map {segmapid} not found.", 422
        elif len(rows) > 1:
            return f"Database corruption, multiple segmaps with id {segmapid}.  This should never happen.", 422
        else:
            return rows[0]


# ======================================================================

class FindSegmentationMap( BaseView ):
    def do_the_things( self ):
        equalses = { 'id', 'band', 'filepath', 'format', 'l2image_id' }
        minmaxes = { 'ra', 'dec', 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                     'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11', 'width', 'height' }
        allowed_keys = { 'provenance', 'provenance_tag', 'process', 'order_by', 'limit', 'offset' }
        allowed_keys = allowed_keys.union( equalses )
        allowed_keys = allowed_keys.union( minmaxes )
        data = self.check_json_keys( set(), allowed_keys, minmax_keys=minmaxes )

        q = sql.SQL( "SELECT * FROM segmap WHERE " )

        with db.DBCon( dictcursor=True ) as dbcon:
            data, provid = self.get_provenance_id( data, dbcon=dbcon )
            conditions = [ sql.SQL( "provenance_id=%(provid)s" ) ]
            subdict = { 'provid': provid }

            ( data,
              conditions,
              subdict,
              finalclause ) = self.make_sql_conditions( data,
                                                        equalses=equalses,
                                                        minmaxes=minmaxes,
                                                        cornerpolypairs=[ ('ra', 'dec') ],
                                                        conditions=conditions,
                                                        subdict=subdict
                                                       )
            if len(data) != 0:
                return f"Error, unknown parameters: {data.keys()}", 422

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class SaveDiaForcedSource( BaseView ):
    """Create a new diaforcedsource.

    Call api endpoint /savediaforcedsource

    POST data must be a json dictionary with keys:
       id: str of UUID
         (optional) the uuid of the diaforcedsource.  If one is not
         given, a new one will be generated.

       provenance_id: str of UUID
         provenance id for diaforcedsource

       diaobject_id: str of UUID
         the object this is a measurement of

       diaobject_position_id: str of UUID  (optional)
         the position of the object used for the measurement.
         If this is null, it means the ra/dec from the diaobject
         table was used.

       image_id: str of UUID
         the science image

       template_id: str of UUID
         the template image.  diaforcedphot implicitly assumes a one
         science minus one template subtraction.  If we want to subtract
         a coadded template, then that coadded template should be in the
         database and this should be its id

       flux: float
         flux in nJy

       dflux: float
         uncertainty on flux

       exist_ok: bool (optional)
         If 1 (or something that's true), we're ok if the point already
         exists.  By default, it's an error to try to save the same
         point more than once.

       atol: real or None, default None (optional)
         If not None, and exist_ok is true, then flux and dflux must be
         within this of an existing point (if there is one) to avoid an
         error.

       rtol: real or None, default 1e-6 (optional)
         If not None, and exist_ok is true, then flux and dflux must be
         within this fraction of what exists to avoid an error.
         Remember that fluxes near 0 can easily violate this without
         being meaningful!)

    If id is not given, a new one will be generated.

    Returns
    -------
      Either a 422 if there's a problem, a 500 if something went
      horribly wrong, or a 400 with a json dictionary with keys:
       id
       provenance_id
       diaobject_id
       diaobject_position_id
       image_id
       template_id
       flux
       dflux

    """

    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected diaforcedsource info in json POST data, didtn't get any.", 422

        needed_keys = { 'provenance_id', 'diaobject_id', 'image_id', 'template_id', 'flux', 'dflux' }
        allowed_keys = needed_keys.union( { 'id', 'diaobject_position_id', 'exist_ok', 'atol', 'rtol' } )
        data = self.check_json_keys( needed_keys, allowed_keys )
        exist_ok = bool( data['exist_ok'] ) if 'exist_ok' in data else False
        atol = float( data['atol'] ) if 'atol' in data and data['atol'] is not None else None
        rtol = ( data['rtol'] ) if 'rtol' in data else 1e-6
        rtol = float( rtol ) if rtol is not None else None
        flux = float( data['flux'] )
        dflux = float( data['dflux'] )

        # RACE CONDITION WARNING.  Right now we don't lock the diaforcedphot table.  It's possible
        #    that somebody will insert a consistent point in between when we check if it's there
        #    and when we insert it ourselves.  If that happens, then it will violate the unique
        #    constraint in the database and there will be an error return.  Better behavior
        #    would be to lock the table (scary) so we don't have to return an error.  Hopefully
        #    this will not happen often enough to be a problem.

        with db.DBCon( dictcursor=True ) as dbcon:
            posclause = ( sql.SQL( "diaobject_position_id={posid}" ).format( posid=data['diaobject_position_id' ] )
                          if 'diaobject_position_id' in data and data['diaobject_position_id'] is not None
                          else sql.SQL( "diaobject_position_id IS NULL" ) )
            rows = dbcon.execute( sql.SQL( textwrap.dedent(
                """\
                SELECT * FROM diaforcedsource
                WHERE provenance_id={provid}
                  AND diaobject_id={objid}
                  AND {posclause}
                  AND image_id={imgid}
                  AND template_id={templid}
                """
            ) ).format( provid=data['provenance_id'],
                        objid=data['diaobject_id'],
                        posclause=posclause,
                        imgid=data['image_id'],
                        templid=data['template_id'] ) )
            if len(rows) > 1:
                return "Database corruption, forced photometry point multiply defined!", 422

            elif len(rows) == 1:
                if not exist_ok:
                    return "Error, diaforcedsource already exists.", 422
                row = rows[0]
                if atol is None:
                    flux_atol_ok = True
                    dflux_atol_ok = True
                else:
                    flux_atol_ok = np.fabs( row['flux'] - flux ) <= atol
                    dflux_atol_ok = np.fabs( row['dflux'] - dflux ) <= atol
                if rtol is None:
                    flux_rtol_ok = True
                    dflux_rtol_ok = True
                else:
                    flux_rtol_ok = np.fabs( row['flux'] - flux ) <= rtol * np.fabs( row['flux'] )
                    dflux_rtol_ok = np.fabs( row['dflux'] - dflux ) <= rtol * np.fabs( row['dflux'] )

                if not all( [ flux_atol_ok, dflux_atol_ok, flux_rtol_ok, dflux_rtol_ok ] ):
                    strio = io.StringIO()
                    atolprint = "None" if atol is None else f"{atol:.3g}"
                    rtolprint = "None" if rtol is None else f"{rtol:.3g}"
                    strio.write( f"Error, a photometry point already exists with flux/dflux within tolerances;\n"
                                 f"    passed flux={flux:.6g} ± {dflux:.6g}, "
                                 f"    existing {row['flux']:.6g} ± {row['dflux']:.6g}\n"
                                 f"    atol = {atolprint}, rtol = {rtolprint}\n"
                                 f"  Violates:"
                                )
                    comma = ""
                    for cond, text in zip( [ flux_atol_ok, dflux_atol_ok, flux_rtol_ok, dflux_rtol_ok ],
                                           [ 'flux atol', 'dflux atol', 'flux rtol', 'dflux rtol' ] ):
                        if not cond:
                            strio.write( f"{comma} {text}" )
                            comma = ","
                    return strio.getvalue(), 422

                # Just return the consistent existing point
                return rows[0]

            else:
                dfp = { 'id': asUUID( data['id'] ) if 'id' in data and data['id'] is not None else uuid.uuid4(),
                        'provenance_id': asUUID( data['provenance_id'] ),
                        'diaobject_id': asUUID( data['diaobject_id'] ),
                        'diaobject_position_id': ( asUUID( data['diaobject_position_id'] )
                                                   if ( ( 'diaobject_position_id' in data ) and
                                                        ( data['diaobject_position_id'] is not None ) )
                                                   else None ),
                        'image_id': asUUID( data['image_id'] ),
                        'template_id': asUUID( data['template_id'] ),
                        'flux': flux,
                        'dflux': dflux
                       }
                fields = sql.SQL(",").join( sql.Identifier(k) for k in dfp.keys() )
                values = sql.SQL(",").join( v for v in dfp.values() )
                dbcon.execute_nofetch( sql.SQL( "INSERT INTO diaforcedsource({fields}) VALUES ({values})" )
                                       .format( fields=fields, values=values ) )
                dbcon.commit()

                return dfp


# ======================================================================

class GetDiaForcedSource( BaseView ):
    """Get a diaforcedsource.

    Call api endpoint /getdiaforcedsource/<diaforcedsource_id>

    Returns a dictionary with keys:
      id
      provenance_id
      diaobject_id
      diaobject_position_id   (may be null)
      image_id
      template_id
      flux
      dflux
    """

    def do_the_things( self, sourceid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( sql.SQL( "SELECT * FROM diaforcedsource WHERE id={dpid}" ).format( dpid=sourceid ) )
            if len(rows) == 0:
                return f"Unknown diaforcedsource {sourceid}", 422
            elif len(rows) > 1:
                return f"Multiple diaforcedsources with id {sourceid}; this should never happen.", 422
            else:
                return rows[0]


# ======================================================================
class GetDiaForcedSourceLtcv( BaseView ):
    """Get a sequence of forced photometry.

    Call either with
       /getdiaforcedsourceltcv/<provid>/<diaobjectid>

    or
       /getdiaforcedsourceltcv/<provtag>/<process>/<diaobjectid>

    Optionally, you may include a json-encoded dictionary in POST data with keys:

    include_ids: bool
      Return lightcurve will include id, diaobject_position_id, image_id
      and template_id.  Note that if you don't ask for this, you may get
      back multiple points from the same mjd without any way of
      distinguishing them.  (The difference would be different template
      ids.)

    WARNING: if you don't give include_ids, you will have no way of
    knowing if all the forced photometry used the same position.  (If
    you do give include_ids, then you can look at the
    diaobject_position_id.)  If we really do provenances right, then
    this inconsistency shouldn't ever happen.

    Returns
    -------
      Json dictionary, the values of which are lists.  All the lists
      should have the same number of elements.  You can feed this into
      pandas.DataFrame (for example).  Keys:

        mjd : list of float

        band : list of str

        flux : list of float

        dflux : list of float

      If you specified include_ids, there will be three additional keys:

        id : list of str (str() of uuid)

        image_id : list of str (str() of uuid)

        template_id : list of str (str() of uuid)

        diaobject_position_id : list of str or None (str() of uuid; None means used diaobject position)

    """

    def do_the_things( self, provtag, process, diaobjectid=None ):
        with db.DBCon() as dbcon:
            if diaobjectid is None:
                provid = provtag
                diaobjectid = process
            else:
                rows, cols = dbcon.execute( sql.SQL( textwrap.dedent(
                    """\
                    SELECT p.id FROM provenance p
                    INNER JOIN provenance_tag t ON p.id=t.provenance_id
                    WHERE t.process={proc} and t.tag={tag}
                    """
                ) ).format( proc=process, tag=provtag ) )
                if len(rows) == 0:
                    return f"Can't find provenance for tag {provtag} and process {process}", 422
                elif len(rows) > 1:
                    return ( f"Multiple provenances for tag {provtag} and process {process}; "
                             f"this should never happen", 422 )
                else:
                    provid = rows[0][0]

            include_ids = False
            if flask.request.is_json:
                include_ids = ( 'include_ids' in flask.request.json ) and flask.request.json['include_ids']

            idvals = ( sql.SQL(", ") +
                       sql.SQL(", ").join( sql.Identifier('p', x) for x in [ 'id', 'image_id', 'template_id',
                                                                            'diaobject_position_id' ] )
                       if include_ids else sql.SQL( "" )
                      )
            rows, cols = dbcon.execute( sql.SQL( textwrap.dedent(
                """\
                SELECT i.mjd, i.band, p.flux, p.dflux{idvals}
                FROM diaforcedsource p
                INNER JOIN l2image i ON p.image_id=i.id
                WHERE p.diaobject_id={diaobjid}
                  AND p.provenance_id={provid}
                ORDER BY i.mjd, i.band
                """
            ) ).format( idvals=idvals, diaobjid=diaobjectid, provid=provid ) )

            return { cols[i]: [ row[i] for row in rows ] for i in range( len(cols) ) }



# ======================================================================

class SaveLightcurve( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected lightcurve info in json POST, didn't get any.", 422

        data = flask.request.json
        needed_keys = { 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id', 'band', 'filepath' }
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( needed_keys ):
            return f"Unknown keys: {passed_keys - needed_keys}", 422
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {needed_keys - passed_keys}", 422

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': data['provenance_id'] } )
            if len(rows) == 0:
                return f"Unknown provenance {data['provenance_id']}", 422

            dbcon.execute( ( "INSERT INTO lightcurve(id, provenance_id, diaobject_id, "
                             "  diaobject_position_id, band, filepath) "
                             "VALUES(%(id)s, %(provenance_id)s, %(diaobject_id)s, %(diaobject_position_id)s, "
                             "  %(band)s, %(filepath)s)" ),
                           data )
            dbcon.commit()

            res = dbcon.execute( "SELECT * FROM lightcurve WHERE id=%(id)s", {'id': data['id']} )
            if len(res) == 0:
                return "Something went wrong, lightcurve not saved to database", 422

        return res[0]


# ======================================================================

class GetLightcurve( BaseView ):
    def do_the_things( self, ltcvid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM lightcurve WHERE id=%(id)s", { 'id': ltcvid } )
            if len(rows) == 0:
                return f"No lightcurve with id {ltcvid}", 422
            elif len(rows) > 1:
                return f"Multiple lightcurves with id {ltcvid}; this should never happen.", 422
            else:
                return rows[0]


# ======================================================================

class FindLightcurves( BaseView ):
    def do_the_things( self ):
        equalses = { 'band', 'filepath', 'diaobject_id', 'diaobject_position_id' }
        minmaxes = set()
        allowed_keys = { 'provenance', 'provenance_tag', 'process', 'order_by', 'limit', 'offset' }
        allowed_keys = allowed_keys.union( equalses )
        allowed_keys = allowed_keys.union( minmaxes )
        data = self.check_json_keys( set(), allowed_keys, minmax_keys=minmaxes )

        q = sql.SQL( "SELECT l.* FROM lightcurve l WHERE " )

        with db.DBCon( dictcursor=True ) as dbcon:
            data, provid = self.get_provenance_id( data, dbcon=dbcon )
            conditions = [ sql.SQL( "provenance_id=%(provid)s" ) ]
            subdict = { 'provid': provid }

            ( data,
              conditions,
              subdict,
              finalclause ) = self.make_sql_conditions( data,
                                                        equalses,
                                                        minmaxes=minmaxes,
                                                        conditions=conditions,
                                                        subdict=subdict )
            if len( data ) != 0:
                return f"Error, unknown parameters: {data.keys()}", 422

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class Spectrum1dBase( BaseView ):
    """Shared by the spectrum1d views: the images that went into a spectrum."""

    @staticmethod
    def parse_image_ids( ids ):
        """Check a list of l2image ids from the client; returns them sorted, without repeats, as strings."""
        if not isinstance( ids, list ):
            raise RuntimeError( "included_image_ids must be a list of l2image ids" )
        try:
            return sorted( set( str( uuid.UUID( str(i) ) ) for i in ids ) )
        except ValueError as ex:
            raise RuntimeError( f"included_image_ids must be UUIDs: {ex}" ) from ex

    @staticmethod
    def add_included_image_ids( dbcon, rows ):
        """Add 'included_image_ids' (sorted strings) to every row (a list of dicts), in one query."""
        for row in rows:
            row['included_image_ids'] = []
        if len( rows ) == 0:
            return rows
        found = dbcon.execute( "SELECT spectrum1d_id, l2image_id FROM spectrum1d_included_image "
                               "WHERE spectrum1d_id=ANY(%(ids)s::uuid[])",
                               { 'ids': [ str(row['id']) for row in rows ] } )
        byspectrum = {}
        for item in found:
            byspectrum.setdefault( str( item['spectrum1d_id'] ), [] ).append( str( item['l2image_id'] ) )
        for row in rows:
            row['included_image_ids'] = sorted( byspectrum.get( str( row['id'] ), [] ) )
        return rows


class SaveSpectrum1d( Spectrum1dBase ):
    """Save a spectrum1d, together with the images that went into it.

    Saving an id that exists is a repeat of the same registration, not an error: the provenance,
    the object and the epoch (which identify the spectrum) must be the same, and the other
    columns, and the included images if they are sent, are replaced by the new values.  The
    unique key (provenance, object, epoch) is the database's own, so another id for the same key
    is refused.  Returns the row, with 'included_image_ids'.
    """

    _identity = ( 'provenance_id', 'diaobject_id', 'epoch' )
    _changeable = ( 'diaobject_position_id', 'band', 'filepath', 'mjd_start', 'mjd_end' )

    def do_the_things( self ):
        needed_keys = { 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id', 'band',
                         'filepath', 'mjd_start', 'mjd_end', 'epoch' }
        allowed_keys = needed_keys.union( { 'included_image_ids' } )
        data = self.check_json_keys( needed_keys, allowed_keys )
        included = data.pop( 'included_image_ids', None )
        if included is not None:
            included = self.parse_image_ids( included )

        with db.DBCon( dictcursor=True ) as dbcon:
            existing = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", { 'id': data['id'] } )
            if len( existing ) == 0:
                keysql, subs = self.build_sql_insert( data.keys() )
                dbcon.execute( sql.SQL( "INSERT INTO spectrum1d(" ) + keysql + sql.SQL( ") VALUES (" )
                               + sql.SQL( subs ) + sql.SQL( ")" ), data )
            else:
                for key in self._identity:
                    if str( existing[0][key] ) != str( data[key] ):
                        return ( f"spectrum1d {data['id']} exists with a different {key} "
                                 f"({existing[0][key]}, not {data[key]})" ), 422
                changes = [ k for k in self._changeable if k in data ]
                # The names come from the fixed list above, so they are safe to put in the query text
                setsql = sql.SQL( ", " ).join( sql.SQL( f"{k}=%({k})s" ) for k in changes )
                dbcon.execute( sql.SQL( "UPDATE spectrum1d SET " ) + setsql + sql.SQL( " WHERE id=%(id)s" ), data )

            if included is not None:
                dbcon.execute( "DELETE FROM spectrum1d_included_image WHERE spectrum1d_id=%(id)s",
                               { 'id': data['id'] } )
                if len( included ) > 0:
                    dbcon.execute( "INSERT INTO spectrum1d_included_image(spectrum1d_id, l2image_id) "
                                   "SELECT %(id)s, i FROM unnest(%(ids)s::uuid[]) AS i",
                                   { 'id': data['id'], 'ids': included } )

            rows = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", { 'id': data['id'] } )
            self.add_included_image_ids( dbcon, rows )
            dbcon.commit()

        return rows[0]


# ======================================================================

class GetSpectrum1d( Spectrum1dBase ):
    def do_the_things( self, spectrumid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", {'id': spectrumid} )
            if len(rows) == 0:
                return f"No spectrum1d with id {spectrumid}", 422
            elif len(rows) > 1:
                return f"Multiple spectrum1d with id {spectrumid}; this should never happen.", 422
            else:
                self.add_included_image_ids( dbcon, rows )
                return rows[0]


# ======================================================================

class FindSpectra1d( Spectrum1dBase ):
    def do_the_things( self ):
        equalses = { 'id', 'diaobject_id', 'band', 'filepath' }
        minmaxes = { 'mjd_start', 'mjd_end', 'epoch' }
        allowed_keys = { 'provenance', 'provenance_tag', 'process', 'order_by', 'limit', 'offset' }
        allowed_keys = allowed_keys.union( equalses )
        allowed_keys = allowed_keys.union( minmaxes )
        data = self.check_json_keys( set(), allowed_keys, minmax_keys=minmaxes )

        q = sql.SQL( "SELECT * FROM spectrum1d WHERE " )

        with db.DBCon( dictcursor=True ) as dbcon:
            data, provid = self.get_provenance_id( data, dbcon=dbcon )
            conditions = [ sql.SQL( "provenance_id=%(provid)s" ) ]
            subdict = { 'provid': provid }

            ( data, conditions, subdict, finalclause ) = self.make_sql_conditions( data,
                                                                                   equalses=equalses,
                                                                                   minmaxes=minmaxes,
                                                                                   conditions=conditions,
                                                                                   subdict=subdict )
            if len(data) != 0:
                return f"Error, unknown parametrs: {data.keys()}", 422

            q += conditions + finalclause
            rows = dbcon.execute( q, subdict )
            return self.add_included_image_ids( dbcon, rows )


# ======================================================================

class ProcessingRunBase( BaseView ):
    """Shared by the processing_run views: a run is identified by (process, diaobject_id, epoch)."""

    @staticmethod
    def check_run_key( data ):
        """Validate the three values that identify a run; returns them as (str, str, int)."""
        process = data['process']
        if ( not isinstance( process, str ) ) or ( process.strip() == '' ):
            raise RuntimeError( "process must be a non-empty string" )
        try:
            objid = str( uuid.UUID( str( data['diaobject_id'] ) ) )
        except ValueError as ex:
            raise RuntimeError( f"diaobject_id must be a UUID: {ex}" ) from ex
        epoch = data['epoch']
        if isinstance( epoch, bool ) or ( not isinstance( epoch, int ) ):
            raise RuntimeError( "epoch must be an integer (millidays)" )
        return process, objid, epoch


class StartProcessingRun( ProcessingRunBase ):
    """Start a run, or start it again.

    A run that does not exist is created as 'processing'.  One that exists is set back to
    'processing' whatever its status was (a run is repeated on purpose: a new release, a
    corrected configuration), and its message, provenance and finish time are cleared.
    Returns the row.  The record says what the last start did; it does not refuse a start.
    """

    def do_the_things( self ):
        data = self.check_json_keys( { 'process', 'diaobject_id', 'epoch' },
                                     { 'process', 'diaobject_id', 'epoch', 'execution' } )
        process, objid, epoch = self.check_run_key( data )
        subs = { 'id': str( uuid.uuid4() ), 'process': process, 'diaobject_id': objid, 'epoch': epoch,
                 'execution': data.get( 'execution' ) }

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "INSERT INTO processing_run(id, process, diaobject_id, epoch, status, execution, "
                                  "                           started_at, status_updated_at) "
                                  "VALUES (%(id)s, %(process)s, %(diaobject_id)s, %(epoch)s, 'processing', "
                                  "        %(execution)s, NOW(), NOW()) "
                                  "ON CONFLICT (process, diaobject_id, epoch) DO UPDATE "
                                  "  SET status='processing', execution=EXCLUDED.execution, message=NULL, "
                                  "      provenance_id=NULL, started_at=NOW(), finished_at=NULL, "
                                  "      status_updated_at=NOW() "
                                  "RETURNING *", subs )
            dbcon.commit()

        return rows[0]


class FinishProcessingRun( ProcessingRunBase ):
    """Finish a run that is 'processing', as 'done' or 'failed'.

    A run that is not 'processing' is not changed (a late or repeated call): the row is returned
    with 'updated': false.  An unknown run is an error.
    """

    _statuses = ( 'done', 'failed' )

    def do_the_things( self ):
        data = self.check_json_keys( { 'process', 'diaobject_id', 'epoch', 'status' },
                                     { 'process', 'diaobject_id', 'epoch', 'status', 'provenance_id',
                                       'execution', 'message' } )
        process, objid, epoch = self.check_run_key( data )
        if data['status'] not in self._statuses:
            return f"Unknown status {data['status']!r}; must be one of {self._statuses}", 422
        provid = data.get( 'provenance_id' )
        if provid is not None:
            try:
                provid = str( uuid.UUID( str( provid ) ) )
            except ValueError as ex:
                return f"provenance_id must be a UUID: {ex}", 422
        subs = { 'process': process, 'diaobject_id': objid, 'epoch': epoch, 'status': data['status'],
                 'provenance_id': provid, 'execution': data.get( 'execution' ),
                 'message': data.get( 'message' ) }

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "UPDATE processing_run SET status=%(status)s, "
                                  "  provenance_id=%(provenance_id)s::uuid, "
                                  "  execution=COALESCE(%(execution)s, execution), "
                                  "  message=%(message)s, finished_at=NOW(), status_updated_at=NOW() "
                                  "WHERE process=%(process)s AND diaobject_id=%(diaobject_id)s "
                                  "  AND epoch=%(epoch)s AND status='processing' "
                                  "RETURNING *", subs )
            updated = len( rows ) > 0
            if not updated:
                rows = dbcon.execute( "SELECT * FROM processing_run "
                                      "WHERE process=%(process)s AND diaobject_id=%(diaobject_id)s "
                                      "  AND epoch=%(epoch)s", subs )
                if len( rows ) == 0:
                    return f"No run of {process} for object {objid} and epoch {epoch}", 422
            dbcon.commit()

        row = rows[0]
        row['updated'] = updated
        return row


class FindProcessingRuns( BaseView ):
    def do_the_things( self ):
        equalses = { 'id', 'process', 'diaobject_id', 'epoch', 'status', 'execution', 'provenance_id' }
        allowed_keys = equalses.union( { 'order_by', 'limit', 'offset' } )
        data = self.check_json_keys( set(), allowed_keys )

        with db.DBCon( dictcursor=True ) as dbcon:
            ( data, conditions, subdict, finalclause ) = self.make_sql_conditions( data, equalses=equalses,
                                                                                   conditions=[], subdict={} )
            if len(data) != 0:
                return f"Error, unknown parameters: {list(data.keys())}", 422

            q = sql.SQL( "SELECT * FROM processing_run" )
            if conditions != sql.SQL( "" ):
                q += sql.SQL( " WHERE " ) + conditions
            return dbcon.execute( q + finalclause, subdict )


# ======================================================================

class LetsEncrypt( flask.views.View ):
    def dispatch_request( self, f ):
        if not re.search( r'^[a-zA-Z0-9_\-\$\.]+$', f ):
            SNLogger.error( f"Got filename {f} which is invalid." )
            raise RuntimeError( "Invalid filename" )
        p = pathlib.Path( "/tmp/.well-known" ) / f
        with open(p) as ifp:
            text = ifp.read()
        return text, 200


# ======================================================================

urls = {
    "/": MainPage,
    "/test/<param>": TestEndpoint,

    "/getprovenance/<provid>": GetProvenance,
    "/getprovenance/<provid>/<process>": GetProvenance,   # provid is really a tag
    "/createprovenance": CreateProvenance,
    "/tagprovenance/<tag>/<process>/<provid>": TagProvenance,
    "/tagprovenance/<tag>/<process>/<provid>/<int:replace>": TagProvenance,
    "/provenancesfortag/<tag>": ProvenancesForTag,

    "/getdiaobject/<diaobjectid>": GetDiaObject,
    "/finddiaobjects/<provid>": FindDiaObjects,
    "/finddiaobjects": FindDiaObjects,
    "/savediaobject": SaveDiaObject,
    "/getdiaobjectposition/<provid>": GetDiaObjectPosition,
    "/getdiaobjectposition/<provid>/<diaobjectid>": GetDiaObjectPosition,
    "/savediaobjectposition": SaveDiaObjectPosition,

    "/getl2image/<imageid>": GetL2Image,
    "/findl2images": FindL2Images,
    "/savel2image": SaveL2Image,
    "/bulksavel2images": BulkSaveL2Images,
    "/setl2imagestatus": SetL2ImageStatus,

    "/savesegmap": SaveSegmentationMap,
    "/getsegmap/<segmapid>": GetSegmentationMap,
    "/findsegmaps": FindSegmentationMap,

    "/savediaforcedsource": SaveDiaForcedSource,
    "/getdiaforcedsource/<sourceid>": GetDiaForcedSource,
    # Next line, really its "gitdiaforcedsourceltcv/<provid>/<diaobjectid>", but Flask needs this
    "/getdiaforcedsourceltcv/<provtag>/<process>": GetDiaForcedSourceLtcv,
    "/getdiaforcedsourceltcv/<provtag>/<process>/<diaobjectid>": GetDiaForcedSourceLtcv,

    "/savelightcurve": SaveLightcurve,
    "/getlightcurve/<ltcvid>": GetLightcurve,
    "/findlightcurves": FindLightcurves,

    "/savespectrum1d": SaveSpectrum1d,
    "/getspectrum1d/<spectrumid>": GetSpectrum1d,
    "/findspectra1d": FindSpectra1d,

    "/startprocessingrun": StartProcessingRun,
    "/finishprocessingrun": FinishProcessingRun,
    "/findprocessingruns": FindProcessingRuns,

    "/.well-known/acme-challenge/<f>": LetsEncrypt
}
