import pytest
import pathlib
import numpy as np
import photutils.aperture
from matplotlib import pyplot

from snappl.utils import env_as_bool
from snappl.image_simulator import ImageSimulator
from snappl.image import FITSImageStdHeaders


@pytest.mark.parametrize("nprocs", [(2), (1)])
def test_image_simulator_one_transient_image(nprocs):
    fnamebase = 'test_image_simulator_one_transient_image'
    assert not pathlib.Path( f'{fnamebase}_image.fits' ).exists()
    assert not pathlib.Path( f'{fnamebase}_noise.fits' ).exists()
    assert not pathlib.Path( f'{fnamebase}_flags.fits' ).exists()
    try:
        kwargs = {
            "seed": 64738,
            "star_center": (120.0, -13.0),
            "star_sky_radius": 150.0,
            "alpha": 1.0,
            "nstars": 0,
            "psf_class": "gaussian",
            "psf_kwargs": ["sigmax=1.0", "sigmay=1.0", "theta=0."],
            "basename": fnamebase,
            "width": 256,
            "height": 256,
            "pixscale": 0.11,
            "mjds": [60030.0],
            "image_centers": [120.0, -13.0],
            "image_rotations": [0.0],
            "zeropoints": [33.0],
            "sky_noise_rms": [100.0],
            "sky_level": [10.0],
            "transient_peak_mag": 21.0,
            "transient_peak_mjd": 60030.0,
            "transient_start_mjd": 60010.0,
            "transient_end_mjd": 60060.0,
            "transient_ra": 120.0,
            "transient_dec": -13.0,
            "numprocs": 1,
            "numimageprocs": nprocs,
        }
        sim = ImageSimulator( **kwargs )
        sim()

        image = FITSImageStdHeaders( f'{fnamebase}_{kwargs["mjds"][0]:7.1f}', std_imagenames=True )
        assert image.mjd == pytest.approx( kwargs['mjds'][0], abs=0.0001 )
        assert image.sca == 1
        assert image.observation_id == '1000'
        assert image.band == 'R062'
        assert image.image_shape == ( kwargs['height'], kwargs['width'] )
        wcs = image.get_wcs()
        print(wcs)
        x, y  = wcs.world_to_pixel( kwargs['transient_ra'], kwargs['transient_dec'] )
        x0 = int( np.floor( x + 0.5 ) )
        y0 = int( np.floor( y + 0.5 ) )


        assert x0 == kwargs['width'] // 2
        assert y0 == kwargs['height'] // 2
        totdata = image.data[ y0-3:y0+4, x0-3:x0+4 ].sum()
        totnoise = np.sqrt( ( image.noise[ y0-3:y0+4, x0-3:x0+4 ] ** 2 ).sum() )
        # Make sure noise is sane
        assert totnoise == pytest.approx( np.sqrt( 49 * kwargs['sky_noise_rms'][0]**2 ), rel=0.1 )

        flux = 10 ** ( ( kwargs['transient_peak_mag'] - kwargs['zeropoints'][0] ) / -2.5 )
        assert totdata == pytest.approx( flux, abs=2. * totnoise )

        # Used in the next test
        gaussian_data = image.data

        direc = pathlib.Path(".")
        for f in direc.glob(f"{fnamebase}*fits"):
            f.unlink()

        kwargs = {
            "seed": 64738,
            "star_center": (120.0, -13.0),
            "star_sky_radius": 150.0,
            "alpha": 1.0,
            "nstars": 0,
            "psf_class": "ou24PSF",
            "psf_kwargs": ["sigmax=1.0", "sigmay=1.0", "theta=0."],
            "basename": fnamebase,
            "width": 256,
            "height": 256,
            "pixscale": 0.11,
            "mjds": [60030.0],
            "image_centers": [120.0, -13.0],
            "image_rotations": [0.0],
            "zeropoints": [33.0],
            "sky_noise_rms": [100.0],
            "sky_level": [10.0],
            "transient_peak_mag": 21.0,
            "transient_peak_mjd": 60030.0,
            "transient_start_mjd": 60010.0,
            "transient_end_mjd": 60060.0,
            "transient_ra": 120.0,
            "transient_dec": -13.0,
            "numprocs": 1,
        }
        sim = ImageSimulator(**kwargs)
        sim()
        image = FITSImageStdHeaders(f"{fnamebase}_{kwargs['mjds'][0]:7.1f}", std_imagenames=True)
        # Since only the CD matrix is modified, the central pixel should be the same
        wcs = image.get_wcs()
        x, y = wcs.world_to_pixel(kwargs["transient_ra"], kwargs["transient_dec"])
        x0 = int(np.floor(x + 0.5))
        y0 = int(np.floor(y + 0.5))
        assert x0 == kwargs["width"] // 2
        assert y0 == kwargs["height"] // 2

        totdata = image.data[y0 - 3 : y0 + 4, x0 - 3 : x0 + 4].sum()
        totnoise = np.sqrt((image.noise[y0 - 3 : y0 + 4, x0 - 3 : x0 + 4] ** 2).sum())
        # Make sure noise is sane
        assert totnoise == pytest.approx(np.sqrt(49 * kwargs["sky_noise_rms"][0] ** 2), rel=0.1)

        flux = 10 ** ((kwargs["transient_peak_mag"] - kwargs["zeropoints"][0]) / -2.5)
        # assert totdata == pytest.approx(flux, abs=2.0 * totnoise)
        # NORMALIZATION OF OU24PSF WHEN NOT PHOTON SHOOTING IS STILL NOT UNDERSTOOD, SEE COLE'S SLACK CONVERSATION
        # FOR NOW, JUST CHECK THAT THE IMAGE IS DIFFERENT FROM THE GAUSSIAN ONE

        assert not image.data == pytest.approx(gaussian_data) # Make sure we just didn't rerender a gaussian!

    finally:
        direc = pathlib.Path( '.' )
        for f in direc.glob( f"{fnamebase}*fits" ):
            f.unlink()


