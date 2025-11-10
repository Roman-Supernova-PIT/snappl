# This code is part of the roman-snpit-db package, done for the Nancy
# Grace Roman Space Telescope Supernova Project Infrastructure Team.
# It's available under a BSD 3-clause license (see ../LICENSE)
#
# Some of this code is in common with code in the DESC FAST DB
# (https://github.com/LSSTDESC/FASTDB), which also has a BSD 3-clause license
# attached to it.

import collections
import types
import uuid
import time
from contextlib import contextmanager

import numpy as np
import psycopg
from psycopg import sql

from snappl.config import Config
from snappl.logger import SNLogger


# ======================================================================
#
# IMPORTANT : make sure that everything in here stays synced with the
#   database schema managed by migrations in ../db
#
# For the most part, that means keeping the all_table_names variable up to date, and
#   making sure that any table that needs a class has one.  (Not all tables need a class.)
# However, some tables may have specific code below.
#
#
# The tables here should be in the order they are safe to drop.  That
# is, assuming you've already decided it's safe to drop all your tables,
# make sure that there are no dependencies that will stop one of the
# tables on the list from being dropped.
all_table_names = [ 'lightcurve', 'summed_image', 'summed_image_component',
                    'l2image', 'diaobject_position', 'diaobject',
                    'provenance_tag', 'provenance_upstream', 'provenance',
                    'passwordlink', 'authuser', '_migrations_applied'
                   ]


# ======================================================================
# Databse connection utilities

def get_connect_info():
    cfg = Config.get()
    dbhost = cfg.value( 'system.db.postgres_host' )
    dbport = cfg.value( 'system.db.postgres_port' )
    dbname = cfg.value( 'system.db.postgres_database' )
    dbuser = cfg.value( 'system.db.postgres_username' )
    dbpasswd = cfg.value( 'system.db.postgres_password' )
    if dbpasswd is None:
        with open( cfg.value( 'system.db.postgres_password_file' ) ) as ifp:
            dbpasswd = ifp.readline().strip()

    return dbhost, dbport, dbname, dbuser, dbpasswd


def get_dbcon():
    """Get a database connection.

    It's your responsibility to roll it back, close it, etc!

    Consider using the DB or DBCon context managers instead of this.
    """

    dbhost, dbport, dbname, dbuser, dbpasswd = get_connect_info()
    ntries = 5
    while ntries > 0:
        try:
            conn = psycopg.connect( dbname=dbname, user=dbuser, password=dbpasswd, host=dbhost, port=dbport,
                                    connect_timeout=1 )
            return conn
        except Exception as e:
            ntries -= 1
            if ntries <= 0:
                raise e
            time.sleep( 1 )


@contextmanager
def DB( dbcon=None ):
    """Get a psycopg.connection in a context manager.

    Always call this as "with DB() as ...".

    Parameters
    ----------
       dbcon: psycopg.connection or None
          If not None, just returns that.  (Doesn't check the type, so
          don't pass the wrong thing.)  Otherwise, makes a new
          connection, and then rolls back and closes that connection
          after it goes out of scope.

    Returns
    -------
       psycopg.connection

    """

    if dbcon is not None:
        yield dbcon
        return

    conn = None
    try:
        conn = get_dbcon()
        yield conn
    finally:
        if conn is not None:
            conn.rollback()
            conn.close()


