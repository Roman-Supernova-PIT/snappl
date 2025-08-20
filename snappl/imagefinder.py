__all__ = [ 'ImageFinder', 'ImageFinderOU2024' ]

from snappl.image import OpenUniverse2024FITSImage
from snpit_utils.http import retry_post



class ImageFinder:
    """A class that finds images.  Use find_images."""

    @classmethod
    def find_images( cls, collection=None, subset=None, **kwargs ):
        """Find images.

        Paramaters
        ----------
          collection : str
             The collection to search.  Currently only "ou2024"
             is implemented, but others will be later.

          subset : str
            Subset of collection to search.  Many collections (including
            ou2024) will ignore this.

          path : pathlib.Path or str, default None
            Relative path of the image to search for.

          mjd_min : float, default None
            Only return images at this mjd or later

          mjd_max : float, default None
            Only return images at this mjd or earlier.

          ra: float, default None
            Only return images that contain this ra

          dec: float, default None
            Only return images that containe this dec

          filter: str, default None
            Only include images from this filter

          exptime_min: float, default None
            Only include images with at least this exptime.

          exptime_max: float, default None
            Only include images with at most this exptime.

          sca: int
            Only include images from this sca.

        Returns
        -------
          List of Image

         """

        if collection == 'ou2024':
            return ImageFinderOU2024._find_images( subset=subset, **kwargs )
        else:
            raise ValueError( f"Unknown collection {collection}" )

    @classmethod
    def _find_images( cls, collection=None, subset=None, **kwargs ):
        raise NotImplementedError( f"{cls.__name__} needs to imlement _find_images" )


class ImageFinderOU2024:

    @classmethod
    def _find_images( cls,
                      subset=None,
                      path=None,
                      mjd_min=None,
                      mjd_max=None,
                      ra=None,
                      dec=None,
                      filter=None,
                      exptime_min=None,
                      exptime_max=None,
                      sca=None ):
        params = {}

        if ( ra is None ) != ( dec is None ):
            raise ValueError( "Specify either both or neither of ra and dec" )

        if ra is not None:
            params['containing'] = ( float(ra), float(dec) )

        if mjd_min is not None:
            params['mjd_min'] = float(mjd_min)
        if mjd_max is not None:
            params['mjd_max'] = float(mjd_max)
        if filter is not None:
            params['filter'] = str(filter)
        if exptime_min is not None:
            params['exptime_min'] = float(exptime_min)
        if exptime_max is not None:
            params['exptime_max'] = float(exptime_max)

        res = retry_post( "https://roman-desc-simdex.lbl.gov/findromanimages", json=params )

        images = []
        for i in range( len(res['pointing']) ):
            path = OpenUniverse2024FITSImage.ou2024_image_filepath( res['pointing'][i],
                                                                    res['filter'][i],
                                                                    res['sca'][i] )
            images.append( OpenUniverse2024FITSImage( path, None, res['sca'][i] ) )

        return images
