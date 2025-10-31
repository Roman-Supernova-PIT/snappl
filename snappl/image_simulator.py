__all__ = [ 'ImageSimulatorPointSource', 'ImageSimulationStar', 'ImageSimulatorStarCollection',
            'ImageSimulatorTransient', 'ImageSimulatorStaticSource', 'ImageSimulatorImage', 'ImageSimulator' ]

import re
import argparse
import functools
import multiprocessing

import numpy as np
import astropy.wcs

from snappl.logger import SNLogger
from snappl.utils import isSequence
from snappl.psf import PSF
from snappl.image import FITSImageStdHeaders
from snappl.wcs import AstropyWCS


class ImageSimulatorPointSource:
    def __init__( self, ra=None, dec=None, psf=None ):
        if any( i is None for i in [ ra, dec, psf ] ):
            raise ValueError( "ImageSimulatorPointSource (or subclass) requires all of [ ra, dec, psf ]" )
        self.ra = ra
        self.dec = dec
        self.psf = psf


    def render_stamp( self, width, height, x, y, flux, zeropoint=None, gain=1., noisy=True, rng=None ):

        if ( ( x < -self.psf.stamp_size ) or ( x > height + self.psf.stamp_size ) or
             ( y < -self.psf.stamp_size ) or ( y > width + self.psf.stamp_size )
            ):
            # No part of the stamp will be on the image, so don't bother rendering
            return None, None, None, None

        x0 = int( np.floor( x + 0.5 ) )
        y0 = int( np.floor( y + 0.5 ) )
        stamp = self.psf.get_stamp( x, y, x0=x0, y0=y0, flux=flux )
        var = np.zeros( stamp.shape )
        if noisy:
            if rng is None:
                rng = np.random.default_rng()
            w = stamp > 0
            var[ w ] = stamp[ w ] / gain
            stamp[ w ] += rng.normal( 0., np.sqrt( var[w] ) )

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
        if ix1 > width:
            sx1 -= ( ix1 - width )
            ix1 = width
        if iy1 > height:
            sy1 -= ( iy1 - height )
            iy1 = height

        if ( all( ( i >= 0 ) and ( i <= stamp.shape[0] ) for i in [ sy0, sy1 ] ) and
             all( ( i >= 0 ) and ( i <= stamp.shape[1] ) for i in [ sx0, sx1 ] )
            ):
            return stamp, var, ( ix0, ix1, iy0, iy1 ), ( sx0, sx1, sy0, sy1 )

        return None, None, None, None



class ImageSimulationStar( ImageSimulatorPointSource ):
    def __init__( self, mag=None, **kwargs ):
        super().__init__( **kwargs )
        self.mag = mag


    def render_star( self, width, height, x, y, zeropoint=None, gain=1., noisy=True, rng=None ):
        flux = 10 ** ( ( self.mag - zeropoint ) / -2.5 )
        return self.render_stamp( width, height, x, y, flux, zeropoint=zeropoint, gain=gain,
                                  noisy=noisy, rng=rng )


    def add_to_image( self, image, varimage, x, y, zeropoint=None, gain=1., noisy=True, rng=None ):
        stamp, var, imcoords, stampcoords =  self.render_star( image.shape[1], image.shape[0], x, y,
                                                               zeropoint=zeropoint, gain=gain, noisy=noisy, rng=rng )
        if stamp is not None:
            ix0, ix1, iy0, iy1 = imcoords
            sx0, sx1, sy0, sy1 = stampcoords
            image[ iy0:iy1, ix0:ix1 ] += stamp[ sy0:sy1, sx0:sx1 ]
            if varimage is not None:
                varimage[ iy0:iy1, ix0:ix1 ] += var[ sy0:sy1, sx0:sx1 ]


class ImageSimulatorStarCollection:
    def __init__( self, psf, ra=None, dec=None, fieldrad=None, m0=None, m1=None, alpha=None, nstars=None, rng=None ):
        if rng is None:
            self.rng = np.random.default_rng()
        self.psf = psf

        stars = []
        norm = ( alpha + 1 ) / ( m1 ** (alpha + 1) - m0 ** (alpha + 1) )
        for i in range(nstars):
            r = np.sqrt( rng.random() ) * fieldrad / 3600.
            φ = rng.uniform( 0., 2 * np.pi )
            dra = r * np.cos( φ )
            ddec = r * np.sin( φ )
            starra = ra + dra / np.cos( dec * np.pi / 180 )
            stardec = dec + ddec
            starm = ( ( alpha + 1 ) / norm * rng.random() + ( m0 ** (alpha + 1) ) ) ** ( 1. / (alpha+1) )
            stars.append( ImageSimulationStar( ra=starra, dec=stardec, mag=starm, psf=self.psf ) )

        self.stars = stars


