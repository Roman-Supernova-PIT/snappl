.. _config-docs:
.. contents::

=================
The Config System
=================

snappl includes a config system based on yaml files that we hope will be used by all Roman SNPIT codes.

Justification
=============

Why a universal config system?  This does impose upon all the various groups writing software, as it requires all of them to use the same mechanism for configuration.  It requires them to learn it, and to imlement it instead of doing things how they usually like to do things.

There are two primary reasons.

First, eventually, all of the code in the SN PIT will need to be run in production by *somebody*, and we cannot assume that that somebody will be a group that has representatives from all the various working groups of the PIT.  To reduce the cognitive load on the people setting up the actual production running pipelines, plus to reduce the likelihood of errors and inconsistencies, it is helpful to have a single mechansim used to configure all of the codes that will be run.  That way, the production pipeline managers won't have to learn the ideosyncracies of every programmer's individual preference for config systems, command-line options, etc.

Second, there will be some configuration that is going to be shared between many if not all codes.  One example might be database access; if we have a central internal PIT database for coordinating processes and data products, we will need to configure access to that database (host locations, users, passwords, etc.).  By using a shared config system, that only needs to be configured *once*, and then every individual code's config can include the database config, and then we can be sure everybody's using the same thing.

Ultimately, we hope to have a single master config file that configures *all* of the SN PIT codes.  (In practice, this may not truly be a single file, but may include other files, as the config system allows for that.  However, from the point of view of the code that uses it, every code would load the same config file and would have access to all of the config variables.)


.. _config-quickstart-example:

Quickstart Example
==================

At the moment, we do not have any global configs for the SN PIT, so you can create your own config files.  Create a config file ``demo.yaml`` *somewhere* that has contents::

  option1: test1
  many_options:
    sub1: subtest1
    sub2: subtest2
  three_numbers: [1,2,3]

Next, create a file ``demo.py`` that has contents::

  from snappl.config import Config

  cfg = Config.get()

  print( f"option1 is {cfg.value('option1')}" )
  print( f"sub option 1 of many options is {cfg.value('many_options.sub1')}" )
  print( f"three numbers are {cfg.value('three_numbers')}" )
  print( f"The second number is {cfg.value('three_numbers.1')}" )
  
Make sure that you have :ref:`installed snappl <installation-docs>`.  Then run::

  SNAPPL_CONFIG=$PWD/demo.yaml python demo.py

.. _config-quickstart-example-command-line:

Quickstart Example — comand line overriding
-------------------------------------------

Edit your ``demo.py`` file from the previous example so that it has contents::

  import argparse

  from snappl.config import Config

  cfg = Config.get()

  parser = argparse.ArgumentParser()
  cfg.augment_argparse( parser )
  args = parser.parse_args( arglist )
  cfg.parse_args( args )

  print( f"option1 is {cfg.value('option1')}" )
  print( f"sub option 1 of many options is {cfg.value('many_options.sub1')}" )
  print( f"three numbers are {cfg.value('three_numbers')}" )
  print( f"The second number is {cfg.value('three_numbers.1')}" )

Now try running each of::

  SNAPPL_CONFIG=$PWD/demo.yaml python demo.py
  SNAPPL_CONFIG=$PWD/demo.yaml python demo.py --option1 hello --three_numbers 4 5 6 7 8
  SNAPPL_CONFIG=$PWD/demo.yaml python demo.py --help


Getting values from config files
================================

This section assumes a config file already exists and you just want to get the config options from that config file.

.. _getting-config-object:

Getting a config object
-----------------------

First, you need to import ``snappl.config`` and get yourself a ``Config`` object.  Do **not** directly instantate a ``Config`` object.  Instead, run::

  from snappl.config import Config
  cfg = Config.get()

If you're enviornment isn't set up right, then this will raise an exeption.  ``Config`` tries to read the ``.yaml`` file specified by environment variable ``SNAPPL_CONFIG``; make sure you have that environment varaible pointing at the right file.  You can also do::

  cfg = Config.get( "<filename>" )

where ``<filename>`` is the name of the ``.yaml`` file you want to read.  However, we strongly recommend against doing this.  Hardcoding filenames into your code will make it less portable, and may later cause issues when people believe they are pointing at a new config file by changing their ``SNAPPL_CONFIG`` environment variable.

Reading config values
---------------------

Once you have a Config object (``cfg`` in this example), you can get config values by just calling::

  result = cfg.value('<fieldspec>')

``<fieldspec>`` specifies the configuration option ("field") you want.  Configurations may be hierarchical; that is, an field may itself have sub options.  In Python terms, the top-level config object is (bascially) a dictionary, and the values of dictionary entries may themselves be dictionaries.  If you want to just get a top-level field, then just give the name of that field.  If you want to get a sub-field of a top-level field, then ``<fieldspec>`` should be ``field.subfield``.  For example, look at the ``demo.yaml`` file in :ref:`config-quickstart-example`.  If you get a ``Config`` object from this file, then ``cfg.value('option1')`` would return just ``test1``.  Likewise, ``cfg.value('many_options.sub1)`` would return ``subtest``.  If for some reason you want to get an sub-field tree, you can get a higher level config value.  In this example, if you ran ``cfg.value('many_options`)``, you would get back the dictionary ``{'sub1':'subtest1', 'sub2':'subtest2'}``.


Creating config files
=====================

TDB.  In the mean time, look at the extensive docstring on `snappl/config.py::Config`.
