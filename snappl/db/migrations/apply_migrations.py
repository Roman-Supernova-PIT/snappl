import io
import logging
import hashlib
import uuid
import subprocess
import importlib.resources

from snappl.logger import SNLogger
from snappl.db.db import DBCon, get_connect_info

import psycopg


def apply_migrations():
    dbhost, dbport, dbname, dbuser, dbpass = get_connect_info()

    loglevel = SNLogger.getEffectiveLevel()
    try:
        # Make this not verbose
        SNLogger.set_level( logging.INFO )

        direc = importlib.resources.files( 'snappl.db.migrations' )
        sqlfiles = [ f for f in direc.iterdir() if f.name[-4:] == '.sql' ]
        sqlfiles.sort()

        with DBCon() as conn:
            try:
                rows, _cols = conn.execute( "SELECT filename,md5sum,applied_time "
                                            "FROM _migrations_applied "
                                            "ORDER BY filename" )
                applied = [ row[0] for row in rows ]
                md5sums = [ row[1] for row in rows ]
                when = [ row[2] for row in rows ]
            except psycopg.errors.UndefinedTable:
                conn.rollback()
                conn.execute_nofetch( "CREATE TABLE _migrations_applied( "
                                      "  filename text,"
                                      "  applied_time timestamp with time zone DEFAULT NOW(),"
                                      "  md5sum UUID"
                                      ")" )
                conn.commit()
                applied = []
                md5sums = []
                when = []

            strio = io.StringIO()
            strio.write( "Previously applied:\n" )
            for a, w in zip( applied, when ):
                strio.write( f"   {a:48s}  ({w})\n" )
            SNLogger.info( strio.getvalue() )

            for i, a in enumerate( applied ):
                if sqlfiles[i].name != a:
                    raise ValueError( f"Mismatch between applied and files at file {sqlfiles[i].name}, "
                                      f"applied logged {a}" )
                filemd5 = hashlib.md5()
                with open( sqlfiles[i], "rb" ) as ifp:
                    filemd5.update( ifp.read() )
                if uuid.UUID( filemd5.hexdigest() ) != md5sums[i]:
                    raise ValueError( f"Contents of migration file {a} md5sum does not match "
                                      f"what was previously applied" )

            for i in range( len(applied), len(sqlfiles) ):
                SNLogger.info( f"Applying {sqlfiles[i]}..." )
                rval = subprocess.run( [ "psql", "-h", dbhost, "-p", str(dbport), "-U", dbuser,
                                         "-v", "ON_ERROR_STOP=on",
                                         "-f", sqlfiles[i],
                                         "--single-transaction", "-b",
                                         dbname ],
                                       env={ 'PGPASSWORD': dbpass },
                                       capture_output=True )
                if rval.returncode != 0:
                    SNLogger.error( f"Error processing {sqlfiles[i]}:\n{rval.stderr.decode('utf-8')}" )
                    raise RuntimeError( "SQL error" )
                filemd5 = hashlib.md5()
                with open( sqlfiles[i], "rb" ) as ifp:
                    filemd5.update( ifp.read() )
                md5sum = filemd5.hexdigest()
                conn.execute_nofetch( "INSERT INTO _migrations_applied(filename,md5sum) "
                                      "VALUES(%(fn)s,%(md5)s)",
                                      { 'fn': sqlfiles[i].name, 'md5': md5sum } )
                conn.commit()

    finally:
        SNLogger.set_level( loglevel )


# ======================================================================
if __name__ == "__main__":
    apply_migrations()