class ImageSimulatorTransient( ImageSimulatorPointSource ):
    def __init__( self, peak_mag=None, peak_mjd=None, start_mjd=None, end_mjd=None, **kwargs ):
        super().__init__( **kwargs )
        if any( i is None for i in ( peak_mag, peak_mjd, start_mjd, end_mjd ) ):
            raise ValueError( "ImageSimulatorTransient requires all of [ peak_mag, peak_mjd, start_mjd, end_mjd ]" )
        self.peak_mag = peak_mag
        self.peak_mjd = peak_mjd
        self.start_mjd = start_mjd
        self.end_mjd = end_mjd


    def render_transient( self, width, height, x, y, mjd, zeropoint=None, gain=1., noisy=True, rng=None ):
        if ( mjd <= self.start_mjd ) or ( mjd >= self.end_mjd ):
            return None, None, None, None

        peakflux = 10 ** ( ( self.peak_mag - zeropoint ) / -2.5 )
        if mjd < self.peak_mjd:
            flux = peakflux * ( mjd - self.start_mjd ) / ( self.peak_mjd - self.start_mjd )
        else:
            flux = peakflux * ( mjd - self.end_mjd ) / ( self.peak_mjd - self.end_mjd )

        mag = -2.5 * np.log10( flux ) + zeropoint
        SNLogger.debug( f"Adding transient with mag {mag:.2f} (flux {flux:.0f}) at mjd {mjd}" )

        return self.render_stamp( width, height, x, y, flux, zeropoint=zeropoint, gain=gain,
                                  noisy=noisy, rng=rng )


class ImageSimulatorStaticSource(ImageSimulatorPointSource):
    """ A class for static sources (galaxies) that don't vary with time."""
    def __init__(self, mag, **kwargs):
        super().__init__(**kwargs)
        if mag is None:
            raise ValueError("ImageSimulatorStaticSource requires a magnitude")
        self.mag = mag

    def render_static_source(self, width, height, x, y, mjd, zeropoint=None, gain=1., noisy=True, rng=None):

        flux = 10 ** ((self.mag - zeropoint) / -2.5)
        SNLogger.debug(f"Adding transient with mag {self.mag:.2f} (flux {flux:.0f}) on mjd {mjd}")

        # To start, we are hardcoding that static sources are just point sources.
        return self.render_stamp(width, height, x, y, flux, zeropoint=zeropoint, gain=gain, noisy=noisy, rng=rng)


