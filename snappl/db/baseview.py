from types import SimpleNamespace
import simplejson

import flask
import flask.views
from psycopg import sql

from snappl.db import db
from snappl.logger import SNLogger
from snappl.utils import SNPITJsonEncoder


# ======================================================================

class BaseView( flask.views.View ):
    """A BaseView that all other views can be based on.

    If the view doesn't override dispatch_request, then it must define a
    function do_the_things.  That should return a dict, list, string,
    tuple, or ...something else.

    If it returns a dict or a list, the web server will send to the
    client application/json with status 200. If the result is a string,
    it the web server will send to the client text/plain with status
    200.  If it's a tuple, just let Flask deal with that tuple to figure
    out what the web server should send to the client.  Otherwise, the
    web server will send to the client application/octet-stream with
    status 200.

    Subclasses that do not override dispatch_request do not need to call
    check_auth.  However, if they do override it, they should call that
    if the results shouldn't be sent back to an unauthenticated user.

    """

    _admin_required = False

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )


    def check_json_keys( self, needed_keys, allowed_keys, minmax_keys=set() ):
        if not flask.request.is_json:
            raise RuntimeError( "Expected json POST data, didn't get any." )

        all_allowed_keys = allowed_keys.copy()
        for kw in minmax_keys:
            for edge in [ 'min', 'max' ]:
                all_allowed_keys.add( f"{kw}_{edge}" )

        data = flask.request.json
        passed_keys = set( data.keys() )
        if not needed_keys.issubset( passed_keys ):
            raise RuntimeError( f"Missing required keys: {needed_keys - passed_keys}" )
        if not passed_keys.issubset( all_allowed_keys ):
            raise RuntimeError( f"Unknown keys: {passed_keys - all_allowed_keys}" )
        return data

    def get_provenance_id( self, data, dbcon=None ):
        with db.DBCon( dictcursor=True ) as dbcon:
            provid = None
            if 'provenance' in data:
                provid = data['provenance']
                del data['provenance']
            elif ( 'provenance_tag' in data ) and ( 'process' in data ):
                rows = dbcon.execute( "SELECT provenance_id FROM provenance_tag "
                                      "WHERE tag=%(tag)s AND process=%(proc)s",
                                      {'tag': data['provenance_tag'], 'proc': data['process'] } )
                if len(rows) == 0:
                    raise RuntimeError( f"Unknown provenance with tag {data['provenance_tag']} "
                                        f"and process {data['process']}" )
                if len(rows) > 1:
                    raise RuntimeError ( f"Database corruption: multiple provenances with tag {data['provenance_tag']}"
                                         f"and process {data['process']}; this should never happen." )
                provid = db.Provenance.get( rows[0]['provenance_id'] ).id
                del data['provenance_tag']
                del data['process']
            else:
                raise RuntimeError( "Must give either provenance_id, or both of provenance_tag and process" )

            return data, provid


    # Warning : only call this next one if you've made sure that there is no SQL injection in keys!
    def build_sql_insert( self, keys ):
        keysql = None
        subs = None
        for key in keys:
            if keysql is None:
                keysql = sql.SQL( "{key}" ).format( key=sql.Identifier( key ) )
            else:
                keysql += sql.SQL( ", {key}" ).format( key=sql.Identifier( key ) )
            if subs is None:
                subs = f"%({key})s"
            else:
                subs += f", %({key})s"
        return keysql, subs


    # WARNING.  Do not use this unless you're sure that everything in
    #   the passed arrays have no SQL injection attacks.
    def make_sql_conditions( self, data, equalses=[], minmaxes=[],
                             q3ctriplets=[], cornerpolypairs=[],
                             conditions=[], subdict={} ):
        finalclause = None

        if any( i in data for i in [ 'order_by', 'limit', 'offset' ] ):
            orderbyclause = None
            limitclause = None
            offsetclause = None

            if 'order_by' in data:
                orderby = data['order_by']
                if not isinstance( orderby, list ):
                    orderby = [ orderby ]
                orderbyclause = sql.SQL( " ORDER BY " )
                comma = ""
                for o in orderby:
                    orderbyclause += sql.SQL( f"{comma}{{orderby}}" ).format( orderby=sql.Identifier(o) )
                    comma = ","
                del data['order_by']
                finalclause = orderbyclause

            if 'limit' in data:
                limitclause = sql.SQL( " LIMIT %(finalclause_limit)s" )
                subdict['finalclause_limit'] = data['limit']
                del data['limit']
                if finalclause is None:
                    finalclause = limitclause
                else:
                    finalclause += limitclause

            if 'offset' in data:
                offsetclause = sql.SQL( " OFFSET %(finalclause_offset)s" )
                subdict['finalclause_offset'] = data['offset']
                del data['offset']
                if finalclause is None:
                    finalclause = offsetclause
                else:
                    finalclause += offsetclause

        finalclause = sql.SQL("") if finalclause is None else finalclause

        for i, triplet in enumerate(q3ctriplets):
            presencecheck = [ ( i in data and data[i] is not None ) for i in triplet ]
            if any( presencecheck ):
                if not all( presencecheck ):
                    raise RuntimeError( f"Must include all or none of {triplet}" )
                barf = f"q3c_triplet_{i}"
                formatsubs = { f"{barf}_0": sql.Identifier( triplet[0] ),
                               f"{barf}_1": sql.Identifier( triplet[1] ) }
                conditions.append( sql.SQL( f"q3c_radial_query({{{barf}_0}},{{{barf}_1}},"
                                            f"%({barf}_0)s,%({barf}_1)s,%({barf}_2)s)"
                                           ).format( **formatsubs ) )
                subdict.update( { f"{barf}_0": data[triplet[0]],
                                  f"{barf}_1": data[triplet[1]],
                                  f"{barf}_2": data[triplet[2]] / 3600. } )
                del data[triplet[0]]
                del data[triplet[1]]
                del data[triplet[2]]

        for i, pair in enumerate(cornerpolypairs):
            presencecheck = [ ( i in data and data[i] is not None ) for i in pair ]
            if any( presencecheck ):
                if not all( presencecheck ):
                    raise RuntimeError( f"Must include both or neither of {pair}" )
                barf = f"corner_pair_{i}"
                # THINKING AHEAD : this poly query doesn't use the q3c index
                # As the number of database rows get large, we should look
                # at performance.  We many need to do this in two steps,
                # which would mean using a temp table.  First step would use
                # regular indexes on the eight corner variables and use
                # LEAST and GREATEST with ra and dec.  Then, a second query
                # would use the poly query on the temp table resulting from
                # that first query.  (Or maybe you can do it all with clever
                # nested queries.)  This becomes very complicated.
                conditions.append( sql.SQL( f"q3c_poly_query(%({barf}_0)s, %({barf}_1)s, "
                                            f"ARRAY[ ra_corner_00, dec_corner_00, ra_corner_01, dec_corner_01, "
                                            f"       ra_corner_11, dec_corner_11, ra_corner_10, dec_corner_10 ] )"
                                           ) )
                subdict.update( { f"{barf}_0": data[pair[0]],
                                  f"{barf}_1": data[pair[1]] } )
                del data[pair[0]]
                del data[pair[1]]

        for kw in equalses:
            if ( kw in data ) and ( data[kw] is not None ):
                conditions.append( sql.SQL( f"{kw}=%({kw})s" ) )
                # I hate that we're doing str here, but we have a legacy of diaobject names
                #   being either strings or integers
                subdict[kw] = str( data[kw] )
                del data[kw]

        for kw in minmaxes:
            if kw in data:
                if data['kw'] is not None:
                    conditions.append( sql.SQL( f"{kw}=%({kw})s" ) )
                    subdict[kw] = data[kw]
                del data[kw]
            for edge, op in zip( [ 'min', 'max' ], [ '>=', '<=' ] ):
                if f'{kw}_{edge}' in data:
                    if data[f'{kw}_{edge}'] is not None:
                        conditions.append( sql.SQL( f"{kw} {op} %({kw}_{edge})s" ) )
                        subdict[f'{kw}_{edge}'] = data[f'{kw}_{edge}']
                    del data[f'{kw}_{edge}']

        condstr = None
        for condition in conditions:
            if condstr is None:
                condstr = condition
            else:
                condstr += sql.SQL(" AND ") + condition
        condstr = sql.SQL("") if condstr is None else condstr

        return data, condstr, subdict, finalclause


    def check_auth( self ):
        self.username = flask.session['username'] if 'username' in flask.session else '(None)'
        self.displayname = flask.session['userdisplayname'] if 'userdisplayname' in flask.session else '(None)'
        self.authenticated = ( 'authenticated' in flask.session ) and flask.session['authenticated']
        self.user = None
        if self.authenticated:
            with db.DB() as conn:
                cursor = conn.cursor()
                cursor.execute( "SELECT id,username,displayname,email FROM authuser WHERE username=%(username)s",
                                {'username': self.username } )
                rows = cursor.fetchall()
                if len(rows) > 1:
                    self.authenticated = False
                    raise RuntimeError( f"Error, more than one {self.username} in database, "
                                        f"this should never happen." )
                if len(rows) == 0:
                    self.authenticated = False
                    raise ValueError( f"Error, failed to find user {self.username} in database" )
                row = rows[0]
                self.user = SimpleNamespace( id=row[0], username=row[1], displayname=row[2], email=row[3] )
                # Verify that session displayname and database displayname match?  Eh.  Whatevs.
        return self.authenticated

    def dispatch_request( self, *args, **kwargs ):
        if not self.check_auth():
            return "Not logged in", 500
        if ( self._admin_required ) and ( not self.user.isadmin ):
            return "Action requires admin", 500
        try:
            retval = self.do_the_things( *args, **kwargs )
            # Can't just use the default JSON handling, because it
            #   writes out NaN which is not standard JSON and which
            #   the javascript JSON parser chokes on.  Sigh.
            if isinstance( retval, dict ) or isinstance( retval, list ):
                # SNLogger.warning( f"Dumping to json: {retval}" )
                return ( simplejson.dumps( retval, ignore_nan=True, cls=SNPITJsonEncoder ),
                         200, { 'Content-Type': 'application/json' } )
            elif isinstance( retval, str ):
                return retval, 200, { 'Content-Type': 'text/plain; charset=utf-8' }
            elif isinstance( retval, tuple ):
                return retval
            else:
                return retval, 200, { 'Content-Type': 'application/octet-stream' }
        except Exception as ex:
            # sio = io.StringIO()
            # traceback.print_exc( file=sio )
            # SNLogger.debug( sio.getvalue() )
            SNLogger.exception( str(ex) )
            return str(ex), 500
