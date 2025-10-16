=====
Usage
=====

.. contents::


--------
Overview
--------

``snappl`` has a set of utilities for the Roman SNPIT, including all the classes and functions necessary for communicating with the internal snpit database.

Things you need to understand:
  * :ref:`connecting-to-the-database`
  * :ref:`config`
  * :ref:`provenance`


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
                                      "SNPIT_CONFIG environment varaible." ) )
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

Upstreams is part of the provenance because even if you run your code with all the same parameters, if you're taking input files that were from a differently configured process earlier in the pipline, you expect different outputs.  Upstreams basically specify which sorts of input files are valid for this provenance.


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