class DBCon:
    """Class that encapsulates a postgres database connection.

    Prefer using this class in a context manager:

        with DBCon() as dbcon:
            rows, cols = dbcon.execute( query, subdict )
             # do other things

    That way, it will automatically rollback and close the database
    connection when the context manager exists.  Because it rolls back,
    make sure to call the commit() method before the context exits if
    you want any changes you've made to persist.

    Send queries using DBCon.execute_nofetch() and DBCon.execute().

    If for some reason you need direct access to the underlying psycopg
    connection, you can get it from the "con" property.

    """

    def __init__( self, con=None, dictcursor=None ):
        """Instantiate.

        If you use this, you should also use close(), and soon.

        Parameters
        ----------
          con : DBCon, default None
            If you pass another DBCon here, then this DBCon object
            shares exactly the same underlying psycopg connection as
            that other connection.  This is useful if you want to call
            functions that do things to the database (say, create
            temporary tables) within the same connection.  Pass your
            DBCon to that function, and then in that function have it
            pass the DBCon to its DBCon constructor.

            There are implications.  The database connection will *not*
            be rolled back and closed when the context exits if you
            passed a non-None con.  The assumption is that there was an
            outer context that originally created the DBCon that will do
            that.

          dictcursor : bool, default None
            If True, then the cursor uses psycopg.rows.dict_row as its
            row factory.  execute() will return a list of dictionaries,
            with each element of the list being one row of the result.
            If False, then execute returns two lists: a list of tuples
            (the rows) and a list of strings (the column names).

            If None, then will inherit dictcursor from con, unless con
            is not a DBCon, in which case dictcursor will be treated as
            False.

        """

        cfg = Config.get()

        if con is not None:
            self.con_is_mine = False
            if isinstance( con, DBCon ):
                self.con = con.con
                self.echoqueries = con.echoqueries
                self.alwaysexplain = con.alwaysexplain
                self.dictcursor = con.dictcursor if dictcursor is None else dictcursor
                self.cursorisdict = con.cursorisdict if dictcursor is None else dictcursor
            elif isinstance( con, psycopg.Connection ):
                self.con = con
                self.echoqueries = cfg.value( 'system.db.echoqueries' )
                self.alwaysexplain = cfg.value( 'system.db.alwaysexplain' )
                self.dictcursor = bool( dictcursor )
                self.cursorisdict = bool( dictcursor )
            else:
                raise TypeError( f"con must be a DBCon or psycopg.Connection, not a {type(con)}" )

        else:
            self.con_is_mine = True
            self.con = get_dbcon()
            self.echoqueries = cfg.value( 'system.db.echoqueries' )
            self.alwaysexplain = cfg.value( 'system.db.alwaysexplain' )
            self.dictcursor = bool( dictcursor )
            self.cursorisdict = bool( dictcursor )

        self.remake_cursor()


    def __enter__( self ):
        return self


    def __exit__( self, type, value, traceback ):
        if self.con_is_mine:
            self.close()


    def remake_cursor( self, dictcursor=None ):
        """Recreate the cursor used for database communication.

        (This is mainly useful if you want to switch between a
        dictcursor and a regular cursor.)

        Parameters
        ----------
          dictcursor : bool, default None
            If None, will make a cursor that returns dictionaries
            (vs. tuples) for rows based on what was passed to the
            dictcursor argument of the DBCon constructor.  If True,
            makes a cursor that will cause execute() to return a list of
            dictionaries.  If False, makes a cursor that will cause
            execute() to return two lists; the first is a list of tuples
            (the rows), the second is a list of strings (the column
            names).

        """
        self.curcursorisdict = self.dictcursor if dictcursor is None else dictcursor
        if self.curcursorisdict:
            self.cursor = self.con.cursor( row_factory=psycopg.rows.dict_row )
        else:
            self.cursor = self.con.cursor()


    def close( self ):
        """Rolls back and closes the connection.

        In normal usage (i.e. if you created your DBCon() with a "with"
        statement), you never need to call this, as it will be called
        automatically.

        If you did stuff you want kept, make sure to call commit before
        calling this.

        """
        self.con.rollback()
        self.con.close()


    def rollback( self ):
        """Roll back the connection."""
        self.con.rollback()
        self.remake_cursor( self.curcursorisdict )  # ...is this necessary?


    def commit( self ):
        """Commit changes to the database.

        Call this if you've done any INSERT or UPDATE or similar
        commands that change the database, and you want your commands to
        stick.

        """
        self.con.commit()
        self.remake_cursor( self.curcursorisdict )  # ...is this necessary?


    def execute_nofetch( self, q, subdict={}, silent=False):
        """Runs a query where you don't expect to fetch results.

        This is useful if, for instance, you're working with temporary tables.

        Parameters are the same as in execute()

        """
        if self.echoqueries and not silent:
            qprint = q.as_string() if isinstance( q, sql.Composable ) else q
            SNLogger.debug( f"Sending query\n{qprint}\nwith substitutions: {subdict}" )

        if self.alwaysexplain and not silent:
            self.cursor.execute( f"EXPLAIN {q}", subdict )
            rows = self.cursor.fetchall()
            dex = 'QUERY PLAN' if self.curcursorisdict else 0
            nl = '\n'
            SNLogger.debug( f"Query plan:\n{nl.join([r[dex] for r in rows])}" )

        self.cursor.execute( q, subdict )


    def execute( self, q, subdict={}, silent=False ):
        """Runs a query, and returns either (rows, columns) or just rows.

        Parameters
        ----------
          q: str
            A query string that you could feed to a psycopg3 cursor's
            execute() method.  Any parameters that you want substituted
            at runtime (which you should use liberally to avoid setting
            yourself up for SQL injection attacks) should be indiucated
            with %(name)s as usual in psycopg; "name" must they be a key
            in subdict.

          subdict: dict
            The substitution dictionary of parameters to put into the query.

          silent: bool, default False
            Usually ignored.  If you're in debugging mode, and either
            self.echoqueries or self.alwaysexplain is True, then set
            silent to True to supporess that log debug output.


        Returns
        -------
          If the current cursor is a dict cursor, returns a list of dictionaries.

          If the current cursor is not a dict cursor, returns two lists.
          The first is a list of lists, with the rows pulled from the
          dictionary.  The second is a list of column names.

        """
        self.execute_nofetch( q, subdict, silent=silent )
        if self.curcursorisdict:
            if self.cursor.description is None:
                return None
            return self.cursor.fetchall()
        else:
            if self.cursor.description is None:
                return None, None
            cols = [ desc[0] for desc in self.cursor.description ]
            rows = self.cursor.fetchall()
            return rows, cols

    @classmethod
    def columnmap( cls, columns ):
        """A utility function that replaces a list with a dictionary of value: index

        If you call this on the columns returned from execute(), you can
        then use this to index rows.  For example:

        with DBCon() as con:
            rows, cols = con.execute( "SELECT name,var1,var2 FROM table" )
            colmap = con.columnmap( cols )
            for i, row in enumerate( rows ):
                print( f"row {i} name is: {row[colmap['name']]}" )

        This is kind of a dumb example, because you know from the SELECT
        statement that name is in row[0].  It's more useful when you do
        something like "SELECT *", or when you've selected out more than
        a small number of columns.

        This is a really short and stupid function to have this much
        documentation.

        Parmaeters
        ----------
           columns: list of string

        Returns
        -------
           dict
             The keys are the strings from the passed columns.  The
             values are the indexes into the list.

        """
        return { c: i for i, c in enumerate(columns) }


