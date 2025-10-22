import numpy as np
import pandas as pd
from pathlib import Path
import uuid

from astropy.table import Table, QTable
import astropy.units as u

from snappl.logger import SNLogger


class lightcurve:
    """A class to store and save lightcurve data across different SNPIT photometry codes."""

    def __init__(self, data, meta):

        assert isinstance(data, dict) or isinstance(data, Table) or isinstance(data, QTable) \
             or isinstance(data, pd.DataFrame), "LC Data must be a dict, astropy Table, or pandas DataFrame"
        assert isinstance(meta, dict), "LC Metadata must be a dict"

        self.data = data.copy()
        self.meta = meta.copy()

        # These should match the wiki: https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        # This is a bit of a moving target, so it's possible the list below is out of date when you are reading this.
        self.required_meta_cols = [
            "provenance_id",
            "diaobject_id",
            "iau_name",
            "ra",
            "ra_err",
            "dec",
            "dec_err"
        ]

        self.required_data_cols = [
            "mjd",
            "band",
            "flux",
            "flux_err",
            "zpt",
            "NEA",
            "sky_background",
        ]

        required_data_col_types = [float, str, float, float, float, float, float]
        required_meta_col_types = [uuid.UUID, uuid.UUID, str, float, float, float, float]
        unique_bands = np.unique(self.data["band"])
        for b in unique_bands:
            self.required_meta_cols.append(f"local_surface_brightness_{b}")
            required_meta_col_types.append(float)

        meta_cols = list(self.meta.keys())
        for col, col_type in zip(self.required_meta_cols, required_meta_col_types):
            assert col in meta_cols, "Missing required metadata column {col}"
            assert isinstance(self.meta[col], col_type), (
                f"Metadata column {col} must be of type {col_type} but" + f" it's actually {type(meta[col])}."
            )
            if col_type is uuid.UUID:
                self.meta[col] = str(self.meta[col]) # UUIDs can't be saved in this form, they must be strings.


        data_cols = list(self.data.keys()) if type(self.data) is dict else list(self.data.columns)
        for col, col_type in zip(self.required_data_cols, required_data_col_types):
            assert col in data_cols, f"Missing required data column {col}"
            assert all([isinstance(item, col_type) for item in data[col]]), \
                f"Data column {col} must be of type {col_type}"

    def write(self, output_dir, filename=None, filetype="parquet", overwrite=False):
        """Save the lightcurve to a parquet file."""
        # These too are standardized on the wiki:
        # https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        units = {"mjd": u.d, "flux": u.photon/u.second, "flux_err": u.photon/u.second,
                "band": "", "NEA": "pixels", "sky_background": u.photon/u.second}

        lc = QTable(data=self.data, meta=self.meta, units=units)

        # Here we sort required columns to the front of the table.
        data_cols = list(lc.columns)
        sorted_cols = self.required_data_cols + [col for col in data_cols if col not in self.required_data_cols]
        lc = lc[sorted_cols]

        provenance_id = self.meta["provenance_id"]
        diaobject_id = self.meta["diaobject_id"]
        lc_file = f"{str(provenance_id)}_ltcv_{str(diaobject_id)}.{filetype}"
        SNLogger.info(f"Saving lightcurve to {lc_file}")
        output_path = Path(output_dir) / Path(lc_file)
        lc.write(output_path, overwrite=overwrite, format="parquet")