class ImageSimulatorImage:
    """NOTE : while working on the image, "noise"  is actually variance!!!!"""

    def __init__( self, width=4088, height=4088, ra=0., dec=0., rotation=0., basename='simulated_image',
                  zeropoint=33., mjd=60000., pixscale=0.11, band='R062', sca=1, exptime=60. ):

        if basename is None:
            raise ValueError( "Must pass a basename" )

        rotation = rotation * np.pi / 180.
        wcsdict = { 'CTYPE1': 'RA---TAN',
                    'CTYPE2': 'DEC--TAN',
                    'NAXIS1': width,
                    'NAXIS2': height,
                    'CRPIX1': width / 2. + 1,
                    'CRPIX2': height / 2. + 1,
                    'CRVAL1': ra,
                    'CRVAL2': dec,
                    'CD1_1': pixscale / 3600. * np.cos( rotation ),
                    'CD1_2': pixscale / 3600. * np.sin( rotation ),
                    'CD2_1': -pixscale / 3600. * np.sin( rotation ),
                    'CD2_2': pixscale / 3600. * np.cos( rotation )
                   }
        self.image = FITSImageStdHeaders( data=np.zeros( ( height, width ), dtype=np.float32 ),
                                          noise=np.zeros( ( height, width ), dtype=np.float32 ),
                                          flags=np.zeros( ( height, width ), dtype=np.int16 ),
                                          wcs=AstropyWCS( astropy.wcs.WCS( wcsdict ) ),
                                          path=f'{basename}_{mjd:7.1f}',
                                          std_imagenames=True )
        self.image.mjd = mjd
        self.image.zeropoint = zeropoint
        self.image.band = band
        self.image.sca = sca
        self.image.pointing = int( 100 * mjd )
        self.image.exptime = exptime

    def render_sky( self, skymean, skysigma, rng=None ):
        if rng is None:
            rng = np.random.default_rng()

        self.image.data += rng.normal( skymean, skysigma, size=self.image.data.shape )
        self.image.noise += np.full( self.image.noise.shape, skysigma**2 )

    def add_stars( self, stars, rng=None, noisy=False, numprocs=12 ):
        if rng is None:
            rng = np.random.default_rng()

        self._bad_things_have_happened = False

        def add_star_to_image( i, data ):
            stamp, var, imcoords, stampcoords = data
            # SNLogger.debug( f"...{'not ' if stamp is None else ''}adding star {i} to image" )
            if stamp is not None:
                ix0, ix1, iy0, iy1 = imcoords
                sx0, sx1, sy0, sy1 = stampcoords
                self.image.data[ iy0:iy1, ix0:ix1 ] += stamp[ sy0:sy1, sx0:sx1 ]
                self.image.noise[ iy0:iy1, ix0:ix1 ] += var[ sy0:sy1, sx0:sx1 ]

        def omg( x ):
            SNLogger.error( str(x) )
            self._bad_things_have_happened = True

        SNLogger.info( f"Adding stars in {numprocs} processes" )
        if numprocs == 1:
            for i, star in enumerate( stars.stars ):
                x, y = self.image.get_wcs().world_to_pixel( star.ra, star.dec )
                try:
                    data = star.render_star( self.image.data.shape[1], self.image.data.shape[0], x, y,
                                             zeropoint=self.image.zeropoint, rng=rng, noisy=noisy )
                    add_star_to_image( i, data )
                except Exception as ex:
                    omg( ex )
        else:
            with multiprocessing.Pool( numprocs ) as pool:
                for i, star in enumerate( stars.stars ):
                    x, y = self.image.get_wcs().world_to_pixel( star.ra, star.dec )
                    doer = functools.partial( star.render_star,
                                              self.image.data.shape[1], self.image.data.shape[0], x, y,
                                              zeropoint=self.image.zeropoint, rng=rng, noisy=noisy )
                    callback = functools.partial( add_star_to_image, i )
                    pool.apply_async( doer, callback=callback, error_callback=omg )
                pool.close()
                pool.join()

        if self._bad_things_have_happened:
            raise RuntimeError( "Bad things have happened." )


    def add_transient( self, transient, rng=None, noisy=False ):
        if rng is None:
            rng = np.random.default_rng()

        x, y = self.image.get_wcs().world_to_pixel( transient.ra, transient.dec )
        SNLogger.debug( f"...adding transient to image at ({x:.2f}, {y:.2f})..." )
        ( stamp, var,
          imcoords, stampcoords ) = transient.render_transient( self.image.data.shape[1], self.image.data.shape[0],
                                                                x, y, self.image.mjd, zeropoint=self.image.zeropoint,
                                                                rng=rng, noisy=noisy )
        if stamp is not None:
            ix0, ix1, iy0, iy1 = imcoords
            sx0, sx1, sy0, sy1 = stampcoords
            self.image.data[ iy0:iy1, ix0:ix1 ] += stamp[ sy0:sy1, sx0:sx1 ]
            self.image.noise[ iy0:iy1, ix0:ix1 ] += var[ sy0:sy1, sx0:sx1 ]

    def add_static_source( self, static_source, rng=None, noisy = False ):
        if static_source is not None:
            if rng is None:
                rng = np.random.default_rng()

            x, y = self.image.get_wcs().world_to_pixel( static_source.ra, static_source.dec )
            SNLogger.debug( f"...adding static source to image at ({x:.2f}, {y:.2f})..." )
            ( stamp, var,
            imcoords, stampcoords ) = static_source.render_static_source( self.image.data.shape[1],
                                                                            self.image.data.shape[0],
                                                                        x, y, self.image.mjd,
                                                                        zeropoint=self.image.zeropoint,
                                                                        rng=rng, noisy=noisy)
            if stamp is not None:
                ix0, ix1, iy0, iy1 = imcoords
                sx0, sx1, sy0, sy1 = stampcoords
                self.image.data[ iy0:iy1, ix0:ix1 ] += stamp[ sy0:sy1, sx0:sx1 ]
                self.image.noise[ iy0:iy1, ix0:ix1 ] += var[ sy0:sy1, sx0:sx1 ]