# ======================================================================

class ColumnMeta:
    """Information about a table column.

    An object has properties:
      column_name
      data_type
      column_default
      is_nullable
      element_type
      pytype

    (They can also be read as if the object were a dictionary.)

    It has methods

      py_to_pg( pyobj )
      pg_to_py( pgobj )

    """

    # A dictionary of postgres type to type of the object in Python
    typedict = {
        'uuid': uuid.UUID,
        'smallint': np.int16,
        'integer': np.int32,
        'bigint': np.int64,
        'text': str,
        'jsonb': dict,
        'boolean': bool,
        'real': np.float32,
        'double precision': np.float64
    }

    # A dictionary of "<type">: <2-element tuple>
    # The first elment is the data type as it shows up postgres-side.
    # The second element is a two element tuple of functions:
    #   first element : convert python object to what you need to send to postgres
    #   second element : convert what you got from postgres to python type
    # If a function is "None", it means the identity function.  (So 0=1, P=NP, and Δs<0.)

    typeconverters = {
        # 'uuid': ( str, util.asUUID ),      # Doesn't seem to be needed any more for psycopg3
        'jsonb': ( psycopg.types.json.Jsonb, None )
    }

    def __init__( self, column_name=None, data_type=None, column_default=None,
                  is_nullable=None, element_type=None ):
        self.column_name = column_name
        self.data_type = data_type
        self.column_default = column_default
        self.is_nullable = is_nullable
        self.element_type = element_type


    def __getitem__( self, key ):
        return getattr( self, key )

    @property
    def pytype( self ):
        return self.typedict[ self.data_type ]


    def py_to_pg( self, pyobj ):
        """Convert a python object to the corresponding postgres object for this column.

        The "postgres object" is what would be fed to psycopg's
        cursor.execute() in a substitution dictionary.

        Most of the time, this is the identity function.

        """
        if ( ( self.data_type == "ARRAY" )
             and ( self.element_type in self.typeconverters )
             and ( self.typeconverters[self.element_type][0] is not None )
            ):
            return [ self.typeconverters[self.element_type][0](i) for i in pyobj ]

        elif ( ( self.data_type in self.typeconverters )
               and ( self.typeconverters[self.data_type][0] is not None )
              ):
            return self.typeconverters[self.data_type][0]( pyobj )

        return pyobj


    def pg_to_py( self, pgobj ):
        """Convert a postgres object to python object for this column.

        This "postgres object" is what you got back from a cursor.fetch* call.

        Most of the time, this is the identity function.

        """

        if ( ( self.data_type == "ARRAY" )
             and ( self.element_type in self.typeconverters )
             and ( self.typeconverters[self.element_type][1] is not None )
            ):
            return [ self.typeconverters[self.element_type][1](i) for i in pgobj ]
        elif ( ( self.data_type in self.typeconverters )
               and ( self.typeconverters[self.data_type][1] is not None )
              ):
            return self.typeconverters[self.data_type][1]( pgobj )

        return pgobj


    def __repr__( self ):
        if self.data_type == 'ARRAY':
            return f"ColumnMeta({self.column_name} [ARRAY({self.element_type})]"
        else:
            return f"ColumnMeta({self.column_name} [{self.data_type}])"


