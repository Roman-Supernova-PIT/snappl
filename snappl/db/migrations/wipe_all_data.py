# TODO : wrap this with --do and --really-do options
# TODO : add ability to also wipe users
# TODO : add ability to also wipe migrations

from snappl.db.db import DBCon, all_table_names
from snappl.logger import SNLogger

# By default, we don't want to drop users or migrations
tablenames = all_table_names.copy()
tablenames.remove( "authuser" )
tablenames.remove( "_migrations_applied" )

with DBCon() as con:
    try:
        for table in tablenames:
            SNLogger.warning( f"Truncating table {table}..." )
            # Yeah, yeah, there's sort of an SQL injection attack here,
            #   though if somebody can edit the code to modify the
            #   all_table_names variable, they could just as easily edit
            #   the code to put whatever SQL in here.  So, using an
            #   f-string on the SQL query below isn't really a worry.
            con.execute_nofetch( f"TRUNCATE TABLE {table} CASCADE" )
        con.commit()
    except Exception:
        SNLogger.exception( "Exception wiping all data." )
        SNLogger.error( "(Probably) not committing the changes." )
