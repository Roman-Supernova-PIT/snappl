import argparse
from matplotlib import pyplot

import numpy as np
import photutils.aperture

from snappl.image import FITSImageStdHeaders

parser = argparse.ArgumentParser( 'ap_phot_ismulated_images.py' )
parser.add_argument( '-i', '--image-basenames', nargs='+', required=True,
                     help="Image basenames.  Leave off _image.fits" )
parser.add_argument( '-r', '--ra', type=float, required=True, help="Transient RA" )
parser.add_argument( '-d', '--dec', type=float, required=True, help="Transient Dec" )
parser.add_argument( '--rad', type=float, default=5.0, help="Aperture radius in pixels (default 5)" )
parser.add_argument( '--transient-peak-mag', '--tp', type=float, default=21.,
                     help="Peak magnitude of transient (default: 21)" )
parser.add_argument( '--transient-start-mjd', '--tt0', type=float, default=60010.,
                     help="Start MJD of transient linear rise (default: 60010.)" )
parser.add_argument( '--transient-peak-mjd', '--ttm', type=float, default=60030.,
                     help="Peak MJD of transient (default: 60030.)" )
parser.add_argument( '--transient-end-mjd', '--tt1', type=float, default=60060.,
                     help="End MJD of transient linear decay (default: 60060.)" )
parser.add_argument( '-s', '--save-plot', default=None,
                     help="Save plot to this file" )
args = parser.parse_args()


images = [ FITSImageStdHeaders(p, std_imagenames=True) for p in args.image_basenames ]
mjds = np.array( [ i.mjd for i in images ] )

fluxen = []
apflux = []
apfluxerr = []
for image in images:
    data = image.get_data( which='data' )[0]
    noise = image.get_data( which='noise' )[0]
    peakflux = 10 ** ( ( args.transient_peak_mag - image.zeropoint ) / -2.5 )
    flux = 0.
    if ( image.mjd >= args.transient_start_mjd ) and ( image.mjd <= args.transient_end_mjd ):
        mjdedge = ( args.transient_start_mjd if image.mjd < args.transient_peak_mjd
                    else args.transient_end_mjd )
        flux = peakflux * ( image.mjd - mjdedge ) / ( args.transient_peak_mjd - mjdedge )
    fluxen.append( flux )

    wcs = image.get_wcs()
    x, y = wcs.world_to_pixel( args.ra, args.dec )
    aperture = photutils.aperture.CircularAperture( (x, y), args.rad )
    res = photutils.aperture.aperture_photometry( data, aperture, error=noise )
    apflux.append( res['aperture_sum'][0] )
    apfluxerr.append( res['aperture_sum_err'][0] )

fluxen = np.array( fluxen )
apflux = np.array( apflux )
apfluxerr = np.array( apfluxerr )

fig, ax = pyplot.subplots()
fig.set_tight_layout( True )
ax.errorbar( mjds, apflux - fluxen, apfluxerr, linestyle='none', marker='s', color='red',
             label=f'{args.rad}-pix radius aperture' )
xmin, xmax = ax.get_xlim()
ax.hlines( 0, xmin, xmax, linestyle='dotted', color='black' )
ax.set_label( "MJD" )
ax.set_ylabel( "Apphot flux - true flux (counts)" )
ax.legend()
fig.show()
if args.save_plot is not None:
    fig.savefig( args.save_plot )
pyplot.show()
