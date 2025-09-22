import re
import argparse

import numpy as np
import astropy.wcs

from snappl.psf import PSF
from snappl.image import ManualFITSImage
from snappl.wcs import AstropyWCS


def _kwargs_list_to_kwargs( kwargs_list ):
    unpack = re.compile( "^([a-zA-Z0-9_+])\s*=\s*(.*[^\s])\s*$" )
    kwargs = {}
    for arg in kwargs_list:
        mat = unpack.search( arg )
        if mat is None:
            raise ValueError( f"Failed to parse key=val from '{arg}'" )
        try:
            kwargs[ mat.group(1) ] = int( mat.group(2) )
        except ValueError:
            try:
                kwargs[ mat.group(1) ] = float( mat.group(2) )
            except ValueError:
                kwargs[ mat.group(1) ] = mat.group(2)
    return kwargs
                         


class ImageSimulationStar:
    def __init__( self, ra, dec, mag, psf ):
        self.ra = ra
        self.dec = dec
        self.mag = mag
        self.psf = psf

    def add_to_image( self, image, varimage, x, y, zeropoint=None, gain=1., noisy=True, rng=None ):
        x0 = int( np.floor( x + 0.5 ) )
        y0 = int( np.floor( y + 0.5 ) )
        flux = 10 ** ( ( self.mag - zeropoint ) / -2.5 )
        stamp = self.psf.get_stamp( x, y, x0=x0, y0=y0, flux=flux )
        if noisy:
            if rng is None:
                rng = np.random.default_rng()
            w = stamp >= 0
            var = np.zeros( stamp.shape )
            var[ w ] = stamp[ w ] / gain
            stamp[ w ] += rng.normal( stamp[w], np.sqrt( var[w] ) )

        sx0 = 0
        sx1 = stamp.shape[1]
        sy0 = 0
        sy1 = stamp.shape[0]

        ix0 = x0 - stamp.shape[1] // 2
        ix1 = ix0 + stamp.shape[1]
        iy0 = y0 - stamp.shape[0] // 2
        iy1 = iy0 + stamp.shape[0]

        if ix0 < 0:
            sx0 -= ix0
            ix0 = 0
        if iy0 < 0:
            sy0 -= iy0
            iy0 = 0
        if ix1 > image.shape[1]:
            sx1 -= ( ix1 - image.shape[1] )
            ix1 = image.shape[1]
        if iy1 > image.shape[0]:
            sy1 -= ( iy1 - image.shape[0] )
            iy1 = image.shape[0]

        image[ iy0:iy1, ix0:ix1 ] += stamp[ sy0:sy1, sx0:sx1 ]
        if varimage is not None:
            varimage[ iy0:iy1, ix0:ix1 ] += var[ sy0:sy1, sx0:sx1 ]


class ImageSimulatorStarCollection:
    def __init__( self, ra=None, dec=None, fieldrad=None, m0=None, m1=None, alpha=None, nstars=None,
                  psf_class='gaussian', psf_kwargs=['sigmax=1.', 'sigmay=1.', 'theta=0.'],
                  rng=None ):
        if rng is None:
            self.rng = np.random.default_rng()
        kwargs = _kwargs_list_to_kwargs( psf_kwargs )
        self.psf = PSF.get_psf_object( psf_class, **kwargs )

        stars = []
        norm = ( alpha + 1 ) / ( m1 ** (alpha + 1) - m0 ** (alpha + 1) )
        for i in range(nstars):
            r = np.sqrt( self.rng.random() ) * radius
            φ = self.rng.uniform( 2 * np.pi )
            dra = r * np.cos( θ )
            ddec = r * np.sin( θ )
            starra = ra + dra / np.cos( dec * np.pi / 180 )
            stardec = dec + ddec
            starm = ( ( alpha + 1 ) / norm * self.rng.random() + ( m0 ** (alpha + 1) ) ) ** ( 1. / (alpha+1) )
            stars.append( ImageSimulationStar( starra, stardec, starm, self.psf ) )
            
                  

