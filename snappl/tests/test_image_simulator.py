import pathlib
import numpy as np

from snappl.image_simulator import ImageSimulator


def test_image_simulator():
    try:
        sim = ImageSimulator(
            seed=42,
            star_center_ra=120.,
            star_center_dec=-13.,
            star_sky_radius=150.,
            alpha=1.,
            nstars=1000,
            psf_class='gaussian',
            psf_kwargs=[ 'sigmax=1.0', 'sigmay=1.0', 'theta=0.' ],
            basename='test_image_simulator',
            width=1024,
            height=1024,
            pixscale=0.11,
            mjds=list( np.arange( 60000., 60065., 5. ) ),
            image_centers=[ 120., -13.,
                            120.005, -13.,
                            120.01, -13.,
                            120., -13.005,
                            120., -13.01,
                            119.995, -13.,
                            119.99, -13.,
                            120., -12.995,
                            120., -12.99,
                            120.01, -12.99,
                            119.99, -12.99,
                            120.01, -13.01,
                            119.99, -13.01 ],
            image_rotations=list( np.arange( 0., 330., 26. ) ),
            zeropoints=[33.],
            sky_noise_rms=[100.],
            sky_level=[10.],
            numprocs=12,
            transient_ra=120.,
            transient_dec=-13.,
            transient_peak_mag=21.,
            transient_peak_mjd=60030.,
            transient_start_mjd=60010.,
            transient_end_mjd=60060.
        )
        sim()
        import pdb; pdb.set_trace()
    finally:
        direc = pathlib.Path( '.' )
        for f in direc.glob( "test_image_simulator*fits" ):
            f.unlink()
