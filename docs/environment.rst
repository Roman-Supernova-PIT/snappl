#######################
Roman SNPIT Environment
#######################

.. contents::
   :depth: 3


Overview
========

Eventually, if possible, we would like all SNPIT Code to run in the same environment.  This will simplify life for the people who are eventually going to be deploying and managing the entire pipeline.  However, if your code absolutely requires its own environment, as long as we can containerize it, we *might* be able to live with that.


Containers vs. Native
---------------------

Currently, at least on NERSC, we support two different Roman SNPIT environments: one that is just a conda environment, and the other that runs inside a container using ``podman-hpc`` (which is similar to using ``docker`` on your own system).  Because the goal is to get all code running in containers, we urge you to move to using the containerized environment on NERSC as soon as possible.


Databases, Filesystems, and Config Files
----------------------------------------

`snappl <github.com/Roman-Supernova-PIT/snappl/>`_ is the SNPIT library that handles connectivity to the database.

While the SNPIT environment itself is just a set of installed libraries, eventually most pipeline code is going to need to connect to a database and access the shared files referred to by that database.  Although we *could* have developed a system that allows the files to be shared across multiple different systems (and Rob has done that for other projects), that adds complexity that we do not believe we will need in the SNPIT.  As such, when you connect to a database, snappl assumes that you're running on a system with all the files where it expects.  Eventually, this will all be on SMDC (assuming, as it looks, that that will be the PIT's production environment.  Currently, for many of our test databases, that is on NERSC Perlmutter.

To connect to the database, you need a config file that points you to the right database and to the right places to find the files tracked by the database.


Making it so your code can run in the SNPIT Environment
-------------------------------------------------------

The most important thing is to **make your code pip installable**.

However, please also make sure that your package has its requirements listed, and that as much as possible the versions of those requirements are consistent with the versions in the `SNPIT environment <https://github.com/Roman-Supernova-PIT/environment>`_ (see the ``requirements-cpu.txt`` and ``requirements-cuda.txt`` files there), and with what's used in ``snappl`` (see the ``dependencies`` section of `snappl's pyproject.toml file <https://github.com/Roman-Supernova-PIT/snappl/blob/main/pyproject.toml>`_.

Next actually test your code in the docker environment.  Some common gotchas are going to be:

* References to absolute paths.  Any time you reference a path on your system, make it something that can be configured via an environment variable or from the command line
* (todo, what are other common problems?)

.. _database_list:

Databases currently supported
=============================

The following test/development databases are currently up and running.  (The columns are all used in other instructions below.)

..
  RST is very annoying.  Among other things, its tables superficially look clean and simple, and in practice are very annoying.  In fact, it's annoying that the world decided it needed markdown in the first place and people didn't just learn HTML.  Of course, HTML (and especially CSS) is also annoying, but less so than most markdown, at least from the point of view of making things do what you want.

.. raw:: html

  <table class="docutils align-default">
  <thead>
    <tr class="row-odd">
      <th class="head">Database</th>
      <th class="head">Secrets File</th>
      <th class="head">System</th>
      <th class="head">Launcher</th>
    </tr>
  </thead>
  <tbody>
    <tr class="row-even">
      <td>The nov2025 test database</td>
      <td><tt>roman_snpit_ou2024_nov_ou2024nov</tt></td>
      <td>NERSC</td>
      <td><tt>interactive-podman-nov2025.sh</tt></td>
    </tr>
    <tr class="row-odd">
      <td>Rob's tests</td>
      <td><tt>roman_snpit_db_rknop_dev</tt></td>
      <td>NERSC</td>
      <td><tt>interactive-podman-rknop-dev.sh</tt></td>
    </tr>
  </tbody>
  </table>



Running on NERSC
================

Using Conda
-----------

TODO


Using the Container
--------------------

There are a few steps you need to do in order to set yourself up to run on NERSC using the container.  Most of these you only have to do once, or once for each database you want to connect to, so this is not as cumbersome as it looks.

Figure out which database you want to connect to
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

See :ref:`database_list` above.

Make a temporary directory
^^^^^^^^^^^^^^^^^^^^^^^^^^

Run:

.. code-block:: console

   mkdir $PSCRATCH/snpit_temp

This directory will be used inside the container, and mounted at ``/snpit_temp``.

You only ever need to do this once.

Create a secrets directory
^^^^^^^^^^^^^^^^^^^^^^^^^^

We do not store the passwords for databases anywhere in github.  As such, there will need to be some manual intervention on your part so that the environment is able to find the password.  Although it's not perfect, we handle this by having a "secrets" directory underneath your home directory that is *not* world readable.  All NERSC admins can still read this file, but we have decided to trust them.  Create your secrets directory with:

.. code-block:: console

  cd
  mkdir secrets
  chmod 710 secrets
  setfacl -Rdm g::x,o::- secrets

You only ever need to do this once.

