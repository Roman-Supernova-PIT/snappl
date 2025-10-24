# Standard Library
import pandas as pd
import pathlib
import pytest
import uuid
import numbers

# Astronomy
from astropy.table import Table, QTable

# SNPIT
from snappl.lightcurve import lightcurve


# Testing intializing with filepath is tested with test_write_and_read below
def test_init_lightcurve():
    """Lightcurve class automatically checks that data and metadata follow Wiki guidelines. Let's ensure those work."""
    meta_dict = {
        "provenance_id": uuid.uuid4(),
        "diaobject_id": uuid.uuid4(),
        "diaobject_position_id": uuid.uuid4(),
        "iau_name": "ACoolLightcurve",
        "band": "Y",
        "ra": 70.0,
        "ra_err": 1e-5,
        "dec": 40.0,
        "dec_err": 1e-5,
        "local_surface_brightness_Y": 18.0,
    }

    data_dict = {
        "mjd": [60000.0, 60001.0],
        "flux": [1000.0, 1100.0],
        "flux_err": [50.0, 55.0],
        "zpt": [25.0, 25.0],
        "NEA": [5.0, 5.0],
        "sky_rms": [200.0, 210.0],
        "pointing": [1, 2],
        "sca": [16, 18],
        "pix_x": [ 128., 64. ],
        "pix_y": [ 13.3, 47.7 ]
    }

    # You can pass data_dict as a dict...
    ltcv = lightcurve( data=data_dict, meta=meta_dict )
    assert isinstance( ltcv.lightcurve, QTable )
    assert ltcv._filepath is None
    assert isinstance( ltcv.id, uuid.UUID )

    # You can explicitly pass the id
    explicitid = uuid.uuid4()
    ltcv = lightcurve( id=explicitid, data=data_dict, meta=meta_dict )
    assert isinstance( ltcv.lightcurve, QTable )
    assert ltcv._filepath is None
    assert ltcv.id == explicitid
    ltcv = lightcurve( id=str(explicitid), data=data_dict, meta=meta_dict )
    assert ltcv.id == explicitid

    # ... or an astropy table...
    data_table = Table(data_dict)
    ltcv = lightcurve( data=data_table, meta=meta_dict )
    assert isinstance( ltcv.lightcurve, QTable )
    assert ltcv._filepath is None

    # ... or a pandas DataFrame.
    data_df = pd.DataFrame(data_dict)
    ltcv = lightcurve( data=data_df, meta=meta_dict )
    assert isinstance( ltcv._lightcurve, QTable )
    assert ltcv._filepath is None

    # You can also initialize with a filepath, which won't be read right away
    ltcv = lightcurve( filepath="foo/bar" )
    assert ltcv._lightcurve is None
    assert ltcv._filepath == pathlib.Path( "foo/bar" )

    # But you can't pass both a filepath and meta / data
    with pytest.raises( ValueError, match="Must specify filepath, or (data and meta), but not both." ):
        lightcurve( filepath="foo/bar", data=data_dict, meta=meta_dict )

    # If anything is missing it should fail.
    for col in meta_dict.keys():
        bad_meta = meta_dict.copy()
        bad_meta.pop(col)
        with pytest.raises( ValueError, match="Incorrect metadata." ):
            lightcurve( data=data_dict, meta=bad_meta )

    for col in data_dict.keys():
        bad_data = data_dict.copy()
        bad_data.pop(col)
        with pytest.raises( ValueError, match="Incorrect or missing data columns." ):
            lightcurve( data=bad_data, meta=meta_dict )

    # Should Also fail if data or meta are the wrong type.
    bad_things = [3, 4.0, "cupcake", True, [1, 2, 3], (1, 2), None]
    for bad in bad_things:
        with pytest.raises( TypeError, match="Lightcurve data must be a dict, astropy Table, or pandas DataFrame" ):
            lightcurve( data=bad, meta=meta_dict )
        with pytest.raises( TypeError, meatch="Lightcurve meta must be a dict" ):
            lightcurve( data=data_dict, meta=bad )

    # Should be able to handle additional info beyond the required columns.
    data_dict["apples eaten"] = [5, 6]
    ltcv = lightcurve( data=data_dict, meta=meta_dict )
    assert isinstance( ltcv.lightcurve, QTable )
    assert "apples eaten" in ltcv.lightcurve.columns

    # Should fail if something is the wrong type.
    for bad in bad_things:
        if not isinstance( bad, numbers.Floating ):
            bad_meta = meta_dict.copy()
            bad_meta["ra"] = bad
            with pytest.raises( ValueError, match="Incorrect metadata." ):
                lightcurve( data=data_dict, meta=bad_meta )

    # Should fail if even a single element of data is the wrong type.
    for bad in bad_things:
        if not isinstance( bad, numbers.Floating ):
            bad_data = data_dict.copy()
            bad_data["flux"] = [1000.0, bad]
            with pytest.raises( ValueError, match="Incorrect or missing data columns." ):
                lightcurve( data=bad_data, meta=meta_dict)


    # Test multiband lightcurve:
    with pytest.raises( ValueError, match="band is a required metadata keyword" ):
        lightcurve( data=data_dict, meta=meta_dict, multiband=True )

    del meta_dict['band']
    data_dict["band"] = [ "Y", "Y" ]
    ltcv = lightcurve( data=data_dict, meta=meta_dict, multiband=True )
    assert isinstance( ltcv.lightcurve, QTable )

    # Should fail if there are two types of bands but only one surface brightness
    data_dict["band"] = ["Y", "J"]
    with pytest.raises( ValueError, match="Incorrect metadata." ):
        lightcurve( data=data_dict, meta=meta_dict )

    # But if I include the second surface brightness it should work.
    meta_dict["local_surface_brightness_J"] = 19.0
    ltcv = lightcurve( data=data_dict, meta=meta_dict)
    assert isinstance( ltcv.lightcurve, QTable )


