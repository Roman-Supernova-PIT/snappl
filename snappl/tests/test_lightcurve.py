# Standard Library
import pandas as pd
import pathlib
import pyarrow.parquet as pq
import pytest
import uuid

# Astronomy
from astropy.table import Table

# SNPIT
from snappl.lightcurve import lightcurve
from snpit_utils.logger import SNLogger


def test_init_lightcurve():
    """Lightcurve class automatically checks that data and metadata follow Wiki guidelines. Let's ensure those work."""
    meta_dict = {
        "provenance_id": uuid.uuid4(),
        "diaobject_id": uuid.uuid4(),
        "iau_name": "ACoolLightcurve",
        "ra": 70.0,
        "ra_err": 1e-5,
        "dec": 40.0,
        "dec_err": 1e-5,
        "local_surface_brightness_Y": 18.0,
    }

    data_dict = {
        "mjd": [60000.0, 60001.0],
        "band": ["Y", "Y"],
        "flux": [1000.0, 1100.0],
        "flux_err": [50.0, 55.0],
        "zpt": [25.0, 25.0],
        "NEA": [5.0, 5.0],
        "sky_background": [200.0, 210.0],
    }

    # You can pass data_dict as either a dict...
    lightcurve(data_dict, meta_dict)
    # ... or an astropy table.

    data_table = Table(data_dict)
    lightcurve(data_table, meta_dict)

    # If anything is missing it should fail.
    for col in meta_dict.keys():
        bad_meta = meta_dict.copy()
        bad_meta.pop(col)
        SNLogger.debug(f"popping {col}")
        with pytest.raises(AssertionError) as e:
            lightcurve(data_dict, bad_meta)
        assert e

    for col in data_dict.keys():
        bad_data = data_dict.copy()
        bad_data.pop(col)

        if col == "band":
            # If band is missing, raises a KeyError because band is needed to determine required meta columns.
            with pytest.raises(KeyError):
                lightcurve(bad_data, meta_dict)

        else:
            with pytest.raises(AssertionError):
                lightcurve(bad_data, meta_dict)

    # Should Also fail if data or meta are the wrong type.
    bad_things = [3, 4.0, "cupcake", True, [1, 2, 3], (1, 2), None]
    for bad in bad_things:
        with pytest.raises(AssertionError):
            lightcurve(bad, meta_dict)
        with pytest.raises(AssertionError):
            lightcurve(data_dict, bad)

    # Should be able to handle additional info beyond the required columns.
    data_dict["apples eaten"] = [5, 6]
    lightcurve(data_dict, meta_dict)

    # Should fail if something is the wrong type.
    for bad in bad_things:
        if isinstance(bad, float):
            continue
        else:
            bad_meta = meta_dict.copy()
            bad_meta["ra"] = bad
            with pytest.raises(AssertionError):
                lightcurve(data_dict, bad_meta)

    # Should fail if even a single element of data is the wrong type.
    for bad in bad_things:
        if isinstance(bad, float):
            continue
        else:
            bad_data = data_dict.copy()
            bad_data["flux"] = [1000.0, bad]
            with pytest.raises(AssertionError):
                lightcurve(bad_data, meta_dict)

    # Should fail if there are two types of bands but only one surface brightness
    data_dict["band"] = ["Y", "J"]
    with pytest.raises(AssertionError):
        lightcurve(data_dict, meta_dict)

    # But if I include the second surface brightness it should work.
    meta_dict["local_surface_brightness_J"] = 19.0
    lightcurve(data_dict, meta_dict)


def test_write_lightcurve():
    meta_dict = {
        "provenance_id": uuid.uuid4(),
        "diaobject_id": uuid.uuid4(),
        "iau_name": "ACoolLightcurve",
        "ra": 70.0,
        "ra_err": 1e-5,
        "dec": 40.0,
        "dec_err": 1e-5,
        "local_surface_brightness_Y": 18.0,
    }

    data_dict = {
        "mjd": [60000.0, 60001.0],
        "band": ["Y", "Y"],
        "flux": [1000.0, 1100.0],
        "flux_err": [50.0, 55.0],
        "zpt": [25.0, 25.0],
        "NEA": [5.0, 5.0],
        "sky_background": [200.0, 210.0],
    }

    lc = lightcurve(data_dict, meta_dict)
    lc.write(pathlib.Path(__file__).parent / "testdata")
    read_df = pd.read_parquet(pathlib.Path(__file__).parent / "testdata" / f"{str(meta_dict['provenance_id'])}_ltcv_{str(meta_dict['diaobject_id'])}.parquet")
    metadata = pq.read_metadata(pathlib.Path(__file__).parent / "testdata" /\
         f"{str(meta_dict['provenance_id'])}_ltcv_{str(meta_dict['diaobject_id'])}.parquet").metadata
    SNLogger.debug(metadata)
    for col in data_dict.keys():
        assert all(read_df[col] == data_dict[col])
    for col in meta_dict.keys():
        if isinstance(meta_dict[col], uuid.UUID):
            assert all(metadata[col] == str(meta_dict[col]))
        else:
            assert all(metadata[col] == meta_dict[col])
