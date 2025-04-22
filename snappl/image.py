import types

from astropy.io import fits

from snappl.logger import Lager

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
        self.inputs = SimpleNamespace()
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

class OpenUniverse2024Image( Image ):
    def __init__( self, *args, **kwargs ):
        super().__init__( *args, **kwargs )

        self._data = None
        self._noise = None
        self._flags = None
        self._wcs = None
        
    @property
    def data( self ):
        if self._data is None:
            self._load_data()
        return self._data

    def _load_data( self ):
        """Loads the data from disk."""
        raise NotImplementedError( "Do." )
    
    def get_data( self, which='all' ):
        if which not in Image.data_array_list:
            raise ValueError( f"Unknown which {which}, must be all, data, noise, or flags" )
        Lager.info( f"Reading FITS file {self.path}" )
        with fits.open( self.path ) as hdul:
            self._wcs = AstropyWCS.from_header( hdul[1].header )
            if which == 'all':
                return [ hdul[1].data, hdul[2].data, hdu[3].data ]
            elif which == 'data':
                return [ hdu[1].data ]
            elif which == 'noise':
                return [ hdu[2].data ]
            elif which == 'flags':
                return [ hdu[3].data ]
            else:
                raise RuntimeError( f"{self.__class__.__name__} doesn't understand data plane {which}" )

    def get_wcs( self ):
        if self._wcs is None:
            with fits.open( self.path ) as hdul:
                self._wcs = AstropyWCS.from_header( hdul[1].header )
        return self._wcs