class ImageSimulator:
    def __init__( self,
                  seed=None,
                  star_center=None,
                  star_sky_radius=320.,
                  min_star_magnitude=18.,
                  max_star_magnitude=28.,
                  alpha=1.,
                  nstars=200,
                  psf_class='gaussian',
                  psf_kwargs=[],
                  no_star_noise=False,
                  basename='simimage',
                  width=4088,
                  height=4088,
                  pixscale=0.11,
                  mjds=None,
                  image_centers=None,
                  image_rotations=[0.],
                  zeropoints=[33.],
                  sky_noise_rms=[10.],
                  sky_level=[10.],
                  band='R062',
                  sca=1,
                  exptime=60.,
                  transient_ra=None,
                  transient_dec=None,
                  transient_peak_mag=21.,
                  transient_peak_mjd=60030.,
                  transient_start_mjd=60010.,
                  transient_end_mjd=60060.,
                  no_transient_noise=False,
                  overwrite=False,
                  static_source_ra=None,
                  static_source_dec=None,
                  static_source_mag=None,
                  no_static_source_noise=False,
                  numprocs=12 ):

        self.mjds = mjds if mjds is not None else np.arange( 60000., 60065., 5. )

        if star_center is None:
            raise ValueError( "star_center and star_center is required" )
        if ( not isSequence(star_center) ) or ( len(star_center) != 2 ):
            raise ValueError( "star_center must have 2 values" )
        star_center_ra, star_center_dec = star_center

        self.imdata = { 'mjds': mjds,
                        'ras': [],
                        'decs': [],
                        'rots': [],
                        'zps': [],
                        'skys': [],
                        'skyrmses': [] }

        if image_centers is None:
            self.imdata['ras'] = [ star_center_ra for t in mjds ]
            self.imdata['decs'] = [ star_center_dec for t in mjds ]
        elif len( image_centers ) == 2:
            self.imdata['ras'] = [ image_centers[0] for t in mjds ]
            self.imdata['decs'] = [ image_centers[1] for t in mjds ]
        elif len(image_centers ) == len(mjds) * 2:
            self.imdata['ras'] = [ image_centers[i*2] for i in range(len(mjds)) ]
            self.imdata['decs'] = [ image_centers[i*2 + 1] for i in range(len(mjds)) ]
        else:
            raise ValueError( f"Generating {len(mjds)} images, so need either 2 values for image_centers "
                              f"(ra, dec if they're all the same), or {2*len(mjds)} values "
                              f"(ra0, dec0, ra1, dec1, ...)" )

        for prop, arg in zip( [ 'rots', 'zps', 'skys', 'skyrmses' ],
                              [ 'image_rotations', 'zeropoints', 'sky_level', 'sky_noise_rms' ] ):
            val = locals()[arg]
            if len( val ) == 1:
                self.imdata[prop] = [ val[0] for t in mjds ]
            elif len( val ) == len(mjds):
                self.imdata[prop] = val
            else:
                raise ValueError( f"Generating {len(mjds)} images, so either need one (if they're all the same) or "
                                  f"{len(mjds)} values for {arg}" )

        self.seed = seed
        self.width = width
        self.height = height
        self.basename = basename
        self.pixscale = pixscale
        self.star_center_ra = star_center_ra
        self.star_center_dec = star_center_dec
        self.star_sky_radius = star_sky_radius
        self.min_star_magnitude = min_star_magnitude
        self.max_star_magnitude = max_star_magnitude
        self.alpha = alpha
        self.nstars = nstars
        self.psf_class = psf_class
        self.psf_kwargs = psf_kwargs
        self.no_star_noise = no_star_noise
        self.band = band
        self.sca = sca
        self.exptime = exptime
        self.transient_ra = transient_ra
        self.transient_dec = transient_dec
        self.transient_peak_mag = transient_peak_mag
        self.transient_peak_mjd = transient_peak_mjd
        self.transient_start_mjd = transient_start_mjd
        self.transient_end_mjd = transient_end_mjd
        self.no_transient_noise = no_transient_noise
        self.static_source_ra = static_source_ra
        self.static_source_dec = static_source_dec
        self.static_source_mag = static_source_mag
        self.no_static_source_noise = no_static_source_noise

        self.overwrite = overwrite
        self.numprocs = numprocs

    def __call__( self ):
        base_rng = np.random.default_rng( self.seed )
        sky_rng = np.random.default_rng( base_rng.integers( 1, 2147483648 ) )
        star_rng = np.random.default_rng( base_rng.integers( 1, 2147483648 ) )
        transient_rng = np.random.default_rng( base_rng.integers( 1, 2147483648 ) )

        unpack = re.compile( r"^([a-zA-Z0-9_]+)\s*=\s*(.*[^\s])\s*$" )
        kwargs = {}
        for arg in self.psf_kwargs:
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
        psf = PSF.get_psf_object( self.psf_class, **kwargs )

        stars = ImageSimulatorStarCollection( psf=psf, ra=self.star_center_ra, dec=self.star_center_dec,
                                              fieldrad=self.star_sky_radius,
                                              m0=self.min_star_magnitude, m1=self.max_star_magnitude,
                                              alpha=self.alpha, nstars=self.nstars, rng=star_rng )

        transient = ImageSimulatorTransient( ra=self.transient_ra, dec=self.transient_dec,
                                             psf=psf, peak_mag=self.transient_peak_mag,
                                             peak_mjd=self.transient_peak_mjd, start_mjd=self.transient_start_mjd,
                                             end_mjd=self.transient_end_mjd )
        if all ( i is not None for i in [ self.static_source_ra, self.static_source_dec, self.static_source_mag ] ):
            static_source = ImageSimulatorStaticSource( ra=self.static_source_ra, dec=self.static_source_dec,
                                                    psf=psf, mag=self.static_source_mag )
        else:
            static_source = None

        for i in range( len( self.imdata['mjds'] ) ):
            SNLogger.debug( f"Simulating image {i} of {len(self.imdata['mjds'])}" )
            image =  ImageSimulatorImage( self.width, self.height,
                                          ra=self.imdata['ras'][i], dec=self.imdata['decs'][i],
                                          rotation=self.imdata['rots'][i], basename=self.basename,
                                          zeropoint=self.imdata['zps'][i], mjd=self.imdata['mjds'][i],
                                          pixscale=self.pixscale, band=self.band, sca=self.sca, exptime=self.exptime )
            image.render_sky( self.imdata['skys'][i], self.imdata['skyrmses'][i], rng=sky_rng )
            image.add_stars( stars, star_rng, numprocs=self.numprocs, noisy=not self.no_star_noise )
            image.add_transient( transient, rng=transient_rng, noisy=not self.no_transient_noise )
            image.add_static_source(static_source, rng=transient_rng, noisy=not self.no_static_source_noise)
            image.image.noise = np.sqrt( image.image.noise )
            SNLogger.info( f"Writing {image.image.path}, {image.image.noisepath}, and {image.image.flagspath}" )
            image.image.save( overwrite=self.overwrite )