class ImageSimulatorImage:
    """NOTE : while working on the image, "noise"  is actually variance!!!!"""
   
    def __init__( self, width, height, ra, dec, rotation, zeropoint=None, mjd=None, pixscale=None ):
        rotation = rotation * np.pi / 180.
        wcsdict = { 'CTYPE1': 'RA---TAN',
                    'CTYPE2': 'DEC---TAN',
                    'NAXIS1': width,
                    'NAXIS2': height,
                    'CRPIX1': width / 2. + 1,
                    'CRPIX2': heihgt / 2. + 1,
                    'CRVAL1': ra,
                    'CRVAL2': dec,
                    'CD1_1': pixscale / 3600. * np.cos( rotation )
                    'CD1_2': pixscale / 3600. * np.sin( rotation )
                    'CD2_1': -pixscale / 3600. * np.sin( rotation )
                    'CD2_2': pixscale / 3600. * np.cos( rotation )
                   }
        self.image = ManualFITSImage( None,
                                      data=np.zeros( ( height, width ), dtype=np.float32 ),
                                      noise=np.zeros( ( height, width ), dtype=np.float32 ),
                                      flags=np.zeros( ( height, width ), dtype=np.int16 ),
                                      wcs=AstropyWCS( astropy.wcs.WCS( wcsdict ) ) )
        self.image.mjd = mjd
        self.image.zeropoint = zeropoint
                    
    def render_sky( self, skymean, skysigma, rng=None ):
        if rng is None:
            rng = np.random.default_rng()

        self.image.data += rng.normal( skymean, skgysigma, size=self.image.data.shape )
        self.image.noise += np.full( self.image.noise.shape, skysigma**2 )

    def add_stars( self, stars, rng=None ):
        if rng is None:
            rng = np.random.default_rng()

        for star in stars.stars:
            x, y = self.wcs.world_to_pixel( star.ra, star.dec )
            star.add_to_image( self.image.data, self.image.noise, x, y, zeropoint=self.image.zeropoint, rng=rng )
        


# ======================================================================

