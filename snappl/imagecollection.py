__all__ = [ 'ImageCollection', 'ImageCollectionOU2024', 'ImageCollectionManualFITS' ]

import pathlib

from snpit_utils.config import Config


class ImageCollection:
    """A class that keeps track of groups of images.

    Never instantiate an object of this class of its subclasses
    directly.  Call the get() class method go get your image collection.

    Available properties include:

    base_path : pathlib.Path ; image paths are relative to this absolute path.

    """

    @classmethod
    def get_collection( cls, collection, subset=None, **kwargs ):
        """Get an ImageCollection object.

        Parameters
        ----------
          collection : str
            Name of the collection

          subset : str or None
            Name of the subset, if relevant for that collection.

          **kwargs : Some collections types require additional arguments.

        """
        if collection == 'ou2024':
            return ImageCollectionOU2024( **kwargs )
        elif collection == 'manual_fits':
            return ImageCollectionManualFITS( **kwargs )
        else:
            raise ValueError( f"Unknown image collection {collection} (subset {subset})" )

    def get_image_path( self, pointing, band, sca, rootdir=None ):
        """Return the absolute path to the desired image, if that makes sense.

        This will only make sense for image collections where an image
        is uniquely defined by a pointing, band, and sca.  Other image
        collections will just not implement this method.

        Parameters
        ----------
          pointing : str (int?)
            The pointing number

          band : str
            The band

          sca : str (int?)
            The SCA

          rootdir : str or Path, default None
            If None, use the default value for this collection

        Returns
        -------
          pathlib.Path

        """
        raise NotImplementedError( f"{self.__class__.__name__} doesn't implement get_image_path" )


class ImageCollectionOU2024:
    """Collection of OpenUnivers 2024 FITS images."""
    def __init__( self, base_path=None ):
        self._base_path = None if base_path is None else pathlib.Path( base_path )

    @property
    def base_path( self ):
        if self._base_path is None:
            self._base_path = Config.get().value( 'ou24.images' )
        return self._base_path

    @classmethod
    def get_image_path( cls, pointing, band, sca, rootdir=None ):
        """Return the absolute path to the desired OU2024 FITS image.

        See ImageCollection.get_image_path for documentation.

        """
        rootdir = pathlib.Path( Config.get().value( 'ou24.tds_base' ) if rootdir is None else rootdir )
        path = ( rootdir / 'images/simple_model' / band / str(pointing) /
                 f'Roman_TDS_simple_model_{band}_{str(pointing)}_{str(sca)}.fits.gz' )
        return path


class ImageCollectionManualFITS:
    """Manually specified custom images."""

    def __init__( self, base_path=None ):
        if base_path is None:
            raise RuntimeError( "manual_fits collection needs a base path" )
        self.base_path = pathlib.Path( base_path )