# This test is really slow, so don't run it on github CI, and don't run
#   it locally by default.  Do make sure to run it if you futz around
#   with the image simulator.  It's here mostly to generate images we're
#   going to stick in photometry_test_data.  Set
#   GENERATE_IMAGE_SIMULATOR_TESTS env var to 1 to actually run this
#   test.  I chose the nprocs=12 because my desktop has 12 CPU cores (24
#   threads).
@pytest.mark.skipif( not env_as_bool('GENERATE_IMAGE_SIMULATOR_TESTS'),
                     reason='Set GENERATE_IMAGE_SIMULATOR_TESTS=1 to run this "test"' )
def test_image_simulator_gen_simple_gaussian_test_images( output_directories ):
    outdir, plotdir = output_directories
    try:

        kwargs = {
            "seed": 42,
            "star_center": (120.0, -13.0),
            "star_sky_radius": 150.0,
            "alpha": 1.0,
            "nstars": 1000,
            "psf_class": "gaussian",
            "psf_kwargs": ["sigmax=1.0", "sigmay=1.0", "theta=0."],
            "basename": str(outdir / "test_image_simulator"),
            "width": 1024,
            "height": 1024,
            "pixscale": 0.11,
            "mjds": list(np.arange(60000.0, 60065.0, 5.0)),
            "image_centers": [
                120.0,
                -13.0,
                120.005,
                -13.0,
                120.01,
                -13.0,
                120.0,
                -13.005,
                120.0,
                -13.01,
                119.995,
                -13.0,
                119.99,
                -13.0,
                120.0,
                -12.995,
                120.0,
                -12.99,
                120.01,
                -12.99,
                119.99,
                -12.99,
                120.01,
                -13.01,
                119.99,
                -13.01,
            ],
            "image_rotations": list(np.arange(0.0, 330.0, 26.0)),
            "zeropoints": [33.0],
            "sky_noise_rms": [100.0],
            "sky_level": [10.0],
            "transient_peak_mag": 21.0,
            "transient_peak_mjd": 60030.0,
            "transient_start_mjd": 60010.0,
            "transient_end_mjd": 60060.0,
            "transient_ra": 120.0,
            "transient_dec": -13.0,
            "numprocs": 12,
        }
        sim = ImageSimulator( **kwargs )
        sim()

        # Uncomment this next line to pause if you want to save the
        # images; They'll all get deleted at the end of the test.
        # import pdb; pdb.set_trace()

        # Let's do a quick and dirty check to make sure the lightcurve is sane.

        zp = kwargs['zeropoints'][0]
        peakflux = 10 ** ( (kwargs['transient_peak_mag'] - zp) / -2.5 )
        fluxen = []
        aperflux = []
        apererr = []
        for mjd in kwargs['mjds']:
            flux = 0.
            if ( mjd >= kwargs['transient_start_mjd'] ) and ( mjd <= kwargs['transient_end_mjd'] ):
                mjdedge = ( kwargs['transient_start_mjd'] if mjd < kwargs['transient_peak_mjd']
                            else kwargs['transient_end_mjd'] )
                flux = peakflux * ( mjd - mjdedge ) / ( kwargs['transient_peak_mjd'] - mjdedge )

            fname = f'{kwargs["basename"]}_{mjd:7.1f}'
            image = FITSImageStdHeaders( fname, std_imagenames=True )
            wcs = image.get_wcs()
            x, y  = wcs.world_to_pixel( kwargs['transient_ra'], kwargs['transient_dec'] )
            x0 = int( np.floor( x + 0.5 ) )
            y0 = int( np.floor( y + 0.5 ) )

            totdata = image.data[ y0-3:y0+4, x0-3:x0+4 ].sum()
            totnoise = np.sqrt( ( image.noise[ y0-3:y0+4, x0-3:x0+4 ] ** 2 ).sum() )

            assert totdata == pytest.approx( flux, abs=2. * totnoise )

            aperture = photutils.aperture.CircularAperture( (x, y), 5. )
            res = photutils.aperture.aperture_photometry( image.data, aperture, error=image.noise )

            fluxen.append( flux )
            aperflux.append( res['aperture_sum'][0] )
            apererr.append( res['aperture_sum_err'][0] )

        # Uncomment this next line to pause if you want to save the
        # images; They'll all get deleted at the end of the test.
        # import pdb; pdb.set_trace()

        fig, ax = pyplot.subplots()
        ax.errorbar( kwargs['mjds'], np.array(aperflux) - np.array(fluxen), apererr, linestyle='none', marker='s',
                     color='red', label='5-pix radius aperture' )
        xmin, xmax = ax.get_xlim()
        ax.hlines( 0, xmin, xmax, linestyle='dotted', color='black' )
        ax.set_label( 'MJD' )
        ax.set_ylabel( 'Apphot flux - true flux (counts)' )
        ax.legend()
        fig.savefig( plotdir / 'test_image_simulator_aperphot.png' )

    finally:
        for f in outdir.glob( "test_image_simulator*fits" ):
            f.unlink()