# ======================================================================
# ogod, it's like I'm writing my own ORM, and I hate ORMs
#
# But, two things.  (1) I'm writing it, so I know actually what it's doing
#   backend with the PostgreSQL queries, (2) I'm not trying to create a whole
#   new language to learn in place of SQL, I still intend mostly to just use
#   SQL, and (3) sometimes it's worth re-inventing the wheel so that you get
#   just a wheel (and also so that you really get a wheel and not massive tank
#   treads that you are supposed to think act like a wheel)
#
# This class shares a lot of DNA with DBBase in FASTDB
#   ( https://github.com/LSSTDESC/FASTDB )

class DBBase:
    """A base class from which all other table classes derive themselves.

    All subclasses must include:

    __tablename__ = "<name of table in database>"
    _tablemeta = None
    _pk = <list>

    _pk must be a list of strings with the names of the primary key
    columns.  Uusally (but not always) this will be a single-element
    list.

    """

    # A dictionary of "<colum name>": <2-element tuple>
    # The first element is the converter that converts a value into something you can throw to postgres.
    # The second element is the converter that takes what you got from postgres and turns it into what
    #   you want the object to have.
    # Often this can be left as is, but subclasses might want to override it.
    colconverters = {}

    @property
    def tablemeta( self ):
        """A dictionary of column_name : ColumMeta."""
        if self._tablemeta is None:
            self._load_table_meta()
        return self._tablemeta

    @property
    def pks( self ):
        return [ getattr( self, k ) for k in self._pk ]


    @classmethod
    def _load_table_meta( cls, dbcon=None ):
        if cls._tablemeta is not None:
            return

        with DBCon( dbcon ) as con:
            con.remake_cursor( dictcursor=True )
            cols = con.execute( "SELECT c.column_name,c.data_type,c.column_default,c.is_nullable,"
                                "       e.data_type AS element_type "
                                "FROM information_schema.columns c "
                                "LEFT JOIN information_schema.element_types e "
                                "  ON ( (c.table_catalog, c.table_schema, c.table_name, "
                                "        'TABLE', c.dtd_identifier) "
                                "      =(e.object_catalog, e.object_schema, e.object_name, "
                                "        e.object_type, e.collection_type_identifier) ) "
                                "WHERE table_name=%(table)s",
                                { 'table': cls.__tablename__ } )

            cls._tablemeta = { c['column_name']: ColumnMeta(**c) for c in cols }

            for col, meta in cls._tablemeta.items():
                if col in cls.colconverters:
                    if cls.colconverters[col][0] is not None:
                        # Play crazy games because of the confusingness of python late binding
                        def _tmp_py_to_pg( self, pyobj, col=col ):
                            return cls.colconverters[col][0]( pyobj )
                        meta.py_to_pg = types.MethodType( _tmp_py_to_pg, meta )
                    if cls.colconverters[col][1] is not None:
                        def _tmp_pg_to_py( self, pgobj, col=col ):
                            return cls.colconverters[col][1]( pgobj )
                        meta.pg_to_py = types.MethodType( _tmp_pg_to_py, meta )


    def __init__( self, dbcon=None, cols=None, vals=None, _noinit=False, noconvert=True, **kwargs):
        """Create an object based on a row returned from psycopg's cursor.fetch*.

        You could probably use this also just to create an object fresh; in
        that case, you *probably* want to set noconvert to True.

        Parameters
        ----------
          dbcon : DBCon or None
            If passed, will use this to read column information from the
            database if necessary.  If this is None, will briefly make a
            new connection to do that.  (The column information is
            cached in the class, so the connection will only happen the
            first time you make an object of each subclass.)

          cols : list of str
            Column names.  Properties of self with these names will be created.

          vals : list
            Value that go with cols.

          **kwargs : additional arguments
            Instead of passing cols and vals, you can pass the
            properties to be set in the object as named parameters to
            __init__.

          _noinit : bool
            Don't actually initialize the object.  Use this if you just
            need an object and don't have any cols or vals to pass right
            now.  This is probably hardly ever useful, but there are all
            kinds of python games you might play.

          noconvert : bool, default True
            If True, assign the values in vals directly to the
            properties of self whose names are in cols.  If False,
            then vals will be run through the type converters for the
            columns, if any, to convert postgres types to python types.
            Set this to False if you're passing cols and vals as the
            direct output of a SQL SELECT command.

        """

        if _noinit:
            return

        self._load_table_meta( dbcon=dbcon )
        mycols = set( self._tablemeta.keys() )

        if ( cols is None ) != ( vals is None ):
            raise ValueError( "Both or neither of cols and vals must be none." )

        if cols is not None:
            if ( ( not isinstance( cols, collections.abc.Sequence ) ) or ( isinstance( cols, str ) ) or
                 ( not isinstance( vals, collections.abc.Sequence ) ) or ( isinstance( vals, str ) ) or
                 ( len( cols ) != len( vals ) )
                ):
                raise ValueError( "cols and vals most both be lists of the same length" )

        if cols is not None:
            if len(kwargs) > 0:
                raise ValueError( "Can only column values as named arguments "
                                  "if cols and vals are both None" )
        else:
            cols = kwargs.keys()
            vals = kwargs.values()

        keys = set( cols )
        if not keys.issubset( mycols ):
            raise RuntimeError( f"Unknown columns for {self.__tablename__}: {keys-mycols}" )

        for col in mycols:
            setattr( self, col, None )

        self._set_self_from_fetch_cols_row( cols, vals, noconvert=noconvert )


    def to_dict( self, columns=None, dbcon=None ):
        """Return a dictionary with the database fields."""

        self._load_table_meta( dbcon=dbcon )

        retval = {}
        if columns is not None:
            if any( c not in self.tablemeta for c in columns ):
                raise ValueError( f"Not all of the columns in {columns} are in the table" )
        else:
            columns = self.tablemeta.keys()

        for col in columns:
            if hasattr( self, col ):
                retval[col] = getattr( self, col )
            else:
                retval[col] = None

        return retval


    def _set_self_from_fetch_cols_row( self, cols, fetchrow, noconvert=False, dbcon=None ):
        if self._tablemeta is None:
            self._load_table_meta( dbcon=dbcon )

        if noconvert:
            for col, val in zip( cols, fetchrow ):
                setattr( self, col, val )
        else:
            for col, val in zip( cols, fetchrow ):
                setattr( self, col, self._tablemeta[col].pg_to_py( val ) )


    def _build_subdict( self, columns=None, dbcon=None ):
        """Create a substitution dictionary that could go into a cursor.execute() statement.

        The columns that are included in the dictionary interacts with default
        columns in a potentially confusing way.

        IF self does NOT have an attribute corresponding to a column, then
        that column will not be in the returned dictionary.

        IF self.{column} is None, and the table has a default that is *not*
        None, that column will not be in the returned dictionary.

        In other words, if self.{column} doesn't exist, or self.{column} is
        None, it means that the actual table column will get the PostgreSQL
        default value when this subdict is used (assuming the query is constructed
        using only the keys of the subdict).

        (It's not obvious that this is the best behavior; see comment in
        method source.)

        Paramters
        ---------
          columns : list of str, optional
            If given, include these columns in the returned subdict; by
            default, include all columns from the table.  (But, not not all
            columns may actually be in the returned subdict; see above.)  If
            the list includes any columns that don't actually exist for the
            table, an exception will be raised.

        Returns
        -------
          dict of { column_name: value }

        """

        self._load_table_meta( dbcon=dbcon )

        subdict = {}
        if columns is not None:
            if any( c not in self.tablemeta for c in columns ):
                raise ValueError( f"Not all of the columns in {columns} are in the table" )
        else:
            columns = self.tablemeta.keys()

        for col in columns:
            if hasattr( self, col ):
                val = getattr( self, col )
                if val is None:
                    # What to do when val is None is not necessarily obvious.  There are a couple
                    #  of possibilities:
                    # (1) We really want to set this field to NULL in the database
                    # (2) It just hasn't been set yet in the object, so we want the
                    #     database row to keep what it has, or (in the case of an insert)
                    #     get the default value.
                    # How to know which is the case?  Assume that if the column_default is None,
                    # then we're in case (1), but if it's not None, we're in case (2).
                    if self.tablemeta[col]['column_default'] is None:
                        subdict[ col ] = None
                else:
                    subdict[ col ] = self.tablemeta[ col ].py_to_pg( val )

        return subdict


    @classmethod
    def _construct_pk_query_where( cls, *args, me=None ):
        if cls._tablemeta is None:
            cls._load_table_meta()

        if me is not None:
            if len(args) > 0:
                raise ValueError( "Can't pass both me and arguments" )
            args = me.pks

        if len(args) != len( cls._pk ):
            raise ValueError( f"{cls.__tablename__} has a {len(cls._pk)}-element compound primary key, but "
                              f"you passed {len(args)} values" )
        q = "WHERE "
        _and = ""
        subdict = {}
        for k, v in zip( cls._pk, args ):
            q += f"{_and} {k}=%({k})s "
            subdict[k] = cls._tablemeta[k].py_to_pg( v )
            _and = "AND"

        return q, subdict

    @classmethod
    def get( cls, *args, dbcon=None ):
        """Get an object from a table row with the specified primary key(s)."""

        q, subdict = cls._construct_pk_query_where( *args )
        q = f"SELECT * FROM {cls.__tablename__} {q}"
        with DBCon( dbcon, dictcursor=False ) as con:
            rows, cols = con.execute( q, subdict )

        if len(rows) > 1:
            raise RuntimeError( f"Found multiple rows of {cls.__tablename__} with primary keys {args}; "
                                f"this should never happen." )
        if len(rows) == 0:
            return None

        obj = cls( cols=cols, vals=rows[0] )
        return obj

    @classmethod
    def get_batch( cls, pks, dbcon=None ):
        """Get a list of objects based on primary keys.

        Arguments
        ---------
          pks : list of lists
            Each element of the list must be a list whose length matches
            the length of self._pk.

        Returns
        -------
          list of objects
            Each object will be an instance of the class this class
            method was called on.

        """

        if ( not isinstance( pks, collections.abc.Sequence ) ) or ( isinstance( pks, str ) ):
            raise TypeError( f"Must past a list of lists, each list having {len(cls._pk)} elwements." )

        if cls._tablemeta is None:
            cls._load_table_meta( dbcon )

        comma = ""
        mess = ""
        subdict = {}
        pktypes = [ cls._tablemeta[k]['data_type'] for k in cls._pk ]
        for dex, pk in enumerate( pks ):
            if len( pk ) != len( cls._pk ):
                raise ValueError( f"{pk} doesn't have {len(cls._pk)} elements, should match {cls._pk}" )
            mess += f"{comma}("
            subcomma=""
            for subdex, ( pkval, pkcol ) in enumerate( zip( pk, cls._pk ) ):
                mess += f"{subcomma}%(pk_{dex}_{subdex})s"
                subdict[ f'pk_{dex}_{subdex}' ] = cls._tablemeta[pkcol].py_to_pg( pkval )
                subcomma = ","
            mess += ")"
            comma = ","
        comma = ""
        _and = ""
        collist = ""
        onlist = ""
        for subdex, ( pk, pktyp ) in enumerate( zip( cls._pk, pktypes ) ):
            collist += f"{comma}{pk}"
            onlist += f"{_and} t.{pk}={cls.__tablename__}.{pk} "
            _and = "AND"
            comma = ","

        with DBCon( dbcon, dictcursor=False ) as con:
            q = f"SELECT * FROM {cls.__tablename__} JOIN (VALUES {mess}) AS t({collist}) ON {onlist} "
            rows, cols = con.execute( q, subdict )

        objs = []
        for row in rows:
            obj = cls( _noinit=True )
            obj._set_self_from_fetch_cols_row( cols, row )
            objs.append( obj )

        return objs

    @classmethod
    def getbyattrs( cls, dbcon=None, **attrs ):
        if cls._tablemeta is None:
            cls._load_table_meta( dbcon )

        # WORRY : when we edit attrs below, will that also affect anything outside
        #   this function?  E.g. if it's called with a ** itself.
        q = f"SELECT * FROM {cls.__tablename__} WHERE "
        _and = ""
        for k in attrs.keys():
            attrs[k] = cls._tablemeta[k].py_to_pg( attrs[k] )
            q += f"{_and} {k}=%({k})s "
            _and = "AND"

        with DBCon( dbcon, dictcursor=False ) as con:
            rows, cols = con.execute( q, attrs )

        objs = []
        for row in rows:
            obj = cls( _noinit=True )
            obj._set_self_from_fetch_cols_row( cols, row )
            objs.append( obj )

        return objs

    def refresh( self, dbcon=None ):
        q, subdict = self._construct_pk_query_where( *self.pks )
        q = f"SELECT * FROM {self.__tablename__} {q}"

        with DBCon( dbcon, dictcursor=False ) as con:
            rows, cols = con.execute( q, subdict )

        if len(rows) > 1:
            raise RuntimeError( f"Found more than one row in {self.__tablename__} with primary keys "
                                f"{self.pks}; this probably shouldn't happen." )
        if len(rows) == 0:
            raise ValueError( f"Failed to find row in {self.__tablename__} with primary keys {self.pks}" )

        self._set_self_from_fetch_cols_row( cols, rows[0] )


    def insert( self, dbcon=None, refresh=True, nocommit=False ):
        if refresh and nocommit:
            raise RuntimeError( "Can't refresh with nocommit" )

        subdict = self._build_subdict( dbcon=dbcon )

        q = ( f"INSERT INTO {self.__tablename__}({','.join(subdict.keys())}) "
              f"VALUES ({','.join( [ f'%({c})s' for c in subdict.keys() ] )})" )

        with DBCon( dbcon, dictcursor=False ) as con:
            con.execute( q, subdict )
            if not nocommit:
                con.commit()
                if refresh:
                    self.refresh( con )

    def delete_from_db( self, dbcon=None, nocommit=False ):
        where, subdict = self._construct_pk_query_where( me=self )
        q = f"DELETE FROM {self.__tablename__} {where}"
        with DBCon( dbcon, dictcursor=False ) as con:
            con.execute( q, subdict )
            con.commit()


    def update( self, dbcon=None, refresh=False, nocommit=False ):
        if refresh and nocommit:
            raise RuntimeError( "Can't refresh with nocommit" )

        subdict = self._build_subdict( dbcon=dbcon )
        q = ( f"UPDATE {self.__tablename__} SET "
              f"{','.join( [ f'{c}=%({c})s' for c in subdict.keys() if c not in self._pk ] )} " )
        where, wheresubdict = self._construct_pk_query_where( me=self )
        subdict.update( wheresubdict )
        q += where

        with DBCon( dbcon, dictcursor=False ) as con:
            con.execute( q, subdict )
            if not nocommit:
                con.commit()
                if refresh:
                    self.refresh( con )

    @classmethod
    def bulk_insert_or_upsert( cls, data, upsert=False, assume_no_conflict=False,
                               dbcon=None, nocommit=False ):
        """Try to efficiently insert a bunch of data into the database.

        ROB TODO DOCUMENT QUIRKS

        Parmeters
        ---------
          data: dict or list
            Can be one of:
              * a list of dicts.  The keys in all dicts (including order!) must be the same
              * a dict of lists
              * a list of objects of type cls

          upsert: bool, default False
             If False, then objects whose primary key is already in the
             database will be ignored.  If True, then objects whose
             primary key is already in the database will be updated with
             the values in dict.  (SQL will have ON CONFLICT DO NOTHING
             if False, ON CONFLICT DO UPDATE if True.)

          assume_no_conflict: bool, default Falsea
             Usually you just want to leave this False.  There are
             obscure kludge cases (e.g. if you're playing games and have
             removed primary key constraints and you know what you're
             doing-- this happens in load_snana_fits.py, for instance)
             where the conflict clauses cause the sql to fail.  Set this
             to True to avoid having those clauses.

          nocommit : bool, default False
             This one is very scary and you should only use it if you
             really know what you're doing.  If this is True, not only
             will we not commit to the database, but we won't copy from
             the table temp_bulk_upsert to the table of interest.  It
             doesn't make sense to set this to True unless you also
             pass a dbcon.  This is for things that want to do stuff to
             the temp table before copying it over to the main table, in
             which case it's the caller's responsibility to do that copy
             and commit to the database.

        Returns
        -------
           int OR string
             If nocommit=False, returns the number of rows actually
             inserted (which may be less than len(data)).

             If nocommit=True, returns the string to execute to copy
             from the temp table to the final table.

        """

        if len(data) == 0:
            return

        if isinstance( data, list ) and isinstance( data[0], dict ):
            columns = data[0].keys()
            # Alas, psycopg's copy seems to index the thing it's passed,
            #   so we can't just pass it d.values()
            values = [ list( d.values() ) for d in data ]
        elif isinstance( data, dict ):
            columns = list( data.keys() )
            values = [ [ data[c][i] for c in columns ] for i in range(len(data[columns[0]])) ]
        elif isinstance( data, list ) and isinstance( data[0], cls ):
            # This isn't entirely satisfying.  But, we're going
            #   to assume that things that are None because they
            #   want to use database defaults are going to be
            #   the same in every object.
            sd0 = data[0]._build_subdict( dbcon=dbcon )
            columns = sd0.keys()
            data = [ d._build_subdict( columns=columns, dbcon=dbcon ) for d in data ]
            # Alas, psycopg's copy seems to index the thing it's passed,
            #   so we can't just pass it d.values()
            values = [ list( d.values() ) for d in data ]
        else:
            raise TypeError( f"data must be something other than a {cls.__name__}" )

        with DBCon( dbcon, dictcursor=False ) as con:
            con.execute( "DROP TABLE IF EXISTS temp_bulk_upsert" )
            con.execute( f"CREATE TEMP TABLE temp_bulk_upsert (LIKE {cls.__tablename__})" )
            with con.cursor.copy( f"COPY temp_bulk_upsert({','.join(columns)}) FROM STDIN" ) as copier:
                for v in values:
                    copier.write_row( v )

            if not assume_no_conflict:
                if not upsert:
                    conflict = f"ON CONFLICT ({','.join(cls._pk)}) DO NOTHING"
                else:
                    conflict = ( f"ON CONFLICT ({','.join(cls._pk)}) DO UPDATE SET "
                                 + ",".join( f"{c}=EXCLUDED.{c}" for c in columns ) )
            else:
                conflict = ""

            q = f"INSERT INTO {cls.__tablename__} SELECT * FROM temp_bulk_upsert {conflict}"

            if nocommit:
                return q
            else:
                con.cursor.execute( q )
                ninserted = con.cursor.rowcount
                con.execute( "DROP TABLE temp_bulk_upsert" )
                con.commit()
                return ninserted


# ======================================================================

class AuthUser( DBBase ):
    __tablename__ = "authuser"
    _tablemeta = None
    _pk = [ 'id' ]

    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )


# ======================================================================

class PasswordLink( DBBase ):
    __tablename__ = "passwordlink"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class Provenance( DBBase ):
    __tablename__ = "provenance"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class DiaObject( DBBase ):
    __tablename__ = "diaobject"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class DiaObjectPosition( DBBase ):
    __tablename__ = "diaobject_position"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class L2Image( DBBase ):
    __tablename__ = "l2image"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class SummedImage( DBBase ):
    __tablename__ = "summed_image"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class SegMap( DBBase ):
    __tablename__ = "segmap"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class Lightcurve( DBBase ):
    __tablename__ = "lightcurve"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

class Spectrum1d( DBBase ):
    __tablename__ = "spectrum1d"
    _tablemeta = None
    _pk = [ 'id' ]


# ======================================================================

# class DiaObjectClassification( DBBase ):
#     __tablename__ = "diaobject_classification"
#     _tablemeta = None
#     _pk = [ 'id' ]
