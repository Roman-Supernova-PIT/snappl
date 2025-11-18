__all__ = [ 'Config', 'NoValue', 'NotFoundValue' ]

import argparse
import copy
import numbers
import os
import pathlib
import types
import yaml

from snappl.logger import SNLogger


class NoValue:
    """Used internally by Config, ignore."""
    pass


class NotFoundValue:
    """Used internally by Config, ignore."""
    pass


class Config:
    """Interface for yaml config file.

    Read a yaml file that might include other yaml files, and provide an
    interface. The top level of the yaml must be a dict. Only supports
    dicts, lists, and scalars.


    USAGE

    1. Instantiate a config object with::

           confobj = Config.get()

       or::

           confobj = Config.get(filename)

       in the former case, it will get the default file (see below).
       IMPORTANT : Do NOT instantiate a config item with ``config=Config()``.

       The default file: normally, the default file is specified in the
       environment variable ``SNPIT_CONFIG``.  The first time you call
       ``Config.get()`` without any arguments, it will set the default
       config to be what it read from the file pointed to by
       ``$SNPIT_CONFIG``, and return that config.  You can subvert this
       by calling ``Config.get(filename,setdefault=True)``.  In that
       case, it will read the file in filename, and set the config there
       to be the default config that you'll thereafter get when calling
       ``Config.get()`` without any arguments.

       If the config file has a lot of levels to it, and you are only
       intersted in a subset, you can do::

           confobj = Config.get( prefix='toplevel.midlevel' )

       Thereafter, if you do ``Config.value('sublevel.value')``, it will
       be equivalent to having done
       ``Config.value('toplevel.midlevel.sublevel.value')`` on an object
       you get with just ``Config.get()``.


    2. (Optional.)  You can set things up so that (almost) anything in
       the config can be overridden on the command line.  You must be
       using argparse for this to work.  First, instantiate your
       ``argparse.ArgumentParser`` object and add your own arguments.
       Next, call the ``augment_argparse()`` method of your ``Config``
       object.  Run the ``parse_args()`` method of your
       ``ArgumentParser``, and then pass the return value to the
       ``parse_args()`` method of your ``Config`` object.  For example::

         from snappl.config import Config
         import argparse

         cfg = Config.get()

         parser = argparse.ArgumentParser( 'test.py', description='Do things' )
         parser.add_argument( "-m", "--my-argument", help="My argument; there may be more" )
         cfg.augment_argparse( parser )
         args = parser.parse_args()
         cfg.parse_args( args )

       ``Config.augment_argparse`` will add all of the "leaf node" config
       options as config arguments, using the fieldspec (see (3) below),
       replacing "." with "-".  Exception: if there is a list, it will
       not work down into the list, but will replace the whole list with
       as single multi-valued argument.  For example, if your config is::

          scalar: val

          dict:
            key1: val
            key2:
              subkey1: val
              subkey2: val
            list:
              - val
              - val2

       Then you when you call Config.augment_argparse, you will have new arguments::

           --scalar
           --dict-key1
           --dict-key2-subkey1
           --dict-key2-subkey2
           --dict-list   ( with nargs="*" )

       You should ignore these; when you call Config.parse_args, it will
       look for all of them.

    3. Get the value of something in your config with::

           configval = confobj.value( fieldspec )

       where fieldspec is just the field for a scalar, or .-separated
       fields for lists and dicts.  For lists, it must be a (0-offset)
       integer index.  For example, if the yaml files includes::

         storage:
           images:
             format: fits
             single_file: false
             name_convention: "{inst_name}_{date}_{time}_{section_id}_{band}_{im_type}_{prov_hash:.6s}"

       then ``confobj.value("storage.images.format")`` will return
       ``"fits"``. You can also ask ``configobj.value`` for higher
       levels.  For example, ``config.value("storage.images")`` will
       return a dictionary::

          { "format": "fits",
            "single_file": False,
            "name_convention": "{inst_name}_{date}_{time}_{section_id}_{band}_{im_type}_{prov_hash:.6s}"
          }

    4. Change a config value with::

           confobj.set_value( fieldspec, value )

       This only changes it for the running session, it does *not*
       affect the YAML files in storage.  This will usually not work.
       To use this, you must have set static to False when calling
       Config.get.  You should use this with great care, and if you're
       using it outside of tests, make sure to carefully evaluate your
       life choices.  The whole point of this config system is that it's
       an interface to config files, so if you're making runtime
       changes, then things are scary.


    CONFIG FILES

    This class reads yaml files (which can have other included yaml
    file).  The top level structure of a config file must be a
    dictionary.

    When reading a config file, it is processed as follows:

    The "current working config" starts as an empty dictionary (``{}``).
    When everything is done, it can be a big messy hierarchy.  Each key
    of the top level dictionary can have a value that is a scalar, a
    list, or a dictionary.  The structure is recursive; each element of
    each list can be a scalar, a list, or a dictionary, and the value
    associated with each key in each dictionary can itself be a scalar,
    a list, or a dictionary.

    A config file can have several special keys::

        preloads
        replaceable_preloads
        augments
        overrides
        destructive_appends
        appends

    The value associated with each key is a list of file paths relative
    to the directory where this file is found.  All of this can get
    quite complicated, so use a lot of caution when using it.  The
    safest thing to do is to only use preloads and augments.


    HOW PARSING THE CONFIGS WORK

    To really understand the following, you have to read "DEFINITION OF
    TERMS" below.  Repeating what is said above, and will be said again,
    all of this is very complicated, so to be safe you may wish to never
    use any of the special keys other than "preloads" and "augments".

    ``preloads`` is a list of files which are read first, in order, to make
      a config dictionary (called the "preload config dictionary").
      Files later in the list *augment* the config info from files
      earlier in the list.  This config dictionary is set aside for the
      time being.

    ``replaceable_preloads`` is list of files read next, in order, to make
      a new config dictionary (called the "working config dictionary").
      Files later in the list *destructive_append* files earlier in
      the list.

    The current file is parsed next.  It does a *destructive_append* on
      the working config dictionary (which will just be ``{}`` if there
      aren't any replaceable_prelaods).  Then, the working config
      dictionary *augments* the preload config dictionary, and the
      result is the new working config dictionary.

    ``augments`` is a list of files read next, in order.  Each one
      *augments* the current working dictionary.

    ``overrides`` is a list of files read next, in order.  Each one
      *overrides* the current working dictionary.

    ``destructive_appends`` is a list of files read next, in order.  Each
      one does a *destructive_append* on the current working dictionary.

    ``appends`` is a list of files read last.  Each one *appends* to the
      current working dictionary.

    Any file that's read can itself have the special keys indicating
    other files to include.  If there is any circular inclusion -- or,
    really, if any file is referred to more than once when the whole
    thing is being parsed -- that is an error and will raise an
    exception.  (This isn't a perfect protection.  You can do things
    with symbolic links to get around this and effectively have one file
    include another which then includes the first one again.  Just don't
    do that.)


    DEFINITION OF TERMS

    Above, the words "destructive_augment", "augment", "override", and
    "append" were used to describe how to combine information from two
    different files.  Exactly what happens is complicated; if you
    *really* want to know, see the source code of::

      util/config.py::Config._merge_trees()

    Here's an attempt to define it.  For all the operations below, we
    are trying to combine two values-- call them the "left" value and
    "right" value.  Initially, that's the two dictionaries that are the
    top level things being combined, but later it might be something
    else.  To compare two values:

    augment
       This is the safest one.  If you try to set a config option that
       is already set, it will raise an exception.  This is what you use
       if you want to protect yourself against accidentally setting the
       same option in more than one file and not realizing it, which can
       lead to all kinds of confusion.  Indeed, if you're worried about
       this, *never* use anything other than preloads and augments.

       * If the left and right values have different types, types (scalar
         vs. list vs. dict), this is an error.  This will never happen
         at the very top level, because both left and right are
         dictionaries at the top level.

       * If the current item being compared is a list or a scalar, then
         this is an error; you're not allowed to replace an
         already-existing list or scalar config option.

       * If the current item being compared is a dictionary, then merge
         the two dictionaries.  Any keys in the right dictionary that
         aren't in the left dictionary are added to the left dictionary
         with the value from the right dictionary.  If a key is already
         in both dictionaries, then it recurses using the augment
         method.

    append
       Generally speaking, stuff in the right value is added to stuff in
       the left value, but nothing from the left value will be replaced.

       * If the current item being compared have different types (scalar
         vs. list vs. dict), this is an error.  This will never happen
         at the very top level, because both left and right are
         dictionaries at the top level.

       * If the item being compared is a list, then then the right list
         extends the left list.  (Literally using list.extend().)

       * If the item being compared is a scalar, then this is an error.

       * If the current item being compared is a dictionary, then merge
         the two dictionaries.  Any keys in the right dictionary that
         aren't in the left dictionary are added to the left dictionary
         with the value from the right dictionary.  If a key is already
         in both dictionaries, then it recurses using the append
         method.


    destructive_append
        Works much like augment with the exception that if the item
        being compared is a scalar, then the right value replaces the
        left value.

    override
       Generally speaking, when overriding, the right value replaces the
       left value, but there are wrinkles.

       * If the current item being compared have different types (scalar
         vs. list vs. dict), the new (right) value *replaces* the old
         (left) value.  This will never happen at the very top level,
         because both left and right are dictionaries at the top level.
         Be warned: you can wipe out entire trees of config options
         here!  (Imagine if the left tree had a dictionary and the right
         tree had a scalar.)

       * If the current item being compared is a dictionary, then
         the dictionaries are merged in exactly the same manner
         as "append", with the modification that recursing down
         into the dictionary passes along the fact that we're
         overriding rather than append.

       * If the current item being compared is a list, then the
         right list *replaces* the left list.  (This could
         potentially throw away a gigantic hierarchy if lists
         and dicts and scalars from the left wide, which is as
         designed.)

       * If the item being compared is a scalar, then the right value
         replaces the left value.

    This can be very confusing, so keeping your config files simple.


   WARNINGS

    * Won't work with any old yaml file.  Top level must be a dictionary.
      Don't name your dictionary fields as numbers, as the code will then
      detect it as a list rather than a dict.

    * The yaml parser seems to be parsing "yyyy-mm-dd" strings as a
      datetime.date; beware.

    * python's yaml reading of floats is broken.  It will read 1e10 as a
      string, not a float.  Write 1.0e+10 to make it work right.  There
      are two things here: the first is the + after e (which, I think
      *is* part of the yaml spec, even though we can freely omit that +
      in Python and C).  The second is the decimal point; the YAML spec
      says it's not necessary, but python won't recognize it as a float
      without it.

    """

    # If a config file has never been specified anywhere, looking in the
    #   SNPIT_CONFIG env var to try to figure out what to read.
    _default_default = os.getenv( 'SNPIT_CONFIG', None )

    _default = None
    _configs = {}


    @staticmethod
    def init( configfile=None, setdefault=None ):
        """Initialize configuration globally for process.

        Parameters
        ----------
        configfile : str or pathlib.Path, default None
            See documentation of the configfile parameter in Config.get

        setdefault : bool, default None
            See documentation of the setdefault parameter in Config.get

        """
        Config.get( configfile, setdefault=setdefault )


    @staticmethod
    def get( configfile=None, setdefault=None, prefix=None, static=True, reread=False, clone=None ):
        """Returns a Config object.

        Parameters
        -----------
        configfile : str or Pathlib.Path, default None
            The config file to read (if it hasn't been read before, or
            if reread is True).  If None, will return the default config
            context for the current session (which is normally the one
            in the file pointed to by environment variable
            SNPIT_CONFIG, but see "setdefault" below.  If that env
            var is needed but not set, then an exception will be
            raised).

        setdefault : bool, default None
            Avoid use of this, as it is mucking about with global
            variables and as such can cause confusion.  If True, set the
            Config object read by this method to be the session default
            config.  If False, never set the Config object read by this
            method to be the session default config.  If not specified,
            which is usually what you want, then if configfile is None,
            the configfile in SNPIT_CONFIG will be read and set to the
            be the session default Config; if configfile is not None,
            read that config file, but don't make it the session default
            config.

            Normal usage of Config is to make a call early on to either
            Config.init() or Config.get() without parameters.  That will
            read the config file in SNPIT_CONFIG and make that the
            default config for the process.  If, for some reason, you
            want to read a different config file and make that the
            default config file for the process, then pass a configfile
            here and make setdefault True.  If, for some truly perverse
            reason, you want to the config in SNPIT_CONFIG but not
            set it to the session default, then call
            Config.get(setdefault=False), and question your life
            choices.

        prefix : string, default None

            If not None, then all calls to the .value() and .set_value()
            methods of the config object will add this string (followed
            by a .) to the string you actually pass.  So, for instance,
            if your config file consists of::

              toplevel:
                midlevel1:
                  sublevel1:
                    val1: 1
                    val2: 2
                  sublevel2:
                    str1: cat
                    str2: kitten
                midlevel2:
                  foo: bar

            then, if you did::

               cfg = Config.get( prefix='toplevel.midlevel1' )

            then ``cfg.value('sublevel1.val1')`` would return ``1``, and
            ``cfg.value('sublevel1.val2')`` would return ``2``.  This is
            here as a convenience to save you from typing a bunch of
            extra stuff when within one function you only need part of
            the config hierarchy.


        static : bool, default True
            If True (the default), then you get one of the config object
            singletons described below.  In this case, it is not
            permitted to modify the config.  If False, you get back a
            clone of the config singleton, and that clone is not stored
            anywhere other than the return value.  In this case, you may
            modify the config.  Call Config.get(static=False) to get a
            modifiable version of the default config.

        reread : bool, default False
           If True, then the config file will be reread if it's already
           been cache.  If static is True and reread is True, then the
           singleton will be modified (meaning that thereafter, whenever
           you get() that singleton, you'll get the new config values
           that were just reread here).  If static is False and reread
           is True, then you the returned Config object will read the
           config files from disk, but will not change the singleton.
           Ignored if clone is not None.

        clone : Config, default None
            If given, return a clone of this Config object.  The
            returned object, if all is working properly, is a deep copy,
            so it should be safe to mangle it.  It's not possibe to set
            a cloned config object as default, nor is the cloned object
            ever set as a singleton, so setdefault and static are both
            ignored and treated as False when making a clone.


        Returns
        -------
            Config object

        Config objects are stored as an array of singletons (as class
        variables of the Config class).  That is, if you pass a config
        file that has been passed before in the current execution
        context, you'll get back exactly the same object each time
        (unless static is True).  If you pass a config file that hasn't
        been passed before, it will read the indicated configuration
        file, cache an object associated with it for future calls, and
        return that object (unless static is False, in which case the
        the object is still cached, but you get a copy of that object
        rather than the object itself).

        If you don't pass a config file, then you will get back the
        default config object.  If there is no default config object
        (because neither Config.get() nor Config.init() have been called
        previously), and if the class is not configured with a "default
        default", then an exception will be raised.

        """

        if clone is not None:
            if configfile is not None:
                raise ValueError( "Only specify one of clone or configfile." )
            cfg = Config( clone=clone, _ok_to_call=True )

        else:
            if configfile is None:
                if Config._default is not None:
                    configfile = Config._default
                else:
                    if Config._default_default is None:
                        raise RuntimeError( 'No default config defined yet; run Config.init(configfile)' )
                    configfile = Config._default_default
                    if setdefault is None:
                        setdefault = True

            configfile = str( pathlib.Path(configfile).resolve() )

            if setdefault:
                Config._default = configfile

            if reread or ( configfile not in Config._configs ):
                cfg = Config( configfile=configfile, _ok_to_call=True )
                if static or ( not reread ):
                    Config._configs[configfile] = cfg
                else:
                    cfg._static = False
            else:
                if static:
                    cfg = Config._configs[configfile]
                else:
                    cfg = Config( clone=Config._configs[configfile], _ok_to_call=True )

        # prefix is a little scary.  It's not going to use its own _data array;
        #   rather, it's going to use the parent config's data array, so if
        #   either is modified, the changes are reflected in both.  (This should
        #   usually only be possible in cloned configs, unless the user has
        #   been naughty and mucked about with the _static property.)
        if prefix is not None:
            if ( not isinstance( prefix, str ) ) or ( len( prefix ) == 0 ):
                raise TypeError( f"prefix must be a str of lengt ≥ 1, not a {type(prefix)}" )
            if prefix[-1] == '.':
                raise ValueError( 'prefix must not end in "."' )
            val = cfg.value( prefix )
            if ( not isinstance( val, dict ) ) and ( not isinstance( val, list ) ):
                raise ValueError( f"\"{prefix}\" is an invalid prefix: it doesn't point to a "
                                  f"sub-list or sub-dictionary in the config structure." )
            parentcfg = cfg
            cfg = Config( _ok_to_call=True )
            cfg._data = None
            cfg._parentconfig = parentcfg
            cfg._prefix = prefix
            cfg._static = parentcfg._static

        return cfg


    # SOMETHING I DON'T UNDERSTAND:
    #    When I had files_read=set() in the function definition,
    #    later calls to __init__ started this function that did
    #    not explicitly pass that parmeter did not have an empty
    #    set for files_read!  My understanding of python is in
    #    that case, files_read should have been initialized to
    #    a new set.  But it wasn't!  WTF?  Doing the "None"
    #    thing as a workaround.
    def __init__( self, configfile=None, clone=None, files_read=None, _ok_to_call=False ):
        """Don't directly instantiate a Config object, call static method Config.get().

        Parameters
        ----------
        configfile : str or Path, or None

        clone : Config object, default None
          If clone is not None, then build the current object as a copy of
          the config object passed in clone.  In this case, the returned
          config object is modifiable.

          Otherwise, read the configfile and build the object based on
          that; in this case, the returned config object is not supposed
          to be modified, and set_value won't work.  (Of course, you can
          always go and muck about directly with the _data property, but
          don't do that!)

        """

        if not _ok_to_call:
            raise RuntimeError( "Don't instantiate a Config directly; use configobj=Config.get(...)." )

        self._static = True
        self._parentconfig = None
        self._prefix = None

        if clone is not None:
            if not isinstance( clone, Config ):
                raise TypeError( f"Clone must be a Config, not a {type(clone)}" )
            if clone._parentconfig is not None:
                data = clone._parentconfig.value( clone._prefix )
                if not isinstance( data, dict ):
                    raise TypeError( "Cannot clone a config whose top level element is a list "
                                     "(this may happen when using a config created with a prefix)" )
                self._data = copy.deepcopy( data  )
            else:
                self._data = copy.deepcopy( clone._data )
            self._static = False
            return

        self._data = {}

        if configfile is not None:
            self._path = pathlib.Path( configfile ).resolve()

            files_read = set() if files_read is None else files_read
            if self._path in files_read:
                raise RuntimeError( f"Config file {self._path} was read more than once!  Circular dependencies!" )
            files_read.add( self._path )

            try:
                SNLogger.debug( f"Loading config file {self._path}" )
                curfiledata = yaml.safe_load( open(self._path) )
                if curfiledata is None:
                    # Empty file, so self._data can stay as {}
                    return
                if not isinstance( curfiledata, dict ):
                    raise RuntimeError( f"Config file {configfile} doesn't have yaml I like." )

                imports = { 'preloads': [], 'replaceable_preloads': [], 'augments': [],
                            'overrides': [], 'destructive_appends': [], 'appends': [] }
                for importfile in imports.keys():
                    if importfile in curfiledata:
                        if not isinstance( imports[importfile], list ):
                            raise TypeError( f'{importfile} must be a list' )
                        imports[importfile] = curfiledata[importfile]
                        del curfiledata[importfile]

                preloaddict = {}
                for preloadfile in imports['preloads']:
                    cfg = Config( self._pathify(preloadfile), files_read=files_read, _ok_to_call=True )
                    preloaddict = self._merge_trees( '', preloaddict, cfg._data, mode='augment' )

                workingdict = {}
                for preloadfile in imports['replaceable_preloads']:
                    cfg = Config( self._pathify(preloadfile), files_read=files_read, _ok_to_call=True )
                    workingdict = self._merge_trees( '', workingdict, cfg._data, mode='destructive_append' )

                workingdict = self._merge_trees( '', workingdict, curfiledata, mode='destructive_append' )
                self._data = self._merge_trees( '', preloaddict, workingdict, mode='augment' )

                for augmentfile in imports['augments']:
                    self._merge_file( augmentfile, 'augment', files_read=files_read )

                for overridefile in imports['overrides']:
                    self._merge_file( overridefile, 'override', files_read=files_read )

                for appendfile in imports['destructive_appends']:
                    self._merge_file( appendfile, 'destructive_append', files_read=files_read )

                for appendfile in imports['appends']:
                    self._merge_file( appendfile, mode='append', files_read=files_read )

            except Exception as e:
                SNLogger.exception( f'Exception trying to load config from {configfile}' )
                raise e


    def value( self, field=None, default=NoValue(), struct=None ):
        """Get a value from the config structure.


        Parameters
        ----------
        field: str
          The field specification, relative to the top level of the
          config.  So, to get the value of a keyword aligned to column 0
          of the config file, the field is just that keyword.  For
          trees, separate fields by periods.  If there is an array
          somewhere in the tree, then the array index as a number is the
          field for that branch.

           For example, if the config yaml file is;

           scalar: value

           dict1:
             dict2:
               sub1: 2level1
               sub2: 2level2

           dict3:
             list:
               - list0
               - list1

           then you could get values with:

           configobj.value( "scalar" ) --> returns "value"
           configobj.value( "dict1.dict2.sub2" ) --> returns "2level2"
           configobj.value( "dict3.list.1" ) --> returns "list1"

           You can also specify a branch to get back the rest of the
           subtree; for instance configobj.value( "dict1.dict2" ) would
           return the dictionary { "sub1": "2level1", "sub2": "2level2" }.

           If this is None, return the entire config tree as a
           dictionary (or, if working with a confg created with prefix=,
           maybe a list).

        default: object, default NoValue instance
            Used internally, don't muck with this.

        struct: dict, default None
            If passed, use this dictionary in place of the object's own
            config dictionary.  Avoid use.

        Returns
        -------
        int, float, str, list, or dict

          If a list or dict, you get a deep copy of the original list or
          dict.  As such, it's safe to modify the return value without
          worrying about changing the internal config.  (If you want to
          change the internal config, use set_value().)

        """

        if field is None:
            if self._parentconfig is not None:
                return self._parentconfig.value( self._prefix )
            else:
                return self._data

        else:
            cfg = self
            if self._parentconfig is not None:
                cfg = self._parentconfig
                field = f'{self._prefix}{f".{field}" if field is not None else ""}'

            _, _, value = cfg._parent_key_and_value( field, parent=None, struct=struct, default=default )
            return value


    def set_value( self, field, value, structpass=None, appendlists=False ):
        """Set a value in the config object.

        If the config object was created with static=True (which is the
        case for all the singleton objects stored in the Config class),
        use of this method raises an exception.

        Parameters
        ----------
        field: str
            See value() for more information

        value: str, int, float, list, or dict

        structpass: some object with a ".struct" field
           Used internally when the Config object is building it's own
           _data field; don't use externally

        appendlists: bool, default False
           If true and if field is a pre-existing list, then value is
           appended to the list.  Otherwise, value replaces the
           pre-existing field if there is one.

        Does not save to disk.  Follows the standard rules docuemnted in
        "augment" and "override"; if appendlists is True, uses
        "augment", else "override".  Will create the whole hierarchy if
        necessary.

        """

        if self._parentconfig is not None:
            field = f'{self._prefix}{f".{field}" if field is not None else ""}'
            self._parentconfig.set_value( field, value, structpass=structpass, appendlists=appendlists )
            return

        if self._static:
            raise RuntimeError( "Not permitted to modify static Config object." )

        if structpass is None:
            structpass = types.SimpleNamespace()
            structpass.struct = self._data
        elif not hasattr( structpass, 'struct' ):
            raise ValueError( 'structpass must have a field "struct"' )
        fields, isleaf, curfield, ifield = self._fieldsep( field )

        if isleaf:
            if isinstance( structpass.struct, list ):
                if appendlists:
                    if ifield is None:
                        raise TypeError( "Tried to add a non-integer field to a list." )
                    structpass.struct.append( value )
                else:
                    if ifield is None:
                        structpass.struct = { curfield: value }
                    else:
                        structpass.struct = [ value ]
            elif isinstance( structpass.struct, dict ):
                if ifield is not None:
                    raise TypeError( "Tried to add an integer field to a dict." )
                structpass.struct[curfield] = value
            else:
                structpass.struct = { curfield: value }
        else:
            structchuck = types.SimpleNamespace()
            try:
                nextifield = int( fields[1] )
            except ValueError:
                nextifield = None

            if isinstance( structpass.struct, list ):
                structchuck.struct = {} if nextifield is None else []
                self.set_value( ".".join(fields[1:]), value, structchuck, appendlists=appendlists )
                if appendlists:
                    if ifield is None:
                        raise TypeError( "Tried to add a non-integer field to a list" )
                    structpass.struct.append( structchuck.struct )
                else:
                    if ifield is None:
                        structpass.struct = { curfield: structchuck.struct }
                    else:
                        structpass.struct = [ structchuck.struct ]
            else:
                if ifield is None:
                    if isinstance( structpass.struct, dict ):
                        if curfield in structpass.struct:
                            structchuck.struct = structpass.struct[curfield]
                        else:
                            structchuck.struct = {} if nextifield is None else []
                    else:
                        structpass.struct = {}
                    self.set_value( ".".join(fields[1:]), value, structchuck, appendlists=appendlists )
                    structpass.struct[curfield] = structchuck.struct
                else:
                    if isinstance( structpass.struct, dict ):
                        raise TypeError( "Tried to add an integer field to a dict." )
                    structchuck.struct = {} if nextifield is None else []
                    self.set_value( ".".join(fields[1:]), value, structchuck, appendlists=appendlists )
                    structpass.struct = [ structchuck.struct ]


    def _parent_key_and_value( self, field, parent=None, struct=None, fullfield=None, default=NoValue ):
        if ( self._parentconfig is not None ) or ( self._prefix is not None ):
            raise RuntimeError( "This should never happen." )

        fullfield = fullfield if fullfield is not None else field
        if struct is None:
            struct = self._data
        fields, isleaf, curfield, ifield = self._fieldsep( field )

        if isinstance( struct, list ):
            if ifield is None:
                raise ValueError( f'Failed to parse {curfield} of {fullfield} as an integer index' )
            elif ifield < 0:
                if isinstance( default, NoValue ):
                    raise ValueError( f'Array index {ifield} is negative for {fullfield}' )
                else:
                    return_parent = struct
                    return_key = ifield
                    return_value = default
            elif ifield >= len(struct):
                if isinstance( default, NoValue ):
                    raise ValueError( f'{ifield} >= {len(struct)}, the length of the list for {fullfield}' )
                else:
                    return_parent = struct
                    return_key = ifield
                    return_value = default
            elif isleaf:
                return_parent = struct
                return_key = ifield
                return_value = struct[ifield]
            else:
                return_parent, return_key, return_value = self._parent_key_and_value( ".".join(fields[1:]),
                                                                                      parent=struct,
                                                                                      struct=struct[ifield],
                                                                                      fullfield=fullfield,
                                                                                      default=default )

        elif isinstance( struct, dict ):
            if curfield not in struct:
                if isinstance( default, NoValue ):
                    raise ValueError( f"Can't find field {fullfield}" )
                else:
                    return_parent = struct
                    return_key = curfield
                    return_value = default
            elif isleaf:
                return_parent = struct
                return_key = curfield
                return_value = struct[curfield]
            else:
                return_parent, return_key, return_value = self._parent_key_and_value( ".".join(fields[1:]),
                                                                                      parent=struct,
                                                                                      struct=struct[curfield],
                                                                                      fullfield=fullfield,
                                                                                      default=default )

        else:
            if not isleaf:
                raise ValueError( f'Tried to get field {field} of scalar {curfield} in {fullfield}!' )
            return_parent = parent
            return_key = curfield
            return_value = struct

        if isinstance(return_value, (dict, list)):
            return_value = copy.deepcopy( return_value )

        return return_parent, return_key, return_value


    def delete_field( self, field, missing_ok=False ):
        """Remove a field from the config.

        Use this this with great care.

        """
        if self._parentconfig is not None:
            field = f'{self._prefix}{f".{field}" if field is not None else ""}'
            self._parentconfig.delete_field( field, missing_ok=True )
            return

        if self._static:
            raise RuntimeError( "Not permitted to modify static Config object." )

        parent, key, value = self._parent_key_and_value( field, default=NotFoundValue() )
        if isinstance( value, NotFoundValue ):
            if missing_ok:
                return
            else:
                raise ValueError( f"Can't find config field {field} to delete it." )

        if isinstance( parent, list ):
            parent.pop( key )
        elif isinstance( parent, dict ):
            del parent[key]
        else:
            # ... I think this shouldn't ever actually happen
            raise RuntimeError( "Rob, figure out how to cope with this." )


    @classmethod
    def _fieldsep( cls, field ):
        """Parses a period-separated config specifier string.  Internal use only.

        Parameters
        ----------
        field: str
            A field specifier to parse

        Returns
        -------
        tuple with 4 elements: fields, isleav, curfield, ifield.
          fields : list of the hierarchy (e.g. "val1.val2.val3" returns ["val1","val2","val3"])
          isleaf : True if len(fields) is 1, otherwise false
          curfield : The first element of the field (val1 in the example above)
          ifield : None if curfield is not an integer, otherwise the integer value of curfield

        """
        fields = field.split( "." )
        isleaf = ( len(fields) == 1 )
        curfield = fields[0]
        try:
            ifield = int(curfield)
        except ValueError:
            ifield = None
        return fields, isleaf, curfield, ifield


    @classmethod
    def _is_parent_field( cls, parent, child ):
        parent = parent.split( "." )
        child = child.split( "." )
        if len(parent) >= len(child):
            return False
        return child[ 0 : len(parent) ] == parent


    @classmethod
    def _allkeys( cls, struct, base="" ):
        keys = []

        if isinstance( struct, dict ):
            for key, val in struct.items():
                keys.append( f"{base}{key}" )
                keys.extend( cls._allkeys( val, base=f'{base}{key}.' ) )
        elif isinstance( struct, list ):
            for i, val in enumerate( struct ):
                keys.append( f"{base}{i}" )
                keys.extend( cls._allkeys( val, base=f'{base}{i}.' ) )
        else:
            return []

        return keys


    def _pathify( self, fname ):
        if ( self._parentconfig is not None ) or ( self._prefix is not None ):
            raise RuntimeError( "This should never happen." )

        fname = pathlib.Path( fname )
        if fname.is_absolute():
            return fname
        else:
            return self._path.parent / fname


    def _merge_file( self, path, mode, files_read=None ):
        if ( self._parentconfig is not None ) or ( self._prefix is not None ):
            raise RuntimeError( "This should never happen." )

        files_read = { self._path } if files_read is None else files_read
        cfg = Config( self._pathify(path), files_read=files_read, _ok_to_call=True )
        self._data = self._merge_trees( '', self._data, cfg._data, mode=mode )


    @staticmethod
    def _merge_trees( keyword, left, right, mode='augment', parentpath='' ):
        """Internal usage, do not call."""
        ppath = f"{parentpath}." if len(parentpath) > 0 else ""
        errkeyword = f'{ppath}{keyword}'

        if mode not in ( 'append', 'augment', 'destructive_append', 'override' ):
            raise ValueError( f"Unknown mode {mode} for {errkeyword}" )

        if not isinstance( left, dict ):
            if mode == 'override':
                return copy.deepcopy( right )

            if isinstance( left, list ):
                if isinstance( right, list ) and ( mode in ('append', 'destructive_append') ):
                    newlist = copy.deepcopy( left )
                    newlist.extend( copy.deepcopy( right ) )
                    return newlist

            elif not ( isinstance( right, list ) or isinstance( right, dict ) ):
                if mode == 'destructive_append':
                    return right

        else:
            if not isinstance( right, dict ):
                if mode == 'override':
                    return copy.deepcopy( right )
            else:
                newdict = copy.deepcopy( left )
                for key, value in right.items():
                    if key not in newdict:
                        newdict[key] = copy.deepcopy( value )
                    else:
                        newdict[key] = Config._merge_trees( key, newdict[key], value, mode=mode,
                                                            parentpath=f"{ppath}{keyword}" )
                return newdict

        raise RuntimeError( f"Error combining key {errkeyword} with mode {mode}; left is a {type(left)} "
                            f"and right is a {type(right)}" )



    def augment_argparse( self, parser, path='', _dict=None ):
        """Add arguments to an ArgumentParser for all config values.

        See the Config docstring for instructions on use.

        Parameters
        ----------
          parser : ArgumentParser
            The ArgumentParser to which additional arguments should be added.

          path : str
            Used internally for recursion.

          _dict : dict
            Used internally for recursion.

        """
        if ( self._parentconfig is not None ) or ( self._prefix is not None ):
            raise RuntimeError( "This should never happen." )

        _dict = self._data if _dict is None else _dict

        for key, val in _dict.items():
            if isinstance( val, dict ):
                self.augment_argparse( parser, path=f'{path}{key}-', _dict=val )
            elif isinstance( val, list ):
                parser.add_argument( f'--{path}{key}', nargs="*", help=f"Default: {val}" )
            elif isinstance( val, str ):
                parser.add_argument( f'--{path}{key}', help=f"Default: {val}" )
            elif isinstance( val, bool ):
                parser.add_argument( f'--{path}{key}', action=argparse.BooleanOptionalAction, help=f"Default: {val}" )
            elif isinstance( val, numbers.Integral ):
                parser.add_argument( f'--{path}{key}', type=int, help=f"Default: {val}" )
            elif isinstance( val, numbers.Real ):
                parser.add_argument( f'--{path}{key}', type=float, help=f"Default: {val}" )
            elif val is None:
                # Not obvious what to do here, so just add a string argument
                parser.add_argument( f'--{path}{key}', help=f"Default: {val}" )
            else:
                # If this happens, then it means more code needs to be written here
                raise RuntimeError( f"Failed to add an argument for {path}{key} which is of type {type(val)}" )


    def parse_args( self, args, path='',_dict=None ):
        """Update config options from argparse arguments.

        See the docstring for the Config class for instructions on using this.

        Parameters
        ----------
          args: Namespace
            Something returned by argparser.ArgumentParser.parse_args()

          path: string
            Used internally for recursion

          _dict: dict
            Used internally for recursion

        """
        if ( self._parentconfig is not None ) or ( self._prefix is not None ):
            raise RuntimeError( "This should never happen." )

        _dict = self._data if _dict is None else _dict

        for key, val in _dict.items():
            arg = f'{path}{key}'
            if isinstance( val, dict ):
                self.parse_args( args, path=f'{arg}_', _dict=val )
            elif getattr( args, arg ) is not None:
                _dict[key] = getattr( args, arg )


    def dump_to_dict_for_params( self, omitkeys=['system'], keepkeys=None ):
        """Dump the config to a dictionary suitable for use in a Provenance params field.

        Specify one of omitkeys or keepkeys.

        Parameters
        ----------
          omitkeys: None, or list of str
            This is a list of keys to delete from the config before
            exporting it.  (The internal state of the config will not be
            affected, only what is exported.)  Be careful not to list a
            subkey of a key that's already earlier in the list, or
            you'll get errors.

            By default, the top-level key "system" is deleted, as per
            the Roman SNPIT standard that this holds all of the (but
            only the) system-specific config needed to run at a
            particular place.  (system should not include anything that
            changes the behavior of the code.)

            However, this default is a bit profligate, as it will keep
            all of the config options for all codes, not just the code
            you're running right now.  Use with thought.

          keepkeys: None, or list of str
            This is a list of keeps to keep in the export.  Currently,
            only top-level keys are supported.

        Returns
        -------
          dict
            This is a deep copy of the internal dictionary, so ideally
            you should be able to do anything you want to it without
            screwing up the internal config state.

        """

        if ( omitkeys is not None ) and ( keepkeys is not None ):
            raise ValueError( "Only specify one of omitkeys or keepkeys." )

        cfg = Config.get( clone=self )

        if omitkeys is not None:
            for kw in omitkeys:
                cfg.delete_field( kw )

        elif keepkeys is not None:
            allkeys = Config._allkeys( cfg._data )
            allkeys.reverse()
            for kw in allkeys:
                if not ( ( kw in keepkeys )
                         or any( [ Config._is_parent_field( i, kw ) for i in keepkeys ] )
                         or any( [ Config._is_parent_field( kw, i ) for i in keepkeys ] )
                        ):
                    cfg.delete_field( kw )

        else:
            raise ValueError( "Must specify either omitkeys or keepkeys." )

        return cfg._data


if __name__ == "__main__":
    Config.init()
