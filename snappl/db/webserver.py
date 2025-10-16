__all__ = [ 'setup_flask_app' ]
import uuid
import flask
import flask_session

from rkwebutil import rkauth_flask

from snappl.config import Config
from snappl.db import db
from snappl.db.baseview import BaseView


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
                return f"Unknown provenance {provid}{'' if process is None else f' for process {process}'}", 500
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
            elif not existok:
                return f"Error, provenance {data['id']} already exists", 500

            if tag is not None:
                self.tag_provenance( dbcon, tag, data['process'], data['id'], replace=replace_tag )

            for uid in upstream_ids:
                dbcon.execute( "INSERT INTO provenance_upstream(downstream_id,upstream_id) "
                               "VALUES (%(down)s,%(up)s)",
                               { 'down': prov.id, 'up': uid } )
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
    def do_the_things( self, provid ):
        q = "SELECT * FROM diaobject WHERE "
        conditions = [ 'provenance_id=%(provid)s' ]
        subdict = { 'provid': provid }
        if flask.request.is_json:
            data = flask.request.json

            if ( 'ra' in data ) or ( 'dec' in data ):
                if not ( ( 'ra' in data ) and ( 'dec' in data ) ):
                    return "Error, if you specify ra or dec, you must specify both"
                radius = 1.0
                if 'radius' in data:
                    radius = data['radius']
                    del data['radius']
                conditions.append( "q3c_radial_query(ra,dec,%(ra)s,%(dec)s,%(radius)s)" )
                subdict.update( { 'ra': data['ra'], 'dec': data['dec'], 'radius': radius / 3600. } )
                del data['ra']
                del data['dec']

            for kw in [ 'name', 'iauname' ]:
                if kw in data:
                    conditions.append( f"{kw}=%({kw})s" )
                    subdict[kw] = str( data[kw] ) if data[kw] is not None else None
                    del data[kw]
            for kw in [ 'mjd_discovery', 'mjd_peak', 'mjd_start', 'mjd_end' ]:
                for edge, op in zip( [ 'min', 'max' ], [ '>=', '<=' ] ):
                    if f'{kw}_{edge}' in data and data[f'{kw}_{edge}'] is not None:
                        conditions.append( f"{kw} {op} %({kw}_{edge})s" )
                        subdict[f'{kw}_{edge}'] = data[f'{kw}_{edge}']
                        del data[f'{kw}_{edge}']
            if len(data) != 0:
                return f"Error, unknown parameters: {data.keys()}", 500

        q += ' AND '.join( conditions )

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( q, subdict )

        return rows


# ======================================================================

class SaveDiaObject( BaseView ):
    def do_the_things( self ):
        if not flask.request.is_json:
            return "Expected diaobject data in json POST data, didn't get any.", 500

        data = flask.request.json
        needed_keys = { 'provenance_id', 'name', 'ra', 'dec', 'mjd_discovery' }
        allowed_keys = { 'id', 'iauname', 'mjd_peak', 'mjd_start', 'mjd_end', 'properties' }.union( needed_keys )
        passed_keys = set( data.keys() )
        if not passed_keys.issubset( allowed_keys ):
            return f"Unknown keys: {passed_keys - allowed_keys}", 500
        if not needed_keys.issubset( passed_keys ):
            return f"Missing required keys: {passed_keys - needed_keys}", 500
        if any( data[i] is None for i in needed_keys ):
            return f"None of the necessary keys can be None: {needed_keys}"

        if 'id' not in data:
            data['id'] = uuid.uuid4()

        duplicate_ok = False
        if 'dupliate_ok' in data:
            duplicate_ok = data['duplicate_ok']
            del data['duplicate_ok']

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( "SELECT * FROM diaobject WHERE id=%(id)s", { 'id': data['id'] } )
            if len(rows) != 0:
                return f"diaobject {data['id']} already exists!", 500
            if not duplicate_ok:
                rows = dbcon.execute( "SELECT * FROM diaobject WHERE name=%(name)s AND provenance_id=%(prov)s",
                                      { 'name': data['name'], 'prov': data['provenance_id'] } )
                if len(rows) != 0:
                    return ( f"diaobject with name {data['name']} in provenance {data['provenance_id']} "
                             f"already exists!", 500 )

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
    def do_the_things( self, provid ):
        q = "SELECT * FROM l2image WHERE "
        conditions = [ 'provenance_id=%(provid)s' ]
        subdict = { 'provid': provid }

        if flask.request.is_json:
            data = flask.request.json

            if ( 'ra' in data ) or ( 'dec' in data ):
                # 'ra' and 'dec' are supposed to be "includes this".
                #
                # THINKING AHEAD : this poly query doesn't use the q3c index
                # As the number of images get large, we should look at performance.
                # We many need to do this in two steps, which would mean using
                # a temp table.  First step would use regular indexes on the
                # eight corner variables and use LEAST and GREATEST with ra and dec.
                # Then, a second query would use the poly query on the temp table
                # resulting from that first query.  (Or maybe you can do it all
                # with clever nested queries.)
                #
                if not ( ( 'ra' in data ) and ( 'dec' in data ) ):
                    return "Error, if you specify ra or dec, you must specify both"
                conditions.append( "q3c_poly_query( %(ra)s, %(dec)s, "
                                   "ARRAY[ ra_corner_00, dec_corner_00, ra_corner_01, dec_corner_01, "
                                   "       ra_corner_11, dec_corner_11, ra_corner_10, dec_corner_10 ] )" )
                subdict.update( { 'ra': data['ra'], 'dec': data['dec'] } )
                del data['ra']
                del data['dec']

            for kw in [ 'pointing', 'sca', 'filter', 'filepath' ]:
                if kw in data:
                    conditions.append( f"{kw}=%({kw})s" )
                    subdict[kw] = data[kw] if data[kw] is not None else None
                    del data[kw]

            for kw in [ 'ra_corner_00', 'ra_corner_01', 'ra_corner_10', 'ra_corner_11',
                        'dec_corner_00', 'dec_corner_01', 'dec_corner_10', 'dec_corner_11',
                        'width', 'height', 'mjd_start', 'exptime' ]:
                if kw in data:
                    conditions.append( f"{kw}=%({kw})s" )
                    subdict[kw] = data[kw] if data[kw] is not None else None
                    del data[kw]
                for edge, op in zip( [ 'min', 'max' ], [ '>=', '<=' ] ):
                    if f'{kw}_{edge}' in data and data[f'{kw}_{edge}'] is not None:
                        conditions.append( f"{kw} {op} %({kw}_{edge})s" )
                        subdict[f'{kw}_{edge}'] = data[f'{kw}_{edge}']
                        del data[f'{kw}_{edge}']

            if len(data) != 0:
                return f"Error, unknown parameters: {data.keys()}", 500

        q += ' AND '.join( conditions )

        with db.DBCon( dictcursor=True ) as dbcon:
            rows = dbcon.execute( q, subdict )

        return rows


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
    "/savediaobject": SaveDiaObject,

    "/getl2image/<imageid>": GetL2Image,
    "/findl2images/<provid>": FindL2Images,
}
