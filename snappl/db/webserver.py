__all__ = [ 'setup_flask_app' ]

import uuid

import flask
import flask_session
from psycopg import sql

from rkwebutil import rkauth_flask

from snappl.config import Config
from snappl.db import db
from snappl.db.baseview import BaseView
# from snappl.logger import SNLogger


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
                         f"{'' if process is None else f' for process {process}'}!" ), 500
            prov = { cols[i]: rows[0][i] for i in range( len(cols) ) }
            self.get_upstreams( prov, con )

        return prov


# ======================================================================

class CreateProvenance( BaseProvenance ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected JSON payoad", 500
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
                return f"Error, provenance {data['id']} already exists", 500

            if tag is not None:
                self.tag_provenance( dbcon, tag, data['process'], data['id'], replace=replace_tag )

            dbcon.commit()

        return { "status": "ok" }


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
            return f"Database corruption; multiple diaobjects with id {diaobjectid}", 500
        elif len(rows) == 0:
            return f"Object not found: {diaobjectid}", 500
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
                return f"Error, unknown parameters: {list(data.keys())}", 500

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class SaveDiaObject( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected diaobject data in json POST data, didn't get any.", 500

        data = flask.request.json
        needed_keys = { 'provenance_id', 'ra', 'dec', 'mjd_discovery' }
        allowed_keys = { 'id', 'iauname', 'name', 'mjd_peak', 'mjd_start',
                         'mjd_end', 'properties', 'association_radius' }.union( needed_keys )
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( allowed_keys ):
            return f"Unknown keys: {passed_keys - allowed_keys}", 500
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {needed_keys - passed_keys}", 500
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
                return f"diaobject id {data['id']} already exists!", 500

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
                             f"already exists!", 500 )

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
                    return f"Error, saved diaobject {data['id']}, but it's not showing up in the database", 500
                elif len(rows) > 1:
                    return f"Database corruption, more than one diaobject with id={data['id']}", 500
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
                    return "No postion for diaobject {diaobjectid} in with position provenance {provid}", 500
                return rows[0]

            if not flask.request.is_json:
                return "getdiaobjectposition/<provid> requires JSON POST data", 500
            data = flask.request.json
            if 'diaobject_ids' not in data:
                return "getdiaobjectposition/<provid> requres diaobject_ids in POST JSON dict", 500

            rows = dbcon.execute( "SELECT * FROM diaobject_position "
                                  "WHERE provenance_id=%(provid)s AND diaobject_id=ANY(%(objids)s)",
                                  { 'provid': provid, 'objids': data['diaobject_ids'] } )
            return rows


# ======================================================================

class SaveDiaObjectPosition( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected diaobject position data in json POST data, didn't get any.", 500

        data = flask.request.json
        needed_keys = { 'provenance_id', 'diaobject_id', 'ra', 'dec' }
        allowed_keys = { 'id', 'ra_err', 'dec_err', 'ra_dec_covar' }.union( needed_keys )
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( allowed_keys ):
            return f"Unknown keys: {passed_keys - allowed_keys}", 500
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {passed_keys - needed_keys}", 500
        if any( data[i] is None for i in needed_keys ):
            return f"None of the necessary keys can be None: {needed_keys}"

        if ( 'id' not in data ) or ( data['id'] is None ):
            data['id'] = uuid.uuid4()

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': data['provenance_id'] } )
            if len(rows) == 0:
                return f"Unknown provenance {data['provenance_id']}", 500

            dbcon.execute( "LOCK TABLE diaobject_position" )

            rows = dbcon.execute( "SELECT * FROM diaobject_position "
                                  "WHERE diaobject_id=%(objid)s AND provenance_id=%(provid)s",
                                  { 'objid': data['diaobject_id'], 'provid': data['provenance_id'] } )
            if len(rows) != 0:
                return ( f"Object {data['diaobject_id']} already has a position "
                         f"with provenance {data['provenance_id']}" ), 500

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
            return f"Database corruption: multiple l2image with id {imageid}", 500
        elif len( rows ) == 0:
            return f"L2image not found: {imageid}", 500
        else:
            return rows[0]


# ======================================================================

class FindL2Images( BaseView ):
    def do_the_things( self ):
        equalses = { 'id', 'pointing', 'sca', 'band', 'filepath', 'format' }
        minmaxes = { 'ra', 'dec', 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                     'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                     'width', 'height', 'mjd', 'exptime', 'position_angle' }
        allowed_keys = { 'provenance', 'provenance_tag', 'process', 'order_by', 'limit', 'offset' }
        allowed_keys = allowed_keys.union( equalses )
        allowed_keys = allowed_keys.union( minmaxes )
        data = self.check_json_keys( set(), allowed_keys, minmax_keys=minmaxes )

        q = sql.SQL( "SELECT * FROM l2image WHERE " )

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
                return f"Error, unknown parameters: {data.keys()}", 500

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class SaveSegmentationMap( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected segmeap info in json POST< didn't get any.", 500

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
            return f"Segmentation map {segmapid} not found.", 500
        elif len(rows) > 1:
            return f"Database corruption, multiple segmaps with id {segmapid}.  This should never happen.", 500
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
                return f"Error, unknown parameters: {data.keys()}", 500

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class SaveLightcurve( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected lightcurve info in json POST, didn't get any.", 500

        data = flask.request.json
        needed_keys = { 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id', 'band', 'filepath' }
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( needed_keys ):
            return f"Unknown keys: {passed_keys - needed_keys}", 500
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {needed_keys - passed_keys}", 500

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM provenance WHERE id=%(id)s", { 'id': data['provenance_id'] } )
            if len(rows) == 0:
                return f"Unknown provenance {data['provenance_id']}", 500

            dbcon.execute( ( "INSERT INTO lightcurve(id, provenance_id, diaobject_id, "
                             "  diaobject_position_id, band, filepath) "
                             "VALUES(%(id)s, %(provenance_id)s, %(diaobject_id)s, %(diaobject_position_id)s, "
                             "  %(band)s, %(filepath)s)" ),
                           data )
            dbcon.commit()

            res = dbcon.execute( "SELECT * FROM lightcurve WHERE id=%(id)s", {'id': data['id']} )
            if len(res) == 0:
                return "Something went wrong, lightcurve not saved to database", 500

        return res[0]


# ======================================================================

class GetLightcurve( BaseView ):
    def do_the_things( self, ltcvid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM lightcurve WHERE id=%(id)s", { 'id': ltcvid } )
            if len(rows) == 0:
                return f"No lightcurve with id {ltcvid}", 500
            elif len(rows) > 1:
                return f"Multiple lightcurves with id {ltcvid}; this should never happen.", 500
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
                return f"Error, unknown parameters: {data.keys()}", 500

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


# ======================================================================

class SaveSpectrum1d( BaseView ):
    def do_the_things( self ):
        needed_keys = { 'id', 'provenance_id', 'diaobject_id', 'diaobject_position_id', 'band',
                         'filepath', 'mjd_start', 'mjd_end', 'epoch' }
        allowed_keys = needed_keys
        data = self.check_json_keys( needed_keys, allowed_keys )

        keysql, subs = self.build_sql_insert( data.keys() )
        q = sql.SQL( "INSERT INTO spectrum1d(" ) + keysql + sql.SQL( ") VALUES (" ) + sql.SQL( subs ) + sql.SQL( ")" )

        with db.DBCon( dictcursor=True ) as dbcon:
            dbcon.execute( q, data )
            row = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", {'id': data['id']} )
            dbcon.commit()

        return row


# ======================================================================

class GetSpectrum1d( BaseView ):
    def do_the_things( self, spectrumid ):
        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM spectrum1d WHERE id=%(id)s", {'id': spectrumid} )
            if len(rows) == 0:
                return f"No spectrum1d with id {spectrumid}", 500
            elif len(rows) > 1:
                return f"Multiple spectrum1d with id {spectrumid}; this should never happen.", 500
            else:
                return rows[0]


# ======================================================================

class FindSpectra1d( BaseView ):
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
                return f"Error, unknown parametrs: {data.keys()}", 500

            q += conditions + finalclause
            return dbcon.execute( q, subdict )


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

    "/savesegmap": SaveSegmentationMap,
    "/getsegmap/<segmapid>": GetSegmentationMap,
    "/findsegmaps": FindSegmentationMap,

    "/savelightcurve": SaveLightcurve,
    "/getlightcurve/<ltcvid>": GetLightcurve,
    "/findlightcurves": FindLightcurves,

    "/savespectrum1d": SaveSpectrum1d,
    "/getspectrum1d/<spectrumid>": GetSpectrum1d,
    "/findspectra1d": FindSpectra1d,
}
