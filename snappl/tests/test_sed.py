import numpy as np
import pandas as pd
import pathlib
import pytest
import tempfile

from astropy.io import fits  # noqa: F401

from snappl.sed import OU2024_Truth_SED, Single_CSV_SED


def test_ou24_get_sn_sed():
    sed_obj = OU2024_Truth_SED(20172782)
    sed = sed_obj.get_sed(20172782, 62476)
    lam = sed._spec.x
    flux = sed._spec.f
    sn_lam_test = np.load(pathlib.Path(__file__).parent
                          / "testdata/SED/sn_lam_test.npy")
    sn_flambda_test = np.load(pathlib.Path(__file__).parent
                              / "testdata/SED/sn_flambda_test.npy")
    np.testing.assert_allclose(lam, sn_lam_test, atol=1e-7)
    np.testing.assert_allclose(flux, sn_flambda_test, atol=1e-7)


def test_ou24_get_star_sed():
    sed_obj = OU2024_Truth_SED(40973149150, isstar=True)
    sed = sed_obj.get_sed(40973149150)
    lam = sed._spec.x
    flux = sed._spec.f
    star_lam_test = np.load(pathlib.Path(__file__).parent
                            / "testdata/SED/star_lam_test.npy")
    star_flambda_test = np.load(pathlib.Path(__file__).parent
                                / "testdata/SED/star_flambda_test.npy")
    np.testing.assert_allclose(flux, star_flambda_test, atol=1e-7)
    np.testing.assert_allclose(lam, star_lam_test, atol=1e-7)


def test_single_csv_sed():
    df = pd.DataFrame({'wavelength': [1, 2], 'flux': [3, 4]})

    for septype in [",", " ", "\t"]:
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w', encoding='utf-8') as tmp:
            df.to_csv(tmp.name, index=False, sep=septype, header=False)
            temp_path = tmp.name

        sed_obj = Single_CSV_SED(temp_path)
        sed = sed_obj.get_sed()
        lam = sed._spec.x
        flux = sed._spec.f
        np.testing.assert_allclose(lam, [1, 2], atol=1e-7)
        np.testing.assert_allclose(flux, [3, 4], atol=1e-7)

    for septype in ["-", ";", "/"]:
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w', encoding='utf-8') as tmp:
            df.to_csv(tmp.name, index=False, sep=septype, header=False)
            temp_path = tmp.name

        with pytest.raises(ValueError, match="Could not read the SED file"):
            sed_obj = Single_CSV_SED(temp_path)
            sed = sed_obj.get_sed()
