import argparse
from snappl.db.db import DBCon


def main():
    parser = argparse.ArgumentParser( 'schema_to_rst', description='Postgres schema of one table to RST' )
    parser.add_argument( '-t', '--table', nargs='+',
                         default=[ 'provenance', 'provenance_upstream', 'provenance_tag',
                                   'l2image', 'summed_image', 'summed_image_component',
                                   'diaobject', 'diaobject_position',
                                   'lightcurve',
                                   'authuser', 'passwordlink' ] )
    args = parser.parse_args()

    with DBCon( dictcursor=True ) as con:
        for table in args.table:
            rows = con.execute( "SELECT %(tab)s::regclass::oid AS tabid", { 'tab': table } )
            if len(rows) == 0:
                raise ValueError( "Didn't find table {table}" )
            tabid = rows[0]['tabid']
            rows = con.execute( "SELECT description FROM pg_catalog.pg_description "
                                "WHERE objoid=%(tabid)s AND objsubid=0",
                                { "tabid": tabid } )
            if len(rows) > 0:
                tabdesc = rows[0]['description']
            else:
                tabdesc = "(no description)"

            cols = con.execute( "SELECT c.column_name,c.ordinal_position,c.data_type,c.is_nullable,c.column_default,\n"
                                "       d.description\n"
                                "FROM information_schema.columns c\n"
                                "LEFT JOIN pg_catalog.pg_description d ON objoid=%(tabid)s\n"
                                "                                      AND objsubid=c.ordinal_position\n"
                                "WHERE table_schema='public' AND table_name=%(tab)s\n"
                                "ORDER BY ordinal_position",
                                { 'tab': table, 'tabid': tabid  } )

            print( "\n" )
            tablehdr = f"**Table:** ``{table}``"
            print( tablehdr )
            print( '-' * len(tablehdr) )
            print( "\n" )
            print( f"{tabdesc}\n" )

            namewid = max( [ len(c['column_name'])+4 for c in cols ] )
            namewid = max( namewid, len("Column") )
            typewid = max( [ len(c['data_type'])+4 for c in cols ] )
            typewid = max( typewid, len("Type") )
            defwid = max( [ len(str(c['column_default']))+4 for c in cols ] )
            defwid = max( defwid, len("Default") )
            descwid = max( [ len(str(c['description'])) for c in cols ] )
            descwid = max( descwid, len("Comment") )

            print( f"{'='*namewid} {'='*typewid} ===== {'='*defwid} {'='*descwid}" )
            print( f"{'Column':{namewid}s} {'Type':{typewid}s} null? {'Default':{defwid}s} {'Comment':{descwid}s}" )
            print( f"{'='*namewid} {'='*typewid} ===== {'='*defwid} {'='*descwid}" )

            for col in cols:
                cn = f"``{col['column_name']}``"
                dt = f"``{col['data_type']}``"
                de = f"``{str(col['column_default'])}``"
                print( f"{cn:{namewid}s} {dt:{typewid}s} {col['is_nullable']:5s} {str(de):{defwid}s} "
                       f"{str(col['description']):{descwid}s}" )

            print( f"{'='*namewid} {'='*typewid} ===== {'='*defwid} {'='*descwid}" )


# ======================================================================

if __name__ == "__main__":
    main()
