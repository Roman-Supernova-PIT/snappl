import types

from astropy.io import fits
from astropy.nddata.utils import Cutout2D

from snappl.logger import Lager

from astropy.wcs import WCS as AstropyWCS
from astropy.coordinates import SkyCoord
from astropy import units as u

import numpy as np


class Exposure:
    pass

class OpenUniverse2024Exposure:
    def __init__( self, pointing ):
        self.pointing = pointing

class Image:
    """Cole did this (with software):
                    ___
                   / _ \___  __ _  ___ ____
                  / , _/ _ \/  ' \/ _ `/ _ \
                 /_/|_|\___/_/_/_/\_,_/_//_/
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣔⣴⣦⣔⣠⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣿⣭⣿⣟⣿⣿⣿⣅⢀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣾⣷⣾⣿⣿⣿⣿⣿⣿⣿⡶⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣄⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡇⠄⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣠⠤⢤⣄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⡠⢒⣿⣿⣿⣠⠋⠀⠀⠀⠀⠀⠀⣀⣀⠤⠶⠿⠿⠛⠿⠿⠿⢻⢿⣿⣿⣿⠿⠟⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⡞⢀⣿⣿⣿⡟⠃⠀⠀⠀⣀⡰⠶⠛⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠀⠃⠘⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠘⢧⣤⣈⣡⣤⠤⠴⠒⠊⠉⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀


                 _____  __     ___  __________
                / __/ |/ /    / _ \/  _/_  __/
               _\ \/    /    / ___// /  / /
              /___/_/|_/    /_/  /___/ /_/

       """

    data_array_list = [ 'all', 'data', 'noise', 'flags' ]

    def __init__( self, path, exposure, sca ):
        """type things here

        Parameters
        ----------
          path : str
            Path to image file, or otherwise some kind of indentifier
            that allows the class to find the image.

          exposure : Exposure (or instance of Exposure subclass)
            The exposure this image is associated with

          sca : int
            The Sensor Chip Assembly that would be called the
            chip number for any other telescope but is called SCA for
            Roman.

        """
        self.inputs = types.SimpleNamespace()
        self.inputs.path = path
        self.inputs.exposure = exposure
        self.inputs.sca = sca

    @property
    def data( self ):
        """The image data, a 2d numpy array."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement data" )

    @property
    def noise( self ):
        """The 1σ pixel noise, a 2d numpy array."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement noise" )

    @property
    def flags( self ):
        """An integer 2d numpy array of pixel masks / flags TBD"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement flags" )

    @property
    def sky_level( self ):
        """Estimate of the sky level in ADU."""
        raise NotImplementedError( "Do.")

    @property
    def exptime( self ):
        """Exposure time in seconds."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement exptime" )

    @property
    def band( self ):
        """Band (str)"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement band" )

    @property
    def mjd( self ):
        """MJD of the start of the image (defined how? TAI?)"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement mjd" )

    @property
    def position_angle( self ):
        """Position angle in degrees east of north (or what)?"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement position_angle" )

    @property
    def image_shape( self ):
        """ny, nx pixel size of the image"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement image_shape" )


    def fraction_masked( self ):
        """Fraction of pixels that are masked."""
        raise NotImplementedError( "Do.")

    def get_data( self, which='all' ):
        """Read the data from disk and return one or more 2d numpy arrays of data.

        Parameters
        ----------
          which : str
            What to read:
              all : data, noise, and flags
              data :
              noise :
               flags :

        The data read not stored in the class, so when the caller goes
        out of scope, the data will be freed (unless the caller saved it
        somewhere.  This does mean it's read from disk every time.

        Returns
        -------
          list (length 1 or 3 ) of 2d numpy arrays

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_data" )


    def get_wcs( self ):
        """Get an abstract WCS thingy

        Returns
        -------
          snappl.wcs.WCS

        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_wcs" )


    def get_cutout(self, ra, dec, size):
        """Make a cutout of the image at the given RA and DEC.

        Returns
        -------
          snappl.image.Image
        """
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_cutout" )


    @property
    def coord_center(self):
        '''
        Get the RA and DEC at the center of the image.
        Note: By fetching the center from the WCS and not the header,
              this means that this works for cutouts too.

        Returns:
        coord_center: array of floats, shape (2,) [RA, DEC] in degrees.
        '''
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement coord_center" )

    def get_image_shape(self):
        """Get the shape of the image."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_image_shape" )

    @property
    def band( self ):
        """Band (str)"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement band" )




    #     # THE REST OF THIS MAY GO AWAY

    #     self.pipeline = pipeline
    #     self.logger = self.pipeline.logger
    #     self.sims_dir = pathlib.Path( os.getenv( 'SIMS_DIR', None ) )
    #     if self.sims_dir is None:
    #         raise ValueError( "Env var SIMS_DIR must be set" )
    #     self.image_path = self.sims_dir / path
    #     self.image_name = self.image_path.name
    #     if self.image_name[-3:] == '.gz':
    #         self.image_name = self.image_name[:-3]
    #     if self.image_name[-5:] != '.fits':
    #         raise ValueError( f"Image name {self.image_name} doesn't end in .fits, I don't know how to cope." )
    #     self.basename = self.image_name[:-5]
    #     self.pointing = pointing
    #     self.sca = sca
    #     self.mjd = mjd
    #     self.psf_path = None
    #     self.detect_mask_path = None
    #     self.skyrms = None
    #     self.skysub_path = None

    #     self.decorr_psf_path = {}
    #     self.decorr_zptimg_path = {}
    #     self.decorr_diff_path = {}
    #     self.zpt_stamp_path = {}
    #     self.diff_stamp_path = {}

    # def run_sky_subtract( self ):
    #     try:
    #         self.logger.debug( f"Process {multiprocessing.current_process().pid} run_sky_subtract {self.image_name}" )
    #         self.skysub_path = self.pipeline.temp_dir / f"skysub_{self.image_name}"
    #         self.detmask_path = self.pipeline.temp_dir / f"detmask_{self.image_name}"
    #         self.skyrms = sky_subtract( self.image_path, self.skysub_path, self.detmask_path,
    #                                     temp_dir=self.pipeline.temp_dir, force=self.pipeline.force_sky_subtract )
    #         return ( self.skysub_path, self.detmask_path, self.skyrms )
    #     except Exception as ex:
    #         self.logger.error( f"Process {multiprocessing.current_process().pid} exception: {ex}" )
    #         raise

    # def save_sky_subtract_info( self, info ):
    #     self.logger.debug( f"Saving sky_subtract info for path {info[0]}" )
    #     self.skysub_path = info[0]
    #     self.detmask_path = info[1]
    #     self.skyrms = info[2]


    # def run_get_imsim_psf( self ):
    #     psf_path = self.pipeline.temp_dir / f"psf_{self.image_name}"
    #     get_imsim_psf( self.image_path, self.pipeline.ra, self.pipeline.dec, self.pipeline.band,
    #                    self.pointing, self.sca,
    #                    size=201, psf_path=psf_path, config_yaml_file=self.pipeline.galsim_config_file, include_photonOps=True )
    #     return psf_path

    # def save_psf_path( self, psf_path ):
    #     self.psf_path = psf_path


