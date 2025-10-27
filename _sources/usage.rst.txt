=====
Usage
=====

.. contents::


--------
Overview
--------

``snappl`` has a set of utilities for the Roman SNPIT, including all the classes and functions necessary for communicating with the internal snpit database.

If you're here for the SNPIT November 2025 pipeline test, see :ref:`nov2025`.

Things you need to understand:
  * :ref:`connecting-to-the-database`
  * :ref:`config`
  * :ref:`provenance`

.. _nov2025:

----------------------------------------
November 2025 SNPIT Pipeline Test Primer
----------------------------------------

The database connection is under heavy development, and more things are showing up every day.  Right now, the following is available:

* Find image L2 images in the database
* Saving newly discovered DiaObjects to the database
* Finding DiaObjects
* Saving updated positions for DiaObjects

I *hope* that we will have saving lightcurves and finding lightcurves also available by the November test.  How much spectrum saving, and how much characterization saving, is implemented will depend on my time and what we get from those working groups.

This section describes what you need to do in order to connect to the database.

**WARNING**: because everything is under heavy development, it's possible that interfaces will change.  We will try to avoid doing this, because it's a pain when everybody has to adapt, but we're still building this, so it may be inevitable.


Choose a working environment
============================

Whatever it is, you will need to ``pip install roman-snpit-snappl``.  *This package is under heavy development, so you will want to update your install often*.  This provides the ``snappl`` modules that you are currently reading the documentation for.

**We strongly recommend you develop your code to run in a container.  The SNPIT will eventually need to run everything it does in containers.**  On your desktop or laptop, you can use Docker.  On NERSC, you can use ``podman-hpc``.  On many other HPC clusters, you can use Singularity.

**WARNING:** The snpit environment does not currently work on ARM architecture machines (because of issues with Galsim and fftw).  This means that if you're on a Mac, you're SOL.  If you're on a Linux machine, do ``uname -a`` and look towards the end of the output to see if you're on ``x86_64`` or ARM.  We hope to resolve this eventually.  For now, as much as possible run on ``x86_64`` machines.

The SN PIT provides a containerized environment which includes the latest version of snappl at https://github.com/Roman-Supernova-PIT/environment .  You can pull the docker image for this environment from one of:

  * ``registry.nersc.gov/m4385/rknop/roman-snpit-env:cpu``
  * ``registry.nersc.gov/m4385/rknop/roman-snpit-env:cpu-dev``
  * ``registry.nersc.gov/m4385/rknop/roman-snpit-env:cuda``
  * ``registry.nersc.gov/m4385/rknop/roman-snpit-env:cuda-dev``
  * ``rknop/roman-snpit-env:cpu``
  * ``rknop/roman-snpit-env:cpu-dev``
  * ``rknop/roman-snpit-env:cuda``
  * ``rknop/roman-snpit-env:cuda-dev``

We recommend you use the ``cpu`` version, unless you need CUDA, in which case try the ``cuda`` version, but you may need the ``cuda-dev`` version (which is terribly bloated).

You can, of course, create your own containerized environment for your code to run in, but you will need to support it, and eventually you will need to deliver it for the PIT to run in production.  For that reason, we strongly recommend you start trying to use the standard SNPIT environment.  Ideally, your code should be pip installable from PyPI, and eventually your code will be included in the environment just like ``snappl`` currently is.

Creating a Config
=================

Snappl includes a :ref:`config` system, that we strongly recommend you adapt your code to use, as it interacts with some other systems you will need.  In any event, to connect to the database, you are going to need a config file.

.. _password-file:

Setting up a secure password file
---------------------------------

You will eventually need a password for connecting to the database.  **Make sure never to commit passwords to github archives.**  You also don't want them sitting around in world-readable files.  While there are better solutions, a decent compromise between usability and security is to do the following on any system you run:

  * Under your home directory, create a secrets directory::

      cd
      mkdir secrets

  * Make sure the secrets directory is not world-readable::

      chmod 710 secrets

  * Create a file in that secrets directory named ``roman_snpit_ou2024_nov_ou2024nov`` that has one line holding the password for database access.  (We will give you this password if you need it.)

