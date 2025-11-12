import pathlib

from snappl.config import Config


class PathedObject:
    """An object that might be stored in the database but that also has files on disk.

    Subclasses include Image, SegmentatonMap, Lightcurve, and Spectrum1d, and will include more in the future.

    Here so we can have a semi-unified interface.

    Standard properties of a PathedObject are:

      * filepath : pathlib.Path : path of the object *relative to* the base
                                  path for this kind of object.  This is what
                                  gets stored in the database (usually in a
                                  column named "filepath", though the user
                                  will not need to know that).

      * full_filepath : pathlib.Path : the absolute path to the file on disk.
                                       (But see "complications" below.)  This
                                       attribute is usually derived from
                                       base_path and filepath.

      * base_path : pathlib.Path : base path for this kind of object.
                                   Normally this is from the config, and is
                                   the base path for this kind of object.
                                   (For instance, for L2 images, base_path is
                                   the directory pointed to by config value
                                   "system.paths.images").  However, for
                                   backwards compatibility, we want to be able
                                   to support objects that aren't in the
                                   database, so you can set a custom
                                   base_path, if you need to, every time you
                                   create an object.

       * filename : string : the name part of filepath (so if filepath is
         Path("/foo/bar"), filename is "bar").

    Complications:

    This class is designed implicitly assuming that one row in the database
    corresponds to one PathedObject object, and to one file on disk.
    Sometimes that may not be true, e.g. an image might not have the image,
    noise, and flags arrays all packed into one file, but in three different
    files.  In that case, the subclass must know how to deal with this, and
    "filepath" may not be the path to an actual file, but to a path to the
    name of which you must append additional standard stuff to find the file.
    (The one extant example of this is the image.FITSImage class with
    std_imagenames set to True.)

    For subclass developers:

    Any subclass of this class must define one of two things.  Either, it must
    define a class variable _base_path_config_item that is thing to look up
    with Config.get().value(...) to figure out the default base path for
    objects of that class; or, it must define a function _set_base_path that
    sets both self._no_base_path and self._base_path.  (Practically speaking:
    they all define _base_path_config_item, except for Image, which has to do
    other gyrations for backwards compatibility.)

    """


    def __init__( self, filepath=None, base_path=None, base_dir=None, full_filepath=None, no_base_path=False ):
        """Set up object paths.

        Parameters
        ----------
          filepath : str or Path, default None
            Path of the file relative to base_path.  If no_base_path is True
            (which should *never* be the case for an object that is associated
            with the database), then this is the full path.

          base_path, base_dir : str or Path, default None
            Only use one of these; they set the same thing.  (Both parameters
            are defined for backwards compatibility.)  Most of the time you do
            *not* want to specify this, but leave it at the default.  If
            no_base_path is True, you *must* leave these at None.  This is the
            base path for objects of the subclass of PathedObject that is
            being constructed.  By default (which is usually what you want),
            it will use a path that is configured for the type of object that
            the subclass tracks.

          full_filepath : str or Path, default None
            Usually you don't want to specify this, but there are cases where
            you can.

          no_base_path : bool, default False
            You may want to set this to True if you are dealing with
            files that aren't tracked by the database.  In that case,
            you can't specify base_path (or base_dir), and filepath and
            full_filepath mean the same thing (and must be the same if
            for some reasdon you give both).

        """
        # The tortured filepath logic comes about from wanting to have paths
        # controlled when things are in the database, but also wanting to have
        # the ability to create objects that won't eventually be saved to the
        # database, and so want to have manually specified paths.  (Plus, some
        # additional fun from backwards compatibility.)

        if ( base_path is not None ) and ( base_dir is not None ) and ( base_path != base_dir ):
            raise ValueError( "Only give one of base_path or base_dir, they mean the same thing." )
        base_path = base_path if base_path is not None else base_dir if base_dir is not None else None
        self._set_base_path( base_path, no_base_path )

        self._filepath = pathlib.Path( filepath ) if filepath is not None else None

        if full_filepath is not None:
            full_filepath = pathlib.Path( full_filepath ).resolve()
            if self._no_base_path:
                if self._filepath is not None:
                    if self._filepath.resolve() != full_filepath:
                        raise ValueError( f"Error, no_base_path is true, filepath resolves to "
                                          f"{self.filepath.resolve()}, and full_filepath resolves to "
                                          f"{full_filepath}; these are inconsistent." )
                self._filepath = full_filepath

            else:
                try:
                    nominal_filepath = full_filepath.relative_to( self._base_path )
                except ValueError:
                    raise ValueError( f"base_path is {self._base_path}, but full_filepath {full_filepath} "
                                      f"cannot be made relative to that." )

                if self._filepath is None:
                    self._filepath = nominal_filepath
                else:
                    if self._filepath != nominal_filepath:
                        raise ValueError( f"Error, filepath is {self._filepath}, but given base path {self._base_path} "
                                          f"and full path {full_filepath}, this is inconsistent." )

        elif self._no_base_path:
            self._filepath = self._filepath.resolve()


    def _set_base_path( self, base_path=None, no_base_path=False ):
        self._no_base_path = no_base_path
        if no_base_path:
            if base_path is not None:
                raise ValueError( "Cannot specify a base_path (or base_dir) if no_base_path is True." )
            self._base_path = None
        else:
            self._base_path = pathlib.Path( base_path if base_path is not None else
                                            Config.get().value( self._base_path_config_item )
                                           ).resolve()



    @property
    def filepath( self ):
        if self._filepath is None:
            self.generate_filepath()
        return self._filepath

    @filepath.setter
    def filepath( self, val ):
        self._filepath = pathlib.Path( val )
        if self._no_base_path:
            self._filepath = self._filepath.resolve()

    # filename deliberately has no setter
    @property
    def filename( self ):
        return self.filepath.name if self.filepath is not None else None

    @property
    def base_path( self ):
        return self._base_path

    @base_path.setter
    def base_path( self, val ):
        if self._no_base_path is True:
            raise RuntimeError( f"{self.__class__.__name__} object has no_base_path=True, can't set base path" )
        self._base_path = pathlib.Path( val )

    @property
    def base_dir( self ):
        return self._base_path

    @base_dir.setter
    def base_dir( self, val ):
        self.base_path = val

    # full_filepath deliberately does not have a setter
    @property
    def full_filepath( self ):
        if self._no_base_path:
            return self._filepath.resolve()
        else:
            return self._base_path / self._filepath

    def generate_filepath( self ):
        """Classes that have default filepaths should override this function to set self._filepath."""
        raise NotImplementedError( f"{self.__class__.__name__} hasn't implemented generate_filepath." )
