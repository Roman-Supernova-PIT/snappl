# IMPORTS Standard
import numpy as np
import pytest
from photutils.psf import ImagePSF
from scipy.stats import moment

# IMPORTS Internal
from snappl.psf import PSF


def test_A25ePSF():

    psf = PSF.get_psf_object( 'A25ePSF', band = 'J129', sca = 1, x = 1277.5, y = 1277.5 )

    assert psf._data.sum() == pytest.approx( 1.0, rel=1e-9 )
    assert psf._data.mean() == pytest.approx( 0.00016866250632484398, rel=1e-9 )
    assert psf._data.std() == pytest.approx( 0.001380374023163906, rel=1e-9 )
    assert psf._x == np.floor(1277.5)
    assert psf._y == np.floor(1277.5)
    assert moment( psf._data, order=2, axis=0 ).sum() == pytest.approx( 0.00013298609785954455, rel=1e-9 )
    assert moment( psf._data, order=2, axis=1 ).sum() == pytest.approx( 0.00013333930898889708, rel=1e-9 )

    psf = PSF.get_psf_object( 'A25ePSF', band = 'J129', sca = 1, x = 1060, y = 1500 )

    assert psf._data.sum() == pytest.approx( 1.0, rel=1e-9 )
    assert psf._data.mean() == pytest.approx( 0.00016866250632484398, rel=1e-9 )
    assert psf._data.std() == pytest.approx( 0.001380374023163906, rel=1e-9 )
    assert psf._x == np.floor(1277.5)
    assert psf._y == np.floor(1277.5)
    assert moment( psf._data, order=2, axis=0 ).sum() == pytest.approx( 0.00013298609785954455, rel=1e-9 )
    assert moment( psf._data, order=2, axis=1 ).sum() == pytest.approx( 0.00013333930898889708, rel=1e-9 )


    psf = PSF.get_psf_object ('A25ePSF', band = 'J129', sca = 1, x = 2900, y = 1300 )

    assert psf._data.sum() == pytest.approx(1.0, rel=1e-9)
    assert moment( psf._data, order=2, axis=0 ).sum() == pytest.approx( 0.0001333651767527484, rel=1e-9 )
    assert moment( psf._data, order=2, axis=1 ).sum() == pytest.approx( 0.00013370914646239755, rel=1e-9 )
    assert psf._x == np.floor(2810.5)
    assert psf._y == np.floor(1277.5)

    for sca in [2, 3]:
        for x in [0, 3500]:
            with pytest.raises( FileNotFoundError, match='No such file or directory' ):
                psf = PSF.get_psf_object ('A25ePSF', band='J129', sca=sca, x=x, y=1300 )


def test_A25ePSF_get_imagepsf():
    psf = PSF.get_psf_object( 'A25ePSF', band = 'J129', sca = 1, x = 1277.5, y = 1277.5 )

    impsf = psf.getImagePSF( imagesampled=False )
    assert isinstance( impsf, ImagePSF )
    assert ( impsf.oversampling == np.array( [3, 3] ) ).all()

    impsf = psf.getImagePSF()
    assert isinstance( impsf, ImagePSF )
    assert ( impsf.oversampling == np.array( [1, 1] ) ).all()