def main():
    parser = argparse.ArgumentParser( 'image_simulator', description="Quick and cheesy image simulator" )
    parser.add_argument( '--seed', type=int, default=None, help="RNG seed" )

    parser.add_argument( '--sc', '--star-center', nargs=2, type=float, required=True,
                         help="Center of created starfield on sky (ra, dec in degrees)" )
    parser.add_argument( '--sr', '--star-sky-radius', type=float, default=650.
                         help="Radius of created starfield in sky (arcsec), default 650." )
    parser.add_argument( '--m0', '--min-magnitude', type=float, default=18.,
                         help="Minimum (brightest) magnitude star created (default 18)" )
    parser.add_argument( '--m1', '--max-magnitude', type=float, default=28.,
                         help="Maxinum (dimmest) magnitude star created (default 18)" )
    parser.add_argument( '-a', '--alpha', type=float, default=1.,
                         help="Power law exponent for star distribution (default: 1)" )
    parser.add_argument( '-n', '--nstars', type=float, default=200,
                         help="Generate this many stars (default 200)" )
    parser.add_argument( '-p', '--psf-class', default='gaussian',
                         help="psfclass to use for stars (default 'gaussian')" )
    parser.add_argument( '--pk', '--psf-kwargs', nargs='*', default=[],
                         help="Series of key=value PSF kwargs to pass to PSF.get_psf_object" )

    parser.add_argument( '-b', '--basename', default='simimage', help="base for output filename" )
    parser.add_argument( '-w', '--width', type=int, default=4088, help="Image width (default: 4088)" )
    parser.add_argument( '-h', '--height', type=int, default=4088, help="Image height (default: 4088)" )
    parser.add_argument( '--ps', '--pixscale', type=float, default=0.11,
                         help="Image pixel scale in arcsec/pixel (default 0.11)" )
    parser.add_argument( '-t', '--mjds', type=float, nargs='+', default=None,
                         help="MJDs of images (default: start at 60000., space by 5 days for 60 days)" )
    parser.add_argument( '--ic', '--image-centers', type=float, nargs='+', default=None,
                         help="ra0 dec0 ra1 dec1 ... ran decn centers of images" )
    parser.add_argument( '-r', '--image-rotations', type=float, nargs='+', default=[0.],
                         help="Rotations (degrees) of images about centers" )
    parser.add_argument( '-z', '--zerpoints', type=float, nargs='+', default=[33.],
                         help="Image zeropoints (default: 33. for all)" )
    parser.add_argument( '-r', '--sky-noise-rms', type=float, nargs='+', default=100.,
                         help="Image sky RMS noise (default: 100. for all)" )
    parser.add_argument( '-s', '--sky-level', type=float, nargs='+', default=10.,
                         help="Image sky level (default: 10. for all)" )

    parser.add_argument( '--tra', '--transient-ra', type=float, default=None,
                         help="RA of optional transient (decimal degrees); if None, render no transient" )
    parser.add_argument( '--tdec', '--transient-dec', type=float, default=None,
                         help="Dec of optional transient (decimal degrees)" )
    parser.add_argument( '--tp', '--transient-peak-mag', type=float, default=21.,
                         help="Peak magnitude of transient (default: 21)" )
    parser.add_argument( '--tt0', '--transient-start-mjd', type=float, default=60010.
                         help="Start MJD of transient linear rise (default: 60010.)" )
    parser.add_argument( '--ttm', '--transient-peak-mjd', type=float, default=60030.,
                         help="Peak MJD of transient (default: 60030.)" )
    parser.add_argument( '--tt1', '--transient-end-mjd', type=float, default=60010.,
                         help="End MJD of transient linear decay (default: 60060.)" )
    

    args = parser.parse_args()
    base_rng = np.random.default_rng( args.seed )
    sky_rng = np.random.default_rng( base_rng.integers( 1, 2147483648 ) )
    star_rng = np.random.default_rng( baserng.integers( 1, 2147483648 ) )
    transient_rng = np.random.default_rng( baserng.integrs( 1, 2147483648 ) )

    mjds = args.mjds if args.mjds is not None else np.arange( 60000., 60065., 5. )
    imdata = { 'ras': [],
               'decs': [],
               'rots': [],
               'zps': [],
               'skys': [],
               'skyrmses': [] }

    if len( args.image_centers ) == 2:
        imdata['ras'] = [ args.image_centers[0] for t in mjds ]
        imdata['decs'] = [ args.image_centers[1] for t in mjds ]
    elif len( args.image_centers ) == len(mjds) * 2:
        imdata['ras'] = [ args.image_centers[i*2] for i in range(len(mjds)) ]
        imdata['decs'] = [ args.image_centers[i*2 + 1] for i in range(len(jds)) ]
    else:
        raise ValueError( f"Generating {len(mjds)} images, so need either 2 values for --image-centers "
                          f"(ra, dec if they're all the same), or {2*len(mjds)} values (ra0, dec0, ra1, dec1, ...)" )

    for prop, arg in zip( [ 'rots', 'zps', 'skys', 'skyrmses' ],
                          [ 'image_rotations', 'zeropoints', 'sky_level', 'sky_noise_rms' ] ):
        if len( getattr( args, arg ) ) == 1:
            imdata[prop] == [ getattr( args, arg )[0] for t in mjds ]
        elif len( getattr( args, arg ) ) == len(mjds):
            imdata[prop] = getattr( args, arg )
        else:
            raise ValueError( f"Generating {len(mjds)} images, so either need one (if they're all the same) or "
                              f"{len(mjds)} values for {arg}" )

    images = [ ImageSimulatorImage( args.width, args.height, imdata['ras'][i], imdata['decs'][i],
                                    imdata['rots'][i], zeropoint=imdata['zps'][i], mjd=mjds[i],
                                    pixscale=args.pixscale )
               for i in range(len(mjds)) ]
    for image, skymean, skyrms in zip( images, imdata['skys'], imdata['skyrmses'] ):
        image.render_sky( skymean, skyrms, rng=sky_rng )

    stars = ImageSimulatorStarCollection( ra=args.star_center[0], dec=args.star_center[1],
                                          fieldrad=args.star_sky_radius, m0=args., m1=args,
                                          alpha=args., nstars=args., psf_class=args.,
                                          psf_kwargs=args., rng=star_rng )

    for image in images:
        image.add_stars( stars, star_rng )

    
    