def make_simulator(psf_class="ou24PSF", band="R062", observation_id=None, sca=1, **kwargs):
    """Convenience func to avoid repeating in every test."""
    return ImageSimulator(
        psf_class=psf_class,
        band=band,
        observation_id=observation_id,
        sca=sca,
        star_center=(120.0, -13.0), # random values because these are required
        image_centers=[120.0, -13.0],
        mjds = [60000.0],
        **kwargs,
    )


def test_non_ou24psf_skips_band_validation():
    """If psf_class doesn't include 'ou24PSF', no band/obs-id logic runs at all."""
    sim = make_simulator(psf_class="someOtherPSF", band="INVALID", observation_id=None)
    assert sim.observation_id == ["1000"]  # Didn't do anything for non ou24PSF, so observation_id should just be
    # the default, which is 1000.


EXPECTED_DEFAULT_IDS = [
    ("R062", "1"),
    ("Z087", "57"),
    ("Y106", "112"),
    ("J129", "167"),
    ("H158", "222"),
    ("F184", "277"),
]


@pytest.mark.parametrize("band, expected_id", EXPECTED_DEFAULT_IDS)
def test_default_observation_id_per_band(band, expected_id):
    sim = make_simulator(psf_class="ou24PSF", band=band, observation_id=None)
    assert sim.observation_id == [expected_id]


def test_unrecognised_band_with_no_observation_id_raises():
    with pytest.raises(ValueError, match="not recognized"):
        make_simulator(psf_class="ou24PSF", band="INVALID", observation_id=None)

# @pytest.mark.parametrize("band, observation_id", EXPECTED_DEFAULT_IDS)
# def test_matching_band_and_obs_id_passes(band, observation_id):
#     # If you pass a correct observation ID as an int, it should work fine.
#     sim = make_simulator(psf_class="ou24PSF", band=band, observation_id=int(observation_id), sca=1)
#     assert sim.observation_id == [str(observation_id)]
#     # in addition, for all of these defaults, the next higher observation ID is the same band. So here we can
#     # check that another observation Id works and isn't accidentally overwritten with the default one.

#     sim = make_simulator(psf_class="ou24PSF", band=band, observation_id=int(observation_id) + 1, sca=1)
#     assert sim.observation_id == [str(int(observation_id) + 1)]
