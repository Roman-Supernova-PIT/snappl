import pathlib


class PathedObject:
    """An object that might be stored in the database but that also has files on disk.

    Here so we can have a semi-unified interface.

    Standard properties of a PathedObject are:

      * filepath : pathlib.Path : path of the object *relative to* the base path for this kind of object
                                  This is what gets stored in the database.

      * full_filepath : pathlib.Path : the absolute path to the file on disk.  (But see
                                       "complications" below.)  This attribute is usually derived
                                       from base_path and filepath.

      * base_path : pathlib.Path : base path for this kind of object.  Normally this is from the
                                   config, and is the base path for this kind of object.  (For
                                   instance, for L2 images, base_path is the directory pointed to by
                                   config value "system.paths.images").  However, for backwards
                                   compatibility, we want to be able to support objects that aren't
                                   in the database, so you can set a custom base_path, if you need
                                   to, every time you create an object.  * full_filepath :

       * filename : string : the name part of filepath (so if filepath is Path("/foo/bar"), filename is "bar").

    Complications:

    This class is designed implicitly assuming that one row in the database corresponds to one
    PathedObject object, and to one file on disk.  Sometimes that may not be true, e.g. an image
    might not have the image, noise, and flags arrays all packed into one file, but in three
    different files.  In that case, the subclass must know how to deal with this, and "filepath" may
    not be the path to an actual file, but to a path to the name of which you must append additional
    standard stuff to find the file.  (The one extant example of this is the image.FITSImage class
    with std_imagenames set to True.)

    """


    def __init__( self, filepath=None, base_path=None, base_dir=None, full_filepath=None, no_base_path=False ):
        """Set up object paths.

        Parameters
        ----------
          filepath : str or Path, default None
            Path of the file relative to base_path

          base_path, base_dir : str or Path, default None
            Only use one of these; they set the same thing.  Most of the time
            you do *not* want to specify this, but leave it at the default.
            If no_base_path is True, you *must* leave these at None.  This is
            the base path for objects of the subclass of PathedObject that is
            being constructed.  By default (which is usually what you want),
            it will use the class' _get_base_path() function, which usually
            gets a value out of Config

          full_filepath : str or Path, default None
            Usually you don't want to specify this, unless no_base_path=True

          no_base_path : bool, default False
            You may want to set this to True if you are dealing with
            files that aren't tracked by the database.  In that case,
            you can't specify base_path (or base_dir), and filepath and
            full_filepath mean the same thing (and must be the same if
            for some reasdon you give both).

        """
        self._no_base_path = bool( no_base_path )

        # It's weird to have this above the no_base_path check,
        #   but it's needed because of gyrations in image.Image
        #   that are there for backwards compatibility.
        # (image.Image._get_base_path might modify self._no_base_path.)

        base_path = ( base_path if base_path is not None
                      else base_dir if base_dir is not None
                      else self._get_base_path() )
        self._base_path = pathlib.Path( base_path ) if base_path is not None else None

        # Mostly this is a lot of error checking and consistencey

        if self._no_base_path:
            if ( base_path is not None ) or ( base_dir is not None ):
                raise ValueError( "Can't give a base_path or base_dir when no_base_path is True" )
            self._base_path = None
        else:
            if ( base_path is not None ) and ( base_dir is not None ) and ( base_path != base_dir ):
                raise ValueError( "Only give one of base_path or base_dir, they mean the same thing." )

        self._filepath = pathlib.Path( filepath ) if filepath is not None else None

        if ( full_filepath is not None ):
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


    def _get_base_path( self ):
        """Return the base path for objects of this class that are in the database."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement _get_base_path" )


    @property
    def filepath( self ):
        if self._filepath is None:
            self.generate_filepath()
        return self._filepath

    @filepath.setter
    def filepath( self, val ):
        self._filepath = pathlib.Path( val )

    # filename deliberately has no setter
    @property
    def filename( self ):
        return self.filepath.name if self.filepath is not None else None

    @property
    def base_path( self ):
        return self._base_path

    @base_path.setter
    def base_path( self, val ):
        self._base_path = pathlib.Path( val )

    @property
    def base_dir( self ):
        return self._base_path

    @base_dir.setter
    def base_dir( self, val ):
        self._base_path = pathlib.Path( val )

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
