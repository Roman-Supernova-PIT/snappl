#######################
Roman SNPIT Environment
#######################

.. contents::
   :depth: 2


Overview
========

Eventually, if possible, we would like all SNPIT Code to run in the same environment.  This will simplify life for the people who are eventually going to be deploying and managing the entire pipeline.  However, if your code absolutely requires its own environment, as long as we can containerize it, we *might* be able to live with that.


Containers vs. Native
---------------------

Currently, at least on NERSC, we support two different Roman SNPIT environments: one that is just a conda environment, and the other that runs inside a container using ``podman-hpc`` (which is similar to using ``docker`` on your own system).  


Databases, Filesystems, and Config Files
----------------------------------------

`snappl <github.com/Roman-Supernova-PIT/snappl/>`_ is the SNPIT library that handles connectivity to the database.

While the SNPIT environment itself is just a set of installed libraries, eventually most pipeline code is going to need to connect to a database and access the shared files referred to by that database.  Although we *could* have developed a system that allows the files to be shared across multiple different systems (and Rob has done that for other projects), that adds complexity that we do not believe we will need in the SNPIT.  As such, when you connect to a database, snappl assumes that you're running on a system with all the files where it expects.  Eventually, this will all be on SMDE (assuming, as it looks, that that will be the PIT's production environment.  Currently, for many of our test databases, that is on NERSC Perlmutter.

To connect to the database, you need a config file that points you to the right database and to the right places to find the files tracked by the database.


Databases currently supported
-----------------------------

The following test/development databases are currently up and running.  (The "Secrets File" and "NERSC Launhcer" are used in further instructions below.):

+---------------------------------------+----------------------------------------+-----------------------------------+
| Database                              | Secrets File                           | NERSC Launcher                    |
+=======================================+======================================= +===================================+
| The nov2025 test database             | ``roman_snpit_ou2024_nov_ou2024nov``   | ``interactive-podman-nov2025.sh`` |
+---------------------------------------+----------------------------------------+-----------------------------------+

Making it so your code can run in the SNPIT Environment
-------------------------------------------------------

The most important thing is to **make your code pip installable**.

However, please also make sure that your package has its requirements listed, and that as much as possible the versions of those requirements are consistent with the versions in the `SNPIT environment <https://github.com/Roman-Supernova-PIT/environment>`_ (see the ``requirements-cpu.txt`` and ``requirements-cuda.txt`` files there), and with what's used in ``snappl`` (see the ``dependencies`` section of `snappl's pyproject.toml file <https://github.com/Roman-Supernova-PIT/snappl/blob/main/pyproject.toml>`_.

Next actually test your code in the docker environment.  Some common gotchas are going to be:

* References to absolute paths.  Any time you reference a path on your system, make it something that can be configured via an environment variable or from the command line
* (todo, what are other common problems?)

.. _database_list:


Running on NERSC
================

Using Conda
-----------

TODO


Using the Container
--------------------

There are a few steps you need to do in order to set yourself up to run on NERSC using the container.  Most of these you only have to do once, or once for each database you want to connect to, so this is not as cumbersome as it lookis.

Figure out which database you want to connect to
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

See :ref:`database_list` above.


Create a secrets directory
^^^^^^^^^^^^^^^^^^^^^^^^^^

We do not store the passwords for databases anywhere in github.  As such, there will need to be some manual intervention on your part so that the environment is able to find the password.  Although it's not perfect, we handle this by having a "secrets" directory underneath your home directory that is *not* world readable.  All NERSC admins can still read this file, but we have decided to trust them.  Create your secrets directory with::

  cd
  mkdir secrets
  chmod 710 secrets
  setfacl -Rdm g::x,o::- secrets

You only never need to do this once.

Create the password file for the database you wish to connect to
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Figure out two things: the name of the secrets file (see `database_list`_) and the actual password.  (For the latter, you need to talk to Rob, or whoever set up the database you're connecting to.)

Once you know these two things, create the password file with the right name in your ``secrets`` directory.  It should have one line, which is the password.  Do this however you like to do these things (text editor, whatever), or run the following on NERSC:

  cd ~/secrets
  cat > <passwordfile>
  <password>

substituting the right filename for ``<passwordfile>`` and the right password for ``<password>``.  Note that you will *not* get a prompt back after typing ``cat > <passwordfile>``; the system is waiting for you to type the contents that will be written into that file.  After pasting the password, hit ``CTRL-D``.

Verify that the password is right with::

  cat ~/secrets/<passwordfile>

You only need to do this once for each different database you want to connect to.

Pick a directory you're going to work in
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can put this under your homedirectory, but probably don't want to do that, as the space you're allowed in your home directory is very limited.  Either make yourself a subdirectory on scratch under ``$SCRATCH`` (being aware that files will be purged off of that disk after a while, so make sure you've committed anything you want to keep to git), or make yourself a directory underneath ``/global/cfs/cdirs/m4385/users/<yourname>``.

In this directory, check out all the various things that you want to work on.  If you're working on photometry, you probably want to git clone the `photometry test data <https://github.com/roman-Supernova-PIT/photometry_test_data>`_.  You *might* want to clone `snappl <https://github.com/roman-Supernova-PIT/snappl>`_ (but probably don't need to, because snappl is built into the Dockerfile you'll be running.)  And, of course, make sure the directory of the code you're working on is here, and has no symlinks that point outside of itself.

Run the container
^^^^^^^^^^^^^^^^^

Make sure you are in the directory you picked to work in, and do::

  bash /global/cfs/cdirs/m4385/env/<launcher>

where ``<launcher>`` is the "NERSC Launcher" from the :ref:`database_list`.

This will give you a shell inside the container.  You can tell you're in the container because the prompt will change to something like ``root@fa872d696e6b:/home#`` (where the hex barf after the ``@`` will be different).

If you ``cd /home``, you should see all the subdirectories and files that you put in your work directory.

When you're done, just ``exit`` the container.  Probably also be a good citizen and clean up after yourself with::

  podman-hpc system prune

(It's not really a big deal, but if you don't do that, somewhere the system keeps a record of your exited container, and you probably don't need that.)

Submitting bastch jobs
^^^^^^^^^^^^^^^^^^^^^^

This will be more involved.  What you will need to do is copy and edit the "NERSC Launcher" script.  If you're lucky, all you'll have to do is replace ``/bin/bash`` on the last line with the command that you want to run, and edit the top to have all the necessary ``#SBATCH`` directives.  Then ``sbatch`` your copied and edited script from your work directory.


Running a Test Environment
--------------------------

TODO.  Haven't fully figured out yet how to get this working on NERSC.


Running on SMDE
===============

TODO


Running locally on your machine
===============================

Using Pip or Conda
------------------

TODO

Using the Container
-------------------

**Warning**: Currently, we are only able to build our containers for ``x86_64`` (also called ``amd64``) systems.  We have not succeeded in building our containers for ``ARM`` (also called ``arm64``) systems— which includes all Macs.  You *might* be able to run a container from a different architecture on your machine, but performance is likely to be very poor.  This means that for development, you reall want to be using an ``x86_64`` Linux machine if that's at all possible.  (We do hope to get the container working for ``ARM``, but it's a thorny problem and not a high proirity.  If you want to figure out how to make it work, please do.)

TODO

Running a Test Environment
--------------------------

TODO

In the mean time, git clone the archive at 

  
