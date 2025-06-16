import numpy as np

import astropy.table
import photutils.psf


# You probably want stampsize = 2 * 5 * 2√(2ln2) * max(sigmax,sigmay)
def make_gaussian_psf( oversamp=3, sigmax=1.2, sigmay=None, stampsize=None, x0=511, y0=511 ):
    if oversamp % 2 != 1:
        raise ValueError( "Please use an odd oversampling factor." )

    sigmay = sigmax if sigmay is None else sigmay

    # Default to a stamp size of 2 * 5 FHWMs (so "radius" 5 FWHM)
    if stampsize is None:
        stampsize = int( np.ceil( 10 * 2.35482 * max( sigmax, sigmay ) ) )
        stampsize += 1 if stampsize % 2 ==0 else 0
    if stampsize % 2 != 1:
        raise ValueError( "stampsize must be odd" )

    oversampsize = oversamp * stampsize
    ctr = oversampsize // 2
    xvals = np.arange( -ctr, ctr+1 )
    yvals = np.arange( -ctr, ctr+1 )
    ovsigmax = oversamp * sigmax
    ovsigmay = oversamp * sigmay
    data = np.exp( -( xvals[np.newaxis,:]**2 / ( 2. * ovsigmax**2 ) +
                      yvals[:,np.newaxis]**2 / ( 2. * ovsigmay**2 ) ) )
    # photutils expects an oversampled PSF to be normalized like this:
    data /= data.sum() / ( oversamp**2 )

    psf = photutils.psf.ImagePSF( data, flux=1, x_0=x0, y_0=y0, oversampling=oversamp )

    return psf


def make_fake_image( skynoise=10., starflux=100000., nx=1024, ny=1024, x=511, y=511,
                     oversamp=3, sigmax=1.2, sigmay=None, stampsize=None ):
    rng = np.random.default_rng()
    image = rng.normal( scale=skynoise, size=(ny, nx) )

    xc = int( np.floor( x + 0.5 ) )
    yc = int( np.floor( y + 0.5 ) )

    psf = make_gaussian_psf( oversamp=oversamp, sigmax=sigmax, sigmay=sigmay, stampsize=stampsize, x0=x, y0=y )
    xmin = -( stampsize // 2 ) + xc
    xmax = xmin + stampsize
    ymin = -( stampsize // 2 ) + yc
    ymax = ymin + stampsize
    # WORRY : did I get the x, y order right?
    xvals, yvals = np.meshgrid( np.arange( xmin, xmax ), np.arange( ymin, ymax ) )
    # Not adding poisson noise to our PSF; deal
    image[ ymin:ymax, xmin:xmax ] += psf( xvals, yvals ) * starflux

    return image, psf


# **********************************************************************
# Actual experiments

# Have a plenty-sampled PSF with a sigma of 1.2, stampsize 29, oversampling by 3)
psf = make_gaussian_psf( oversamp=3, sigmax=1.2, stampsize=29, x0=511, y0=511 )
xvals = np.arange( 511 - (29//2), 511 + (29//2) + 1 )
yvals = np.arange( 511 - (29//2), 511 + (29//2) + 1 )
xvals, yvals = np.meshgrid( xvals, yvals )
print( f"1.2-sigma PSF clip sums to {psf( xvals, yvals ).sum()}" )

# Have a PSF with a 1-pixel FWHM (so σ = 1/(2√(2ln2)) = 0.42 ), stampsize 11, oversamped 5x
psf = make_gaussian_psf( oversamp=5, sigmax=0.42, stampsize=11, x0=511, y0=511 )
xvals = np.arange( 511 - (29//2), 511 + (29//2) + 1 )
yvals = np.arange( 511 - (29//2), 511 + (29//2) + 1 )
xvals, yvals = np.meshgrid( xvals, yvals )
print( f"0.42-sigma PSF clip sums to {psf( xvals, yvals ).sum()}" )


# Now let's try some PSF photometry and see how it does
# We are always going to use sky noise 10, and just not bother
#  with star poisson noise for now (because we're naughty)

# First with the happy big star
image, psf = make_fake_image( oversamp=3, sigmax=1.2, stampsize=29 )
noiseim = np.full_like( image, 10. )
fit_shape = ( 15, 15 )
photor = photutils.psf.PSFPhotometry( psf, fit_shape )
phot = photor( image, error=noiseim,
               init_params=astropy.table.Table( { 'x_init': [510.5], 'y_init': [513.], 'flux_init': [95000] } ) )
print( f"Fit flux of 100000-flux star for sigma = 1.2: {phot['flux_fit'][0]}; "
       f"(x,y)=({phot['x_fit'][0]}, {phot['y_fit'][0]}" )

# Now with a little star
image, psf = make_fake_image( oversamp=5, sigmax=0.42, stampsize=11 )
fit_shape = ( 7, 7 )
photor = photutils.psf.PSFPhotometry( psf, fit_shape )
phot = photor( image, error=noiseim,
               init_params=astropy.table.Table( { 'x_init': [511.2], 'y_init': [510.9], 'flux_init': [120000] } ) )
print( f"Fit flux of 100000-flux star for sigma = 0.42: {phot['flux_fit'][0]}; "
       f"(x,y)=({phot['x_fit'][0]}, {phot['y_fit'][0]}" )


# RESULTS OF A RUN:
#    root@655734bb3457:/snappl/experimentation# python play_with_photutils.py
#    1.2-sigma PSF clip sums to 1.0000000000018092
#    0.42-sigma PSF clip sums to 1.1267689222010988
#    Fit flux of 100000-flux star for sigma = 1.2: 99833.32184334665; (x,y)=(511.00130567398907, 510.99895105013127
#    Fit flux of 100000-flux star for sigma = 0.42: 100005.90585339173; (x,y)=(511.0002593061244, 511.0001099684552
#
# CONCLUSION:
#
# For PSFs whose FWHM is less than ~2 pixels on the original
# image, the stamps you get from the __call__ method of a photutils
# ImagePSF are not properly normalize.  (Interestingly, they are too big
# by the same factor that lanczos4 interpolation gives....)  However,
# photutils PSFPhotometry works in such a way that it takes this into
# account (...or just doesn't use __call__) and produces reliable results.
#
# Which is all well and good if you just want to use PSFPhotometry, but
# if you need thumbnails for other purposes (e.g. schene modelling),
# that is very sad.
