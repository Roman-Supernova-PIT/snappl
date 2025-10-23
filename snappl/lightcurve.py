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

        self._data = data.copy()
        self._meta = meta.copy()

        # These should match the wiki: https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        # This is a bit of a moving target, so it's possible the list below is out of date when you are reading this.

        meta_type_dict = {
            "provenance_id": (uuid.UUID, type(None)),
            "diaobject_id": (uuid.UUID, type(None)),
            "iau_name": str,
            "ra": float,
            "ra_err": float,
            "dec": float,
            "dec_err": float
        }

        data_unit_dict = {
            "mjd": float,
            "band": str,
            "flux": float,
            "flux_err": float,
            "zpt": float,
            "NEA": float,
            "sky_background": float,
        }

        self.required_data_cols = list(data_unit_dict.keys())
        self.required_meta_cols = list(meta_type_dict.keys())

        unique_bands = np.unique(self._data["band"])
        for b in unique_bands:
            self.required_meta_cols.append(f"local_surface_brightness_{b}")
            meta_type_dict[f"local_surface_brightness_{b}"] = float

        meta_cols = list(self._meta.keys())
        for col in self.required_meta_cols:
            assert col in meta_cols, f"Missing required metadata column {col}"
            col_type = meta_type_dict.get(col)
            SNLogger.debug(f"Checking metadata column {col} of type {col_type}")
            SNLogger.debug(f"col_type type is {type(col_type)}")
            SNLogger.debug(f"self._meta[col] type is {type(self._meta[col])}")
            assert isinstance(self._meta[col], col_type), (
                f"Metadata column {col} must be of type {col_type} but" + f" it's actually {type(meta[col])}."
            )
            if isinstance(self._meta[col], uuid.UUID):
                SNLogger.debug(f"Converting metadata column {col} from UUID to string for saving.")
                self._meta[col] = str(self._meta[col]) # UUIDs can't be saved in this form, they must be strings.


        data_cols = list(self._data.keys()) if type(self._data) is dict else list(self._data.columns)
        for col in self.required_data_cols:
            assert col in data_cols, f"Missing required data column {col}"
            col_type = data_unit_dict.get(col)
            assert all([isinstance(item, col_type) for item in data[col]]), \
                f"Data column {col} must be of type {col_type}"

    def write(self, output_dir, filename=None, filetype="parquet", overwrite=False):
        """Save the lightcurve to a parquet file."""
        # These too are standardized on the wiki:
        # https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve
        units = {"mjd": u.d, "flux": u.photon/u.second, "flux_err": u.photon/u.second,
                "band": "", "NEA": "pixels", "sky_background": u.photon/u.second}

        lc = QTable(data=self._data, meta=self._meta, units=units)

        # Here we sort required columns to the front of the table.
        data_cols = list(lc.columns)
        sorted_cols = self.required_data_cols + [col for col in data_cols if col not in self.required_data_cols]
        lc = lc[sorted_cols]

        provenance_id = self._meta["provenance_id"]
        diaobject_id = self._meta["diaobject_id"]
        lc_file = filename if filename is not None else f"{provenance_id}_ltcv_{diaobject_id}.{filetype}"
        SNLogger.info(f"Saving lightcurve to {lc_file}")
        output_path = Path(output_dir) / Path(lc_file)
        if filetype == "parquet":
            fmt = "parquet"
        elif filetype == "ecsv":
            fmt = "ascii.ecsv"
        lc.write(output_path, overwrite=overwrite, format=fmt)

    @property
    def data(self):
        return self._data

    @property
    def meta(self):
        return self._meta
