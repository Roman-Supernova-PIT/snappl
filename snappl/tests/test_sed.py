import os
import pathlib
import pytest
import numpy as np

from astropy.io import fits  # noqa: F401

from snappl.sed import OU2024_Truth_SED


@pytest.mark.skipif(os.getenv("GITHUB_SKIP"), reason="Skipping test until we have galsim data")
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


@pytest.mark.skipif(os.getenv("GITHUB_SKIP"), reason="Skipping test until we have galsim data")
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