# ======================================================================

def main():
    parser = argparse.ArgumentParser( 'image_simulator', description="Quick and cheesy image simulator" )
    parser.add_argument( '--seed', type=int, default=None, help="RNG seed" )

    parser.add_argument( '--star-center', '--sc', nargs=2, type=float, required=True,
                         help="Center of created starfield on sky (ra, dec in degrees)" )
    parser.add_argument( '--star-sky-radius', '--sr', type=float, default=650.,
                         help="Radius of created starfield in sky (arcsec), default 650." )
    parser.add_argument( '--min-star-magnitude', '--m0', type=float, default=18.,
                         help="Minimum (brightest) magnitude star created (default 18)" )
    parser.add_argument( '--max-star-magnitude', '--m1', type=float, default=28.,
                         help="Maxinum (dimmest) magnitude star created (default 18)" )
    parser.add_argument( '-a', '--alpha', type=float, default=1.,
                         help="Power law exponent for star distribution (default: 1)" )
    parser.add_argument( '-n', '--nstars', type=int, default=200,
                         help="Generate this many stars (default 200)" )
    parser.add_argument( '-p', '--psf-class', default='gaussian',
                         help="psfclass to use for stars (default 'gaussian')" )
    parser.add_argument( '--psf-kwargs', '--pk', nargs='*', default=[],
                         help="Series of key=value PSF kwargs to pass to PSF.get_psf_object" )
    parser.add_argument( '--no-star-noise', action='store_true', default=False,
                         help="Set this to not add poisson noise to stars." )

    parser.add_argument( '-b', '--basename', default='simimage',
                         help=( "base for output filename.  Written files will be basename_{mjd:7.1f}_image.fits, "
                                "..._noise.fits, and ..._flags.fits" ) )
    parser.add_argument( '--width', type=int, default=4088, help="Image width (default: 4088)" )
    parser.add_argument( '--height', type=int, default=4088, help="Image height (default: 4088)" )
    parser.add_argument( '--pixscale', '--ps', type=float, default=0.11,
                         help="Image pixel scale in arcsec/pixel (default 0.11)" )
    parser.add_argument( '-t', '--mjds', type=float, nargs='+', default=None,
                         help="MJDs of images (default: start at 60000., space by 5 days for 60 days)" )
    parser.add_argument( '--image-centers', '--ic', type=float, nargs='+', default=None,
                         help="ra0 dec0 ra1 dec1 ... ran decn centers of images" )
    parser.add_argument( '-θ', '--image-rotations', type=float, nargs='+', default=[0.],
                         help="Rotations (degrees) of images about centers" )
    parser.add_argument( '-z', '--zeropoints', type=float, nargs='+', default=[33.],
                         help="Image zeropoints (default: 33. for all)" )
    parser.add_argument( '-r', '--sky-noise-rms', type=float, nargs='+', default=100.,
                         help="Image sky RMS noise (default: 100. for all)" )
    parser.add_argument( '-s', '--sky-level', type=float, nargs='+', default=10.,
                         help="Image sky level (default: 10. for all)" )
    parser.add_argument( '-f', '--band', '--filter', default="R062",
                         help="Stuck in the BAND Header in the images (default R062)." )
    parser.add_argument( '--sca', default=1,
                         help="Stuck in the SCA Header in the images (default 1)" )
    parser.add_argument( '--exptime', default=60.,
                         help="Stuck in the EXPTIME Header in the images (default 60)" )

    parser.add_argument( '--transient-ra', '--tra', type=float, default=None,
                         help="RA of optional transient (decimal degrees); if None, render no transient" )
    parser.add_argument( '--transient-dec', '--tdec', type=float, default=None,
                         help="Dec of optional transient (decimal degrees)" )
    parser.add_argument( '--transient-peak-mag', '--tp', type=float, default=21.,
                         help="Peak magnitude of transient (default: 21)" )
    parser.add_argument( '--transient-start-mjd', '--tt0', type=float, default=60010.,
                         help="Start MJD of transient linear rise (default: 60010.)" )
    parser.add_argument( '--transient-peak-mjd', '--ttm', type=float, default=60030.,
                         help="Peak MJD of transient (default: 60030.)" )
    parser.add_argument( '--transient-end-mjd', '--tt1', type=float, default=60060.,
                         help="End MJD of transient linear decay (default: 60060.)" )
    parser.add_argument( '--no-transient-noise', action='store_true', default=False,
                         help="Set this to not add poisson noise to transients." )

    parser.add_argument( '--static-source-ra', type=float, default=None,
                         help="RA of optional static source (decimal degrees); if None, render no static source" )
    parser.add_argument( '--static-source-dec', type=float, default=None,
                         help="Dec of optional static source (decimal degrees)" )
    parser.add_argument( '--static-source-mag', type=float, default=22.,
                         help="Magnitude of static source (default: 22)" )
    parser.add_argument( '--no-static-source-noise', action='store_true', default=False,
                         help="Set this to not add poisson noise to static sources." )

    parser.add_argument( '--numprocs', type=int, default=12, help="Number of star rendering processes (default 12)" )
    parser.add_argument( '-o', '--overwrite', action='store_true', default=False,
                         help="Overwrite any existing images with the same filename." )


    args = parser.parse_args()
    sim = ImageSimulator( **vars(args) )
    sim()


# ======================================================================
if __name__ == "__main__":
    main()