def test_write_lightcurve( ou2024_test_lightcurve ):
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
    try:
        lc.write(pathlib.Path(__file__).parent / "testdata")
        read_table = Table.read(pathlib.Path(__file__).parent / "testdata" /
        f"{str(meta_dict['provenance_id'])}_ltcv_{str(meta_dict['diaobject_id'])}.parquet", format="parquet")
        metadata = read_table.meta
        for col in data_dict.keys():
            assert all(read_table[col] == data_dict[col])
        for col in meta_dict.keys():
            if isinstance(meta_dict[col], uuid.UUID):
                assert metadata[col] == str(meta_dict[col])
            else:
                assert metadata[col] == meta_dict[col]
    finally:
        # Clean up test file
        (pathlib.Path(__file__).parent / "testdata" /
         f"{str(meta_dict['provenance_id'])}_ltcv_{str(meta_dict['diaobject_id'])}.parquet").unlink(missing_ok=True)

    # The lightcurve should save all of the required columns to the front of the table,
    # regardless of the order they were provided in.
    data_dict = {
        "mjd": [60000.0, 60001.0],
        "unrequired_col": [3.0, 4.0],
        "band": ["Y", "Y"],
        "flux": [1000.0, 1100.0],
        "another_unrequired_col": ["cupcake", "banana"],
        "flux_err": [50.0, 55.0],
        "zpt": [25.0, 25.0],
        "NEA": [5.0, 5.0],
        "yet_another_unrequired_col": [True, False],
        "sky_background": [200.0, 210.0],
    }
    lc = lightcurve(data_dict, meta_dict)
    n_required = len([f for f in data_dict.keys() if "unrequired" not in f])
    try:
        lc.write(pathlib.Path(__file__).parent / "testdata")
        read_table = Table.read(pathlib.Path(__file__).parent / "testdata" /
            f"{str(meta_dict['provenance_id'])}_ltcv_{str(meta_dict['diaobject_id'])}.parquet", format="parquet")

        for col in data_dict.keys():
            if "unrequired" not in col:
                assert col in read_table.columns[:n_required]

    finally:
        # Clean up test file
        (pathlib.Path(__file__).parent / "testdata" /
         f"{str(meta_dict['provenance_id'])}_ltcv_{str(meta_dict['diaobject_id'])}.parquet").unlink(missing_ok=True)