You will then either point directly from this file (if you are working on the host system) in a configuration variable, or you will bind-mount your secrets directory to ``/secrets`` (if you're working in a container).

The minimal config file
-----------------------

You will need to set an environment variable ``SNPIT_CONFIG`` that points to a yaml configuration file.

This is the minimal config file to connect to the database for November 2025; save it to a file named ``roman_snpit_ou2024_nov_config.yaml`` (or anything else, but remember what you save it to)::

  destructive_appends:
    - snpit_ou2024_nersc.yaml

  system:
    db:
      url: https://c3-sn.lbl.gov/roman_snpit_nov2025
      username: ou2024nov
      password: null
      passwordfile: /secrets/roman_snpit_ou2024_nov_ou2024nov

Please resist the temptation to put the password in the ``password:`` field, even though it's hanging out there enticing you.  Once somebody commits that password to a git archive, our database can now be accessed by anybody.  Once we realize a password has been leaked to a git archive, we'll need to change the password, which will be a hassle for everybody.  (We do use this field sometimes in our test suite, where the user is ``test`` and the password is ``test_password``, and because it's never a live accessible database, we don't care.)  The value of ``passwordfile`` assumes that you're working inside a container; if not, replace it with the full path to where you created the password file (see :ref:`password-file`).

This config file includes the file `snpit_ou2024_nersc.yaml <https://github.com/Roman-Supernova-PIT/environment/blob/main/snpit_ou2024_nersc.yaml>`_.  Save that file in the same directory as where you are writing your config file.  This assumes you're *not* working in a container, but are working directly on NERSC in a python venv where you've ``pip`` installed ``snappl``.  If you're working in a container, then edit the line after ``destructive_appends:`` to read ``- snpit_ou2024_container.yaml``; download that file from `here <https://github.com/Roman-Supernova-PIT/environment/blob/main/snpit_ou2024_container.yaml>`_.  You will then need to make sure you bind-mount the right directories to the right places in the container.  Ask Rob for help if you're trying to figure out how to do this.  Exactly what the directories are will depend on what system you're on.

You may well want to include other things in the config; please see :ref:`config` below.


Finding Images
==============

The images we will be using for the test run are all available in the database.  See the docstring on ``snappl.imagecollection.ImageCollection`` and ``snappl.imagecollection.ImageCollection.find_images`` for detailed documentation.  Briefly, you first need to get yourself an image collection::

  from snappl.dbclient import SNPITDBClient
  from snappl.imagecollection import ImageCollection

  dbclient = SNPITDBClient()
  imcol = ImageCollection.get_collection( provenance_tag='ou2024', process='load_ou2024_image',
                                          dbclient=dbclient )

See :ref:`provenance` below to understand what ``provenance_tag`` and ``process`` is.  We will try to keep this documentation updated with a list of :ref:`nov2025-provtags`.

With your image collection in hand, you can find images.  If, for instance, you wanted to find all images that included the coordinates RA=7.5510934°, dec=-44.8071811°, you could run::

  images = imcol.find_images( ra=7.5510934, dec=-44.8071811, dbclient=dbclient )

That will return a list of ``snappl.image.Image`` objects.  You can read the docstring for that class, but most important is probably the ``path`` attribute that tells you where to find the FITS file.  (For this test, we are still using OpenUniverse 2024 FITS Images.  Eventually we'll be working with ASDF images.)  However, instead of reading the FITS file directly, we recommend working working with the methods Image class, as it has interfaces that will remain the same whether you're reading FITS or ASDF files.  For example, if you've used a good enough config file that snappl knows where to look for data, you can get access to the data array with::

  first_image = images[0]
  image_data = first_image.data

(This is a little bit scary, as you can eat up memory using the easiest interfaces.  If you're reading multiple images at once, think about that.  You can *try* calling ``first_image.free()``, but that's not fully supported for all image types.  If you want to manage memory yourself, you can call ``first_image.get_data()`` with ``cache=False``; see the docstring on ``snappl.image.Image.get_data`` for more information.)

If you wanted to get a list of all 4500 images in the database, you could just run::

  images = imcol.find_images( dbclient=dbclient )

However, we recommend against that.  While 4500 is perhaps not an overwhelming number of images, eventually the number of images is going to be huge, and you aren't going to want to pull them down all at once.  (Not only does this give you more than is reasonable to work with, but you will also be using a lot of bandwidth from the database server to pull all that information down.  The database server does *not* give you the full images, just metadata, but a million rows of a kilobyte of metadata is already a gigabyte.)

Finding Objects
===============

There is also an interface that lets you find objects.  For instance, if you want to find all objects within 100 arcseconds of a given location, you could run::

  from snappl.diaobject import DiaObject

  objs = DiaObject.find_objects( provenance_tag=TAG, process=PROCESS,
                                 ra=7.5510934, dec=-44.8071811, radius=100.,
                                 dbclient=dbclient )

Here, you can use ``ou2024`` for ``TAG`` and ``load_ou2024_diaobject`` for ``PROCESS`` to get the objects uploaded from the OpenUniverse 2024 truth tables.  However, you may instead want to use a different provenance tag and process to get objects discovered with Sidecar; see :ref:`nov2025-provtags` below.  Also, look at the docstring on ``snappl.diaobject.DiaObject.find_objects`` for more information.

Getting Better Object Positions
===============================

``DiaObject.find_objects`` will return a list of ``DiaObject`` objects, and these include properties ``ra`` and ``dec``.  **However, the positions in the DiaObject object should be viewed as approximate.**  They will be the position it had when the object was first discovered.  For objects loaded from truth tables, they will be perfect, but of course we won't have truth tables for the real survey.  Often, the first discovery will be a relatively low S/N point, and much better positions can be determined; doing so will be one of the jobs of ``phrosty``.

To get an improved position for an object, assume you have the object in the variable ``diaobj``.  You can then call::

  position = diaobj.get_position( provenance_tag=TAG, process=PROCESS, dbclient=dbclient )

See :ref:`nov2025-provtags` below to figure out what ``TAG`` and ``PROCESS`` should be.  You will get back a dictionary with keys:

  * ``id``
  * ``diaobject_id``
  * ``provenance_id``
  * ``ra``
  * ``dec``
  * ``ra_err``
  * ``dec_err``
  * ``ra_dec_covar``
  * ``calculated_at``

**Warning**: the fields ``ra_err``, ``dec_err``, and ``ra_dec_covar`` may be ``None``; this will be the case, for instance, for object positions that were loaded from truth tables rather than determined by software.

**Important**: if you use an updated DiaObject position, then the provenance of that position should be one of your upstream provenances; see :ref:`nov2025-making-prov`.


Reading Lightcurves
===================

To read a lightcurve, you need three or four things:

  * The ``diaobject_id`` of the object whose lightcurve you want
  * The ``provenance_tag`` of the provenance you want to get lightcurves from
  * The ``process`` to go with the provenance tag
  * (Optional) The ``band`` of the lightcurve

The ``provenance_tag`` and ``process`` will be given to you through our fake orchestration process, and may possibly be found in :ref:`nov2025-provtags`.  The ``diaobject_id`` will be given to you through the fake orchestration process.

To get the lightcurves::

  from snappl.lightcurve import Lightcurve

  ltcvs = Lightcurve.find_lightcurves( <diaobject_id>, provenance_tag=<tag>, process=<proc>, dbclient=dbclient )

That will return a list of lightcurves.  If you also specify ``band=<band>``, that will be a 1-element list with the lightcurve just for that band.  (Or a 0-element list if it's not found.)

Each element of the list will be a ``Lightcurve`` object.  You can find the actual lightcurve data in the ``.lightcurve`` property as an astropy QTable.  You can find the metadata dictionary either in the ``.lightcurve.meta`` or in the ``.meta`` property (though the latter will intially be ``None`` until you access the ``.lightcurve`` property).  Guaranteed metadata can be found in the `lightcurve schema specification on the PIT wiki <https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve>`_.  You should probably ignore the ``filepath`` in the metadata, because ``snappl`` has already read the file for you (and put it in the ``.lightcurve`` property).


.. _nov2025-making-prov:

Making Provenances
==================

Before you save anything to the database, you need to make a :ref:`provenance` for it.  For example, consider the difference imaging lightcurve package ``phrosty``.  It will need to have a diaobject (let's assume it's in the variable ``obj``), and it will need to have a list of images (let's assume they're in the variable ``images``; we'll leave aside details of template vs. science images for now).  Let's assume ``phrosty`` is using the :ref:`config` system in ``snappl``, and has put all of its configuration under ``photometry.phrosty``.  (There are details here you must be careful about; things like paths on your current system should *not* go under ``photometry.phrosty``, but should go somewhere underneath ``system.``.  The current object and list of images you're working on should not be in the configuration, but should just be passed via command-line parameters.  The idea is that the configuration has all of, but only, the things that are the same for a large number of runs on a large number of input files which guarantee (as much as possible) the same output files.)

phrosty could then determine its own provenance with::

  from snappl.config import Config
  from snappl.provenance import Provenance

  objprov = Provenance.get_by_id( obj.provenance_id, dbclient=dbclient )
  improv = Provenance.get_by_id( images[0].provenance_id, dbclient=dbclient )
  phrostyprov = Provenance( process='phrosty', major=MAJOR, minor=MINOR,
                            upstreams=[ objprov, improv ],
                            params=Config.get(), omitkeys=None, keepkeys=[ 'photometry.phrosty' ] )

See :ref:`provenance` below for more details about what all of this means.  Here, ``MAJOR`` and ``MINOR`` are the first two parts of the `semantic version <https://semver.org/>`_ of phrosty.

We recommend that phrosty put in its output files, somewhere, in addition to what's obvious:

  * The ``provenance_id`` for phrosty (obtained from ``phrostyprov.id``).
  * The configuration parameters for phrosty (obtained from ``phrostprov.params`` — a dictionary).

(If you're very anal, you may want to save a gigantic dictionary structure including everything from ``phrostyprov`` and everything from all of the upstream provenances, and the upstreams of the upstreams, etc.)

**NOTE**: provenance can also store environment and environment version, but we don't have that fully defined yet.

Before saving anything to the database, you will need to make sure that the provenance has been saved to the database.  If you are sure that you've saved this same Provenance before, you can skip this step, but at some point you will need to::

  phrostyprov.save_to_db( tag=PROVENANCE_TAG, dbclient=dbclient )

where ``PROVENANCE_TAG`` is a string; see :ref:`nov2025-provtags` below for a list of what we plan to use.

Saving DiaObjects
=================

This is mostly for Sidecar.  If it's found an object and wants to save it, and if it's obtained a Provenance (including the Provenance of the images it was searching as an upstream) in ``sidecarprov``, then it can call::

  import uuid

  diaobj = DiaObject( id=uuid.uuid4(), provenance_id=sidecarprov.id,
                      ra=RA, dec=DEC, mjd_discovery=MJD, dbclient=dbclient )
  diaobj.save_object( dbclient=None )

Read the docstrings on the relevant functions for more details.  There is additional information that could be included if available.


Saving DiaObject Positions
==========================

If you have an improved position for a DiaObject ``diaobj`` and you want to save it to the database, first you need to make a Provenance (see above) for this position; assume that's in ``diaobj_pos_prov``.  You would then do::

  diaobj.save_updated_position( position_provenance=diaobj_pos_prov, ra=RA, dec=DEC,
                                ra_err=RA_ERR, dec_err=DEC_ERR, ra_dec_covar=RA_DEC_COVAR,
                                dbclient=dbclient )

This will (I believe) return a dictionary that's the same as what you'd get back from ``diaobj.get_position``.


Saving Lightcurves
==================

Lightcurves saved to the database are for only a single band.  If you have a multiband lightcurve, from the point of view of the database that's several different lightcurves.

To write a Lightcurve, first create a ``Lightcurve`` object::

  from snappl.lightcurve import Lightcurve

  ltcv = Lightcurve( data=<data>, meta=<meta> )

where ``<meta>`` is a dictionary with metadata, and ``<data>`` is one of an astropy Table, a pandas DataFrame, or a dictionary of lists.  On the `lightcurve schema specification on the PIT wiki <https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve>`_ you can find the mandatory fields in the metadata dictionary; it's allowed to have additional ones as well.  Likewise, there you can find the mandatory columns (and the order of those columns) in the data array.  You may also have additional columns in that data array.

In order to create a lightcurve, you will need to make a provenance for it; see :ref:`nov2025-making-prov`.  Make sure to include the ``diaobject position`` provenance as an upstream provenance if you used a position other than the cheesy approximate one that comes with the ``DiaObject``.

Once you have your lightcurve object, do two things::

  ltcv.write()
  ltcv.save_to_db( dbclient=dbclient )

The first one writes the actual file; it will write it in the standard location, and will populate the ``.filepath`` property with the location of the file *relative to the configured base directory for lightcurves* (which is in config option ``system.paths.lightcurves``).  The second call saves a record to the database with information about your lightcurve.

.. _nov2025-provtags:

Provenance Tags We Will Use In November 2025
============================================

TODO

.. _connecting-to-the-database:

--------------------------
Connecting to the Database
--------------------------

To connect to the database, you need three things.  First, you have to know the url of the web API front-end to the database.  You must also have a username and a password for that web API.  (NOTE: the config system is likely to change in the future, so exactly how this works may change.)  If you're using :ref:`test_env`, then the test fixture ``dbclient`` configures a user with username ``test`` and password ``test_password``, and in that environment the url of the web API is ``https://webserver:8080/``.

You configure all of these things by setting the ``system.db.url``, ``system.db.username``, and either ``system.db.password`` or ``system.db.password_file`` in the configuration yaml files.  (See :ref:`config` below.)  For example, see the default `snpit_system_config.yaml <https://github.com/Roman-Supernova-PIT/environment/blob/main/snpit_system_config.yaml>`_ in the Roman SNPIT environment.  *Do not save passwords to any git archive, and do not leave them sitting about in insecure places.*  Of course, having to type it all the time is a pain.  A reasonable compromise is to have a ``secrets`` directory under your home directory **that is not world-readable** (``chown 700 secrets``).  Then you can create files in there.  Put your password in a file, and set the location of that file in the ``system.db.password_file`` config.  (Make ``system.db.password`` to be ``null`` so the password file will be used.)  If you're using a docker container, of course you'll need to bind-mount your secrets directory.

Once you've configured these things, you should be able to connect to the database.  You can get a connection object with::

  from snappl.dbclient import SNPITDBClient

  dbclient = SNPITDBClient()

Thereafter, you can pass this ``dbclient`` as an optional argument to any ``snappl`` function that accesses the database.  (Lots of the examples below do not explicitly include this argument, but you could add it to them.)  Most of the functions will create their own ``dbclient`` using the config info as necessary.  However, you are logged in when you first create the object, so it's inefficient if every time you call a function it has to log you in (or, at least, verify that you're logged in).  If you make a ``dbclient`` and then are careful to pass as a keyword argument to any function that accepts it, you avoid this inefficiency.


.. _config:

------
Config
------

`snappl` includes a config system whereby configuration files can be stored in yaml files.  It has the ability to include other yaml files, and to override any of the config values on the command line, if properly used.

The Default Confg
=================

You can find an example/default config for the Roman SNPIT in two files in the `environment` github repo:

  * `default_snpit_config.yaml <https://github.com/Roman-Supernova-PIT/environment/blob/main/default_snpit_config.yaml>`_
  * `snpit_system_config.yaml <https://github.com/Roman-Supernova-PIT/environment/blob/main/snpit_system_config.yaml>`_

Notice that the first one includes the second one.  In the standard Roman SNPIT docker image, these two files are present in the root directory (``/``).

Ideally, all config for every SNPIT application will be in this default config file, so we can all use the same config and be sure we know what we're doing.  Of course, that's far too cumbersome for development, so during development you will want to make your own config file with just the things you need in it.

By convention, everything underneath the ``system`` top level key are the things that you might have to change when moving from one cluster to another cluster, but that don't change the behavior of the code.  This includes paths for where to find things, configurations as to where the database is, login credentials, and the like.  Everything that is _not_ under ``system`` should be things that define the behavior of your code.  These are the things that are the same every you run on different inputs.  It should _not_ include things like the specific images or diaobjects you're currently working on.  Ideally, everything that's _not_ in system, if it stays the same, will give the same outputs on the same inputs when run anywhere.

Using Config
============

To use config, you first have to set the environment variable ``SNIPIT_CONFIG`` to the location of the top-level config file.  If you're using the default config and working in the roman snpit docker image, you can do this with::

  export SNPIT_CONFIG=/default_snpit_config.yaml

Then, in your code, to get access to the config, you can just run::

  from snappl.config import Config

  ...

  cfg = Config.get()
  tmpdir = Config.value( 'system.paths.temp_dir` )

``Config.get()`` gets you a config object.  Then, just call that object's ``value`` method to get the actual config values.  Separate different levels of dictionaries in the config with periods, as in the example.  (Look at ``default_snpit_config.yaml`` to see how the config file corresponds to the value in the example above.)

There are more complicated uses of Config (including reading different, custom config files, modifying the config at runtime, understanding how the config files and all the possible modes of including other files are composed).  Read the docstring on ``snappl.config.Config`` for more information.

Overriding Parameters on the Command Line
-----------------------------------------

At runtime, if you set things up properly, you can override some of the parameters from the config file with command-line arguments.  To accomplish this, you must be using python's ``argparse`` package.  When you're ready to parse your arguments, write the following code::

    configparser = argarse.ArgumentParser( add_help=False )
    configparser.add_argument( '-c', '--config-file', default=None,
                               help=( "Location of the .yaml config file; defaults to the value of the "
                                      "SNPIT_CONFIG environment variable." ) )
    args, leftovers = configparser.parse_known_args()

    try:
        cfg = Config.get( args.config_file, setdefault=True )
    except RuntimeError as e:
        if str(e) == 'No default config defined yet; run Config.init(configfile)':
            sys.stderr.write( "Error, no configuration file defined.\n"
                              "Either run <your application name> with -c <configfile>\n"
                              "or set the SNPIT_CONFIG environment variable.\n" )
            sys.exit(1)
        else:
            raise

    parser = argparse.ArgumentParser()
    # Put in the config_file argument, even though it will never be found, so it shows up in help
    parser.add_argument( '-c', '--config-file', help="Location of the .yaml config file" )

After that, put all of the ``parser.add_argument`` lines that you need for the command-line arguments to your code.  Then, at the bottom, after you're done with all of your ``parser.add_argument`` calls, put in the code::

  cfg.augment_argparse( parser )
  args = parser.parse_args( leftovers )
  cfg.parse_args( args )

At this point in your code, you can get access to the command line arguments you specified with the ``args`` variable as usual.  However, the running config (that you get with ``Config.get()``) will _also_ have been updated with any changes made on the command line.

If you've set your code up like this, run it with ``--help``.  You will see the help on the arguments you defined, but you will also see optional arguments for everything that is in the config file.

TODO : make it so you can only include some of the top-level keys from the config file in what gets overridden on the command line, to avoid things getting far too cluttered with irrelevant options.


.. _provenance:

----------
Provenance
----------

Everything stored in the internal Roman SNPIT database has a *Provenance* associated with it.  The purpose of Provenance is twofold:

  * It allows us to store multiple versions of the same thing in the database.  (E.g., suppose you wanted to build a lightcurve for an object using two different configurations of your photometry software.  If the database just stored "the lightcurve for this object", it wouldn't be possible to store both.  However, in this case, the two lightcurves would have different provenances, so both can be stored.)

  * It keeps track of the code and the configuration used to create the thing stored in the database.  Ideally, this includes all of the parameters (see below) for the code, in addition to the code and code version, as well as (optionally) information about the environment in which the code should be run, such that we could reproduce the output files by running the same code with the same configuration again.

A provenance is defined by:

  * The ``process`` : this is usually the name of the code that produced the thing saved to the database.
  * The ``major`` and ``minor`` version of the process; Roman SNPIT code should use `semantic versioning <https://semver.org>`_.
  * ``params``, The parameters of the process (see below)
  * Optionally: the ``environment``, and ``env_major`` and ``env_minor``, the major and minor versions of the environment.  (By default, these three are all None.)
  * ``upstreams``, the immediate upstream provenances (see below).

An id is generated from the provenance based on a hash of all the information in the provenance, available in the ``id`` property of a Provenance object.  This id is a ``UUID`` (sort of), and will be something ugly like ``f76f39a2-edcf-4e31-ba6b-e3d4335cc972``.  Crucially, every time you create a provenance with all the same information, you will always get exactly the same id.


.. _provenance_tags:

Provenance Tags
===============

Provenances hold all the necessary information, and as such are cumbersome.  Provenance IDs are 128-bit numbers, and are not very human readable.  For this reason, we have *provenance tags*, which are human readable, and also allow us to collect together the provenances of a bunch of different processes into a coherent set of data products.

A provenance tag is defined by a human-readable string ``tag``, and by the ``process`` (which is the same as the ``process`` of a Provenance.)  For a given (``tag``, ``process``) pair, there can only be one Provenance.  That means that you can uniquely define a Provenance by its tag and its process.

We should be careful not to create tags willy-nilly.  Ideally, we will have a small number of provenance tags in the database that correspond to sets of runs through the entire pipeline.


Getting Provenances from the Database
=====================================

If, somehow, you got your hands on a ``provenance_id`` (the ugly 128-bit number), and you want to get the full ``Provenance`` object for it, you can accomplish that with::

  from snappl.provenance import Provenance

  prov = Provenance.get_by_id( provenance_id )

You will find provenance ids in the ``provenance_id`` field of things you pulled out of the database.  For example, if you have a ``DiaObject`` object (call it ``obj``) that you got with ``DiaObject.get_object`` or ``DiaObject.find_objects``, then you can find the id of the provenance of that DiaObject in ``obj.provenance_id``.

If, instead, you know (e.g. because the user passed this on the command line) that you want to work on the objects that we have chosen to tag with the provenance tag ``realtime``, and the process ``rapid_alerts`` (for instance, these may be objects we learned about from the RAPID alert stream), then you could get the provenance with::

  prov = Provenance.get_provs_for_tag( 'realtime', 'rapid_alerts' )


.. _provenance_parameters:

Parameters
==========

The ``params`` field of a Provenance is a dictionary that should include everything necessary for the specified version of your code to produce the same output on the same input.  It should *not* include things like input filenames.  The idea is that the *same* Provenance will apply to everything that is part of a given run.  Only when you are changing the configuration, or when you are getting input files from an earlier part of the pipeline, should the Provenance change.

If you are using the :ref:`config` system, and you've put all of these parameters (but no system-specific, like base paths, and no input files) in the config ``yaml`` file, then you can get a suitable ``params`` with::

  cfg = Config.get()
  params = cfg.dump_to_dict_for_params( keepkeys=[ 'photometry.phrosty' ], omitkeys=None )

The list in ``keepkeys`` are the keys (including the full substructure below that key) from the config that you want to include in the dictionary.  This allows you to select out the parts of the config that are relevant to your code.  ``system`` and anything starting with ``system.`` should never be in ``keepkeys``.

.. _provenance_upstreams:

Upstreams
=========

The upstream provenances are the ones that created the input files you use.  For example, campari has three basic types of inputs: a *diaobject*, the supernova it's running on; a *diaobject_position*, an updated position of the object; and *images*, the images it's fitting its model to.  Thus, it would have three upstream provenances, one for each of these things.

It can figure out these upstreams by just looking at the ``provenance_id`` field of the objects its using.  Again, for example, campari will have (somehow) obtained a ``snappl.diaobject.DiaObject`` object; call that ``diaobj``.  It can get the diaobject provenance by just looking at ``diaobj.provenance_id``.  (To actually get the full Provenance object from the id, run ``snappl.provenance.Provenance.get_by_id( provenance_id )``.)

Upstreams is part of the provenance because even if you run your code with all the same parameters, if you're taking input files that were from a differently configured process earlier in the pipeline, you expect different outputs.  Upstreams basically specify which sorts of input files are valid for this provenance.


Creating a Provenance
=====================

Just create a provenance with::

  from snappl.provenance import Provenance

  prov = Provenance( process, major, minor, params=<params>, upstreams=<upstreams> )

In this call, ``process`` is a string, ``major`` and ``minor`` are integers, ``params`` is a dictionary (see :ref:`provenance_parameters`), and ``upstreams`` is a list of ``Provenance`` objects (see :ref:`provenance_upstreams`).

If this is a totally new Provenance— you've never made it before— then save it to the database with::

  prov.save_to_db( tag=<tag> )

Here, ``<tag>`` is the :ref:`provenance tag <provenance_tags>` that you want to tag this provenance with.  If the provenance already exists in the database, or if another provenance from the same process is already tagged with this tag, you will get an error.  If the provenance you're trying to save already exists, that's fine; it won't resave it, it will just notice that it's there.  So, this is safe to call even if you aren't sure if you've saved it before or not.  If, for some reason, you really want this to be a new provenance, add ``exists=False`` to the call.  In that case, if the provenance already exists, an exception will be raised.

.. _test_env:

--------------------------------
The Roman SNPIT Test Environment
--------------------------------

(This is currently a bit of a mess, and I haven't figured out how to get this to work on Perlmutter.  However, if you're on a desktop or laptop with an ``x86_64`` architecture, then you should be able to get this running on your machine using Docker.  Read all the comments at the top of `this file in the environment repo <https://github.com/Roman-Supernova-PIT/environment/blob/main/test-docker-environment/docker-compose.yaml>`_.)
