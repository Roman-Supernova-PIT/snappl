import astropy.wcs


class BaseWCS:
    def __init__( self ):
        pass

    def pixel_to_world( self, *args, **kwargs ):
        """TODO DOCUMENT THIS"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement pixel_to_world" )

    def world_to_pixel( self, *args, **kwargs ):
        """TODO DOCUMENT THIS"""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement world_to_pixel" )


class AstropyWCS(BaseWCS):
    def __init__( self, apwcs=None ):
        self._wcs = apwcs

    @classmethod
    def from_header( cls, header ):
        wcs = AstropyWCS()
        wcs._wcs = astropy.wcs.WCS( header )
        return wcs

    def pixel_to_world( self, *args, **kwargs ):
        return self._wcs.pixel_to_world( *args, **kwargs )

    def world_to_pixel( self, *args, **kwargs ):
        return self._wcs.world_to_pixel( *args, **kwargs )

    ## More?


class TotalDisasterASDFWCS(BaseWCS):
    pass
