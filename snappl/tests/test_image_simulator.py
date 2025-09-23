import numpy as np

from snappl.image_simulator import ImageSimulator


def test_image_simulator():
    try:
        sim = ImageSimulator(
            seed=42,
            star_center_ra=120.,
            star_center_dec=-13.,
            mjds=np.arange( 60000., 60065., 5. ),
            image_centers=[ 120., -13.,
                            120.02, -13.,
                            120.04, -13.,
                            120., -13.02,
                            120., -13.04,
                            119.98, -13.,
                            119.96, -13.,
                            120., -12.98,
                            120, -12.96,
                            