# ======================================================================
# OpenUniverse 2024 Images are gzipped FITS files
#  HDU 0 : (something, no data)
#  HDU 1 : SCI (32-bit float)
#  HDU 2 : ERR (32-bit float)
#  HDU 3 : DQ (32-bit integer)

class OpenUniverse2024FITSImage( Image ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

        self._data = None
        self._noise = None
        self._flags = None
        self._wcs = None
        self._is_cutout = False
        self._image_shape = None
        self._header = None

    @property
    def data( self ):
        if self._data is None:
            self._load_data()
        return self._data

    @data.setter
    def data(self, new_value):
        if isinstance(new_value, np.ndarray) and np.issubdtype(new_value.dtype, np.floating):
            self._data = new_value
        else:
            raise ValueError("Data must be a numpy array of floats.")

    def _load_data( self ):
        """Loads the data from disk."""
        raise NotImplementedError( "Do." )

    def get_data( self, which='all'):
        if self._is_cutout:
            raise RuntimeError( "get_data called on a cutout image, this will return the ORIGINAL UNCUT image. Currently not supported.")
        if which not in Image.data_array_list:
            raise ValueError( f"Unknown which {which}, must be all, data, noise, or flags" )
        Lager.info( f"Reading FITS file {self.inputs.path}" )

        with fits.open( self.inputs.path ) as hdul:
            self._wcs = AstropyWCS( hdul[1].header )

            if which == 'all':
                return [ hdul[1].data, hdul[2].data, hdul[3].data ]
            elif which == 'data':
                return [ hdul[1].data ]
            elif which == 'noise':
                return [ hdul[2].data ]
            elif which == 'flags':
                return [ hdul[3].data ]
            else:
                raise RuntimeError( f"{self.__class__.__name__} doesn't understand data plane {which}" )

    def get_wcs( self ):
        if self._wcs is None:
            with fits.open( self.inputs.path ) as hdul:
                self._wcs = AstropyWCS( hdul[1].header )
        return self._wcs

    def _get_header(self):
        """Get the header of the image."""
        if self._header is None:
            with fits.open(self.inputs.path) as hdul:
                self._header = hdul[1].header
        return self._header


    @property
    def image_shape(self):
        """Get the shape of the image."""
        if not self._is_cutout:
            self._header = self.get_header()
            self._image_shape = (self._header['NAXIS1'], self._header['NAXIS2'])
            return self._image_shape

        if self._image_shape is None:
            self._image_shape = self.data.shape

        return self._image_shape

    @property
    def coord_center(self):
        '''
        Get the RA and DEC at the center of the image.
        Works for cutouts too.
        Returns:
        coord_center: array of floats, shape (2,) [RA, DEC] in degrees.
        '''
        wcs = self.get_wcs()
        coord_center = wcs.wcs_pix2world(
            self.get_image_shape()[0] // 2,
            self.get_image_shape()[1] // 2,
            1)
        return coord_center

    @property
    def band(self):
        '''
        Return the band the image is taken in.

        Returns:
        band: str
        '''
        header = self.get_header()
        return header['FILTER'].strip()

    def get_cutout(self, x, y, xsize, ysize=None):
        '''
        Creates a new snappl image object that is a cutout of the original
        image, at a location in pixel-space.

        Parameters
        ----------
        x : int
            x pixel coordinate of the center of the cutout.
        y : int
            y pixel coordinate of the center of the cutout.
        xsize : int
            Width of the cutout in pixels.
        ysize : int
            Height of the cutout in pixels. If None, set to xsize.
        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.
        '''
        if ysize is None:
            ysize = xsize
        if xsize % 2 != 1 or ysize % 2 != 1:
            raise ValueError(f"Size must be odd for a well defined central \
                pixel, you tried to pass a size of {xsize, ysize}.")
        loc = (x, y)
        Lager.debug(f'Cutting out at {x , y}')
        data, noise, flags = self.get_data('all')
        astropy_cutout = Cutout2D(data, loc, size=(ysize, xsize), # Astropy asks for this order. Beats me. -Cole
                                   mode='strict', wcs=self.get_wcs())
        astropy_noise = Cutout2D(noise, loc, size=(ysize, xsize),
                                   mode='strict', wcs=self.get_wcs())

        snappl_cutout = self.__class__(self.inputs.path, self.inputs.exposure, self.inputs.sca)
        snappl_cutout._data = astropy_cutout.data
        snappl_cutout._wcs = astropy_cutout.wcs
        snappl_cutout._noise = astropy_noise.data
        snappl_cutout._is_cutout = True

        return snappl_cutout

    def get_ra_dec_cutout(self, ra, dec, xsize, ysize=None):
        '''
        Creates a new snappl image object that is a cutout of the original
        image, at a location in pixel-space.
        Parameters
        ----------
        ra : float
            RA coordinate of the center of the cutout, in degrees.
        dec : float
            DEC coordinate of the center of the cutout, in degrees.
        xsize : int
            Width of the cutout in pixels.
        ysize : int
            Height of the cutout in pixels. If None, set to xsize.

        Returns
        -------
        cutout : snappl.image.Image
            A new snappl image object that is a cutout of the original image.
        '''

        wcs = self.get_wcs()
        x, y = wcs.wcs_world2pix(ra, dec, 0)  # <--- I DO NOT UNDERSTAND WHY THIS
        # NEEDS TO BE ZERO, BUT THAT MADE THIS NEW FUNCTION AGREE WITH THE
        # OUTPUT OF THE OLD FUNCTION. COLE IS CONFUSED!!!!!
        return self.get_cutout(x, y, xsize, ysize)

