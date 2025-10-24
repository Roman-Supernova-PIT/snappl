# Standard Library
import pandas as pd
import pathlib
import pytest
import uuid
import numbers

# Astronomy
from astropy.table import Table, QTable

# SNPIT
from snappl.lightcurve import Lightcurve


def test_init_lightcurve():
    """Lightcurve class automatically checks that data and metadata follow Wiki guidelines. Let's ensure those work."""
    meta_dict = {
        "provenance_id": uuid.uuid4(),
        "diaobject_id": uuid.uuid4(),
        "diaobject_position_id": uuid.uuid4(),
        "iau_name": "ACoolLightcurve",
        "band": "Y",
        "ra": 70.0,
        "dec": 40.0,
        "ra_err": 1e-5,
        "dec_err": 1e-5,
        "ra_dec_covar": 1e-10,
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

    def check_ltcv( ltcv ):
        nonlocal meta_dict, data_dict
        assert isinstance( ltcv.lightcurve, QTable )
        assert isinstance( ltcv.id, uuid.UUID )
        assert set( ltcv.lightcurve.columns ) == set( data_dict.keys() )
        assert set( ltcv.meta.keys() ) == set( meta_dict.keys() )
        assert all( list( ltcv.lightcurve[col].value ) == data_dict[col] for col in data_dict.keys() )
        for key in ltcv.meta.keys():
            if isinstance( meta_dict[key], uuid.UUID ):
                assert ltcv.meta[key] == str( meta_dict[key] )
            else:
                assert ltcv.meta[key] == meta_dict[key]

    # You can pass data_dict as a dict...
    ltcv = Lightcurve( data=data_dict, meta=meta_dict )
    assert ltcv._filepath is None
    check_ltcv( ltcv )

    # You can explicitly pass the id
    explicitid = uuid.uuid4()
    ltcv = Lightcurve( id=explicitid, data=data_dict, meta=meta_dict )
    assert ltcv._filepath is None
    check_ltcv( ltcv )
    assert ltcv.id == explicitid
    ltcv = Lightcurve( id=str(explicitid), data=data_dict, meta=meta_dict )
    check_ltcv( ltcv )
    assert ltcv.id == explicitid

    # ... or an astropy table...
    data_table = Table(data_dict)
    ltcv = Lightcurve( data=data_table, meta=meta_dict )
    check_ltcv( ltcv )
    assert ltcv._filepath is None

    # ... or a pandas DataFrame.
    data_df = pd.DataFrame(data_dict)
    ltcv = Lightcurve( data=data_df, meta=meta_dict )
    check_ltcv( ltcv )
    assert ltcv._filepath is None

    # You can also initialize with a filepath, which won't be read right away
    ltcv = Lightcurve( filepath="foo/bar" )
    assert ltcv._lightcurve is None
    assert ltcv._filepath == pathlib.Path( "foo/bar" )

    # But you can't pass both a filepath and meta / data
    with pytest.raises( ValueError, match=r"Must specify either filepath, xor \(data and meta\)." ):
        Lightcurve( filepath="foo/bar", data=data_dict, meta=meta_dict )

    # Data requires meta and meta requires data
    with pytest.raises( ValueError, match=r"Must specify either filepath, xor \(data and meta\)." ):
        Lightcurve( data=data_dict )
    with pytest.raises( ValueError, match=r"Must specify either filepath, xor \(data and meta\)." ):
        Lightcurve( meta=meta_dict )

    # If anything is missing it should fail.
    for col in meta_dict.keys():
        bad_meta = meta_dict.copy()
        bad_meta.pop(col)
        with pytest.raises( ValueError, match=( 'band is a required metadata keyword' if col=='band'
                                                else "Incorrect metadata." ) ):
            Lightcurve( data=data_dict, meta=bad_meta )

    for col in data_dict.keys():
        bad_data = data_dict.copy()
        bad_data.pop(col)
        with pytest.raises( ValueError, match="Incorrect or missing data columns." ):
            Lightcurve( data=bad_data, meta=meta_dict )

    # Should Also fail if data or meta are the wrong type.
    bad_things = [ 3, 4.0, "cupcake", True, [1, 2, 3], (1, 2) ]   # mmmm, cupcake
    for bad in bad_things:
        with pytest.raises( TypeError, match="Lightcurve data must be a dict, astropy Table, or pandas DataFrame" ):
            Lightcurve( data=bad, meta=meta_dict )
        with pytest.raises( TypeError, match="Lightcurve meta must be a dict" ):
            Lightcurve( data=data_dict, meta=bad )

    # Should be able to handle additional info beyond the required columns.
    data_dict["apples eaten"] = [5, 6]
    ltcv = Lightcurve( data=data_dict, meta=meta_dict )
    check_ltcv( ltcv )
    # This next assert is redundant if check_ltcv is working right, but it doesn't hurt
    assert "apples eaten" in ltcv.lightcurve.columns

    # Should fail if something is the wrong type.
    for bad in bad_things:
        if not isinstance( bad, numbers.Real ):
            bad_meta = meta_dict.copy()
            bad_meta["ra"] = bad
            with pytest.raises( ValueError, match="Incorrect metadata." ):
                Lightcurve( data=data_dict, meta=bad_meta )

    # Should fail if even a single element of data is the wrong type.
    for bad in bad_things:
        if not isinstance( bad, numbers.Real ):
            bad_data = data_dict.copy()
            bad_data["flux"] = [1000.0, bad]
            with pytest.raises( ValueError, match="Incorrect or missing data columns." ):
                Lightcurve( data=bad_data, meta=meta_dict)


    # Test multiband lightcurve:
    with pytest.raises( ValueError, match="missing data column band" ):
        Lightcurve( data=data_dict, meta=meta_dict, multiband=True )
    with pytest.raises( ValueError, match="missing data column band" ):
        Lightcurve( data=Table(data_dict), meta=meta_dict, multiband=True )
    with pytest.raises( ValueError, match="missing data column band" ):
        Lightcurve( data=pd.DataFrame(data_dict), meta=meta_dict, multiband=True )

    del meta_dict['band']
    data_dict["band"] = [ "Y", "Y" ]
    ltcv = Lightcurve( data=data_dict, meta=meta_dict, multiband=True )
    check_ltcv( ltcv )
    ltcv = Lightcurve( data=Table(data_dict), meta=meta_dict, multiband=True )
    check_ltcv( ltcv )
    ltcv = Lightcurve( data=pd.DataFrame(data_dict), meta=meta_dict, multiband=True )
    check_ltcv( ltcv )

    # Should fail if there are two types of bands but only one surface brightness
    data_dict["band"] = ["Y", "J"]
    with pytest.raises( ValueError, match="Incorrect metadata." ):
        Lightcurve( data=data_dict, meta=meta_dict, multiband=True )

    # But if I include the second surface brightness it should work.
    meta_dict["local_surface_brightness_J"] = 19.0
    ltcv = Lightcurve( data=data_dict, meta=meta_dict, multiband=True )
    check_ltcv( ltcv )


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

    lc = Lightcurve(data_dict, meta_dict)
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
    lc = Lightcurve(data_dict, meta_dict)
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