Create the password file for the database you wish to connect to
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Figure out two things: the name of the secrets file (see `database_list`_) and the actual password.  (For the latter, you need to talk to Rob, or whoever set up the database you're connecting to.)

Once you know these two things, create the password file with the right name in your ``secrets`` directory.  It should have one line, which is the password.  Do this however you like to do these things (text editor, whatever), or run the following on NERSC:

.. code-block:: console

  cd ~/secrets
  echo "<password>" > <passwordfile>

substituting the right filename for ``<passwordfile>`` and the right password for ``<password>``.

Verify that the password is right with:

.. code-block:: console

  cat ~/secrets/<passwordfile>

You only need to do this once for each different database you want to connect to.

Pick a directory you're going to work in
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can put this under your home directory, but probably don't want to do that, as the space you're allowed in your home directory is very limited.  Either make yourself a subdirectory on scratch under ``$SCRATCH`` (being aware that files will be purged off of that disk after a while, so make sure you've committed anything you want to keep to git), or make yourself a directory underneath ``/global/cfs/cdirs/m4385/users/<yourname>``.

In this directory, check out all the various things that you want to work on.  If you're working on photometry, you probably want to git clone the `photometry test data <https://github.com/roman-Supernova-PIT/photometry_test_data>`_.  You *might* want to clone `snappl <https://github.com/roman-Supernova-PIT/snappl>`_ (but probably don't need to, because snappl is built into the Dockerfile you'll be running.)  And, of course, make sure the directory of the code you're working on is here, and has no symlinks that point outside of itself.

Run the container
^^^^^^^^^^^^^^^^^

Make sure you are in the directory you picked to work in, and do:

.. code-block:: console

  bash /global/cfs/cdirs/m4385/env/<launcher>

where ``<launcher>`` is the "NERSC Launcher" from the :ref:`database_list`.

**NOTE**: if you need Cuda inside the container (e.g. if you're running sidecar or phrosty), you should instead run:

.. code-block:: console

  WHICHROMANENV=cuda-dev bash /global/cfs/cdirs/m4385/env/<launcher>
  
This will give you a shell inside the container.  You can tell you're in the container because the prompt will change to something like ``root@fa872d696e6b:/home#`` (where the hex barf after the ``@`` will be different).

If you ``cd /home``, you should see all the subdirectories and files that you put in your work directory.

You can find your perlmutter scratch directory inside the container at ``/scratch`` (in case you have anything there you need).

Exit the container when done
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you're done, just ``exit`` the container.  Probably also be a good citizen and clean up after yourself with:

.. code-block:: console

  podman-hpc system prune

(It's not really a big deal, but if you don't do that, somewhere the system keeps a record of your exited container, and you probably don't need that.)

If you need your own config file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The containers come with a config file that has the database connection baked in.  If you're using the snappl config system yourself, you probably have your own config file with things in it that configure your own application.  In order to use the container config's database together with your config file, put the following lines at the top of your config ``.yaml`` file:

.. code-block:: yaml

  preloads:
    - /snpit_env/configs/${SNPIT_DEFAULT_CONFIG}

Make sure that your own config file does *not* have a ``system:`` block; if it does, then things will break.
      
Then, every time you start the container, run:

.. code-block:: console

  export SNPIT_CONFIG=<in-container path to your config file>

Now, when you run anything, snappl will connect to the database designed for the container, but will also include all of your own configuration data.


Submitting batch jobs
^^^^^^^^^^^^^^^^^^^^^

This will be more involved.  What you will need to do is copy and edit the "NERSC Launcher" script.  If you're lucky, all you'll have to do is replace ``/bin/bash`` on the last line with the command that you want to run, and edit the top to have all the necessary ``#SBATCH`` directives.  Then ``sbatch`` your copied and edited script from your work directory.


Running a Test Environment
--------------------------

TODO.  Haven't fully figured out yet how to get this working on NERSC.


Running on SMDC
===============

TODO


Running locally on your machine
===============================

Using Pip or Conda
------------------

TODO

Using the Container
-------------------

**Warning**: Currently, we are only able to build our containers for ``x86_64`` (also called ``amd64``) systems.  We have not succeeded in building our containers for ``ARM`` (also called ``arm64``) systems— which includes all Macs.  You *might* be able to run a container from a different architecture on your machine, but performance is likely to be very poor.  This means that for development, you really want to be using an ``x86_64`` Linux machine if that's at all possible.  (We do hope to get the container working for ``ARM``, but it's a thorny problem and not a high proirity.  If you want to figure out how to make it work, please do.)

TODO

Running a Test Environment
--------------------------

TODO

In the mean time, in your working directory (i.e. the directory that has subdirectories which are checkouts of the other git archives you're working on), clone the `roman SNPIT environment repo <https://github.com/Roman-Supernova-PIT/environment>`_:

.. code-block:: console

  git clone https://github.com/Roman-Supernova-PIT/environment.git

(If you know what you're doing, you probably want to clone the ``git@github.com:`` version instead of the ``https:`` version.)

* cd into ``environment/test-docker-environment``

* Build the necessary docker files with:

  .. code-block:: console

    docker compose build

  As above, this will probably not work if you aren't on an ``x86_64`` Linux machine.

* Start the test environment with:

  .. code-block:: console

    docker compose up -d webserver shell

* Connect into the test environment with:

  .. code-block:: console
    
    docker compose exec -it shell /bin/bash

* Try to do things.

* When you are done, ``exit`` out of the test environment, and bring it all down with:

  .. code-block:: console

    docker compose down -v
    
For example, if you want to run the snappl tests on a branch of snappl, make sure you've checked out both the `snappl repo <https://github.com/Roman-Supernova-PIT/snappl>`_ and the `photometry test data <https://github.com/roman-Supernova-PIT/photometry_test_data>`_ in the same directory as where you checked out the environment repo.  Make sure you've checked out whichever branch of snappl it is you want to run the tests on.  Then, once you're inside the container, try:

.. code-block:: console

  cd /home/snappl
  pip install -e .[test]
  cd snappl/tests
  pytest -v


