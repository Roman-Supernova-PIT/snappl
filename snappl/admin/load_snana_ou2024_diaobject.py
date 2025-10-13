import re
import uuid
import simplejson

import pandas

from snappl.logger import SNLogger
from snappl.utils import SNPITJsonEncoder
import snappl.db.db


def load_snana_ou2024_diaobject( provid, pqf, dbcon=None ):
    match = re.search( r'^snana_([0-9]+)\.parquet$', pqf.name )
    if match is None:
        raise ValueError( f"Failed to parse filename {match}" )
    healpix = int( match.group(1) )
    df = pandas.read_parquet( pqf )

    thingstoinsert = []
    for n, row in enumerate( df.itertuples() ):
        if n % 1000 == 0:
            SNLogger.info( f"File {pqf.name}, {n} of {len(df)} done" )

        params = { k: v for k, v in zip( row.model_param_names, row.model_param_values ) }

        subdict = { 'id':  uuid.uuid4(),
                    'provenance_id': provid,
                    'name': str(row.id),
                    'iauname': None,
                    'ra': float(row.ra),
                    'dec': float(row.dec),
                    'mjd_discovery': float(row.start_mjd),
                    'mjd_peak': float(row.peak_mjd),
                    'mjd_start': float(row.start_mjd),
                    'mjd_end': float(row.end_mjd),
                    'properties': simplejson.dumps(
                        { 'healpix': healpix,
                          'host_id': int(row.host_id),
                          'gentype': int(row.gentype),
                          'model_name': row.model_name,
                          'z_cmb': float(row.z_CMB),
                          'mw_ebv': float(row.mw_EBV),
                          'mw_extinction_applied': float(row.mw_extinction_applied),
                          'av': float(row.AV),
                          'rv': float(row.RV),
                          'v_pec': float(row.v_pec),
                          'host_ra': float(row.host_ra),
                          'host_dec': float(row.host_dec),
                          'host_mag_g': float(row.host_mag_g),
                          'host_mag_i': float(row.host_mag_i),
                          'host_mag_f': float(row.host_mag_F),
                          'host_sn_sep': float(row.host_sn_sep),
                          'peak_mjd': float(row.peak_mjd),
                          'peak_mag_g': float(row.peak_mag_g),
                          'peak_mag_i': float(row.peak_mag_i),
                          'peak_mag_f': float(row.peak_mag_F),
                          'lens_dmu': float(row.lens_dmu),
                          'lens_dmu_applied': bool(row.lens_dmu_applied),
                          'model_params': params },
                        sort_keys=True,
                        cls=SNPITJsonEncoder )
                   }
        thingstoinsert.append( subdict )

    snappl.db.db.DiaObject.bulk_insert_or_upsert( thingstoinsert, dbcon=dbcon.con )
