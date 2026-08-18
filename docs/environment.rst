#######################
Roman SNPIT Environment
#######################

.. contents::
   :depth: 3


Overview
========

Eventually, if possible, we would like all SNPIT Code to run in the same environment.  This will simplify life for the people who are eventually going to be deploying and managing the entire pipeline.  However, if your code absolutely requires its own environment, as long as we can containerize it, we *might* be able to live with that.

To update the environment, see :ref:`releasenewenv`.

Containers vs. Native
---------------------

A "containerized" environment is one you run inside a container using docker, podman-hpc, or apptainer/singularity.  For SNPIT development, We support a containerized environment on both NERSC and SMDC.  For the containerized environment, when you run it, you get the current verison of the SNPIT environment (or one of a few varieties of it).  At that point you can modify the environment with ``pip install``, though any changes you make will only persist as long as you are running the container.  (That is, when you exit the container and start a new one, you get a fresh slate, which can be an advantage.)

On SMDC, we also support a two varieties of a "native" environment, which means one that runs in a python venv.  One venv is a shared environment that you use to just run stuff.  The second is one you install yourself in your own directory, so you can install packages to it and modify it.

We also have a dockerized development environment you can run on your own system; see :ref:`running_locally`.

Databases, Filesystems, and Config Files
----------------------------------------

`snappl <github.com/Roman-Supernova-PIT/snappl/>`_ is the SNPIT library that handles connectivity to the database.

While the SNPIT environment itself is just a set of installed libraries, eventually most pipeline code is going to need to connect to a database and access the shared files referred to by that database.  Although we *could* have developed a system that allows the files to be shared across multiple different systems (and Rob has done that for other projects), that adds complexity that we do not believe we will need in the SNPIT.  As such, when you connect to a database, snappl assumes that you're running on a system with all the files where it expects.  Currently, we have test environments that are meant to run on NERSC and SMDC.

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

The following test/development databases are currently up and running.  (Columns are referenced by other instructions below.):

* **Database**: a brief description of what database this is
* **Secrets File**: The name of the :ref:`password file<env_password_file>` you must have in your secrets directory
* **System**: Which system you must be on to run with this database
* **Launcher**: The name of the script to launch the containerized version environment.  On NERSC, these are in ``/global/cfs/cdirs/m4385/env``; on SMDC, these are in ``/data/snpit/env``.
* **Config File**: The name of the config file.  On NERSC, these are in ``/global/cfs/cdirs/m4385/env/configs``; on SMDC, these are in ``/data/snpit/env/configs``.  You usually don't have to worry about it, the launcher will set this up for you.  However, you *might* need to think about this :ref:`need_own_config`.  (Follow exactly what's in that section, though, and you shouldn't need to think about it.)


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
      <th class="head">Config File</th>
    </tr>
  </thead>
  <tbody>
    <tr class="row-even">
      <td>Rick's Aug 2028 Sims on SMDC</td>
      <td><tt>roman_snpit_db_ricksim_smdc</tt></td>
      <td>SMDC</td>
      <td><tt>singrun_smdc_ricksim.sh</tt></td>
      <td><tt>smdc_ricksim_apptainer.yaml</tt></td>
    </tr>
    <tr class="row-odd">
      <td>Generic NERSC Tests</td>
      <td><tt>roman_snpit_db_rknop_dev</tt></td>
      <td>NERSC</td>
      <td><tt>interactive-podman-rknop-dev.sh</tt></td>
      <td><tt>rknop_dev_container_config.yaml</tt></td>
    </tr>
    <tr class="row-even">
      <td>NERSC OU2024</td>
      <td><tt>roman_snpit_db_ou2024</tt></td>
      <td>NERSC</td>
      <td><tt>interactive-podman-ou2024.sh</tt></td>
      <td><tt>ou2024_container_config.yaml</td></td>
    </tr>
  </tbody>
  </table>

..
    <tr class="row-even">
      <td>The nov2025 test database</td>
      <td><tt>roman_snpit_ou2024_nov_ou2024nov</tt></td>
      <td>NERSC</td>
      <td><tt>interactive-podman-nov2025.sh</tt></td>
    </tr>


.. _running_env:

Running the Environment
=======================

Getting Set Up
--------------

No matter which form of the environment you're going to run in, there are some steps you need to take in order to get set up.

.. _env_password_file:


Create a the password file
^^^^^^^^^^^^^^^^^^^^^^^^^^

You need to create a file that has the password for accessing the database.  You need to do this once for each :ref:`database list<database_list>` you want to connect to.  These passwords are not in the code anywhere, because we do not want to commit them to github archives.  Ideally, they would not sit anywhere, but it would be a pain for you to have to type them every single time you started code.  We have compromised by having everybody create a ``secrets`` directory underneath their home directory that is protected using the operating system so that nobody else can read it.  (Sysadmins on the systems *can* read them; we are choosing to trust them.)

Only once, ever, you need to make your secrets directory on a given system (SMDC or NERSC):

.. code-block:: console

  cd ~
  mkdir secrets
  chmod 700 secrets

That last command sets it so that nobody other than you can list files in the secrets directory.

Then, for each :ref:`database list<database_list>`, create the secrets file once with:

.. code-block:: console

  cd ~/secrets
  echo "<password>" > <passwordfile>
  chmod 600 <passwordfile>

where ``<password>`` is the password for the databse (ask Rob for it), and ``<passwordfile>`` is the filename that's listed in the list of :ref:`database_list`.

.. _env_rundir:

Create your ``$RUNDIR``
^^^^^^^^^^^^^^^^^^^^^^^

Pick a directory you're going to run in.  We will call it ``$RUNDIR`` in this documentation, but you do not need to define that as an environment variable.  (You might want to, but it's not required.)  This might be your home directory, or it might be somewhere else.  On NERSC, we recommend creating yourself a directory underneath ``/global/cfs/cdirs/m4385/users``; then use that directory, or further subdirectories, as your ``$RUNDIR``.

Once you're in your ``$RUNDIR``, create a subdirectory ``packages``:

.. code-block:: console

  mkdir packages

**Important** any github archives you check out (``snappl``, the code you're working on, etc.) should be checked out in the ``packages`` subdirectory!

Do system-specific setup
^^^^^^^^^^^^^^^^^^^^^^^^

There may be some additional steps for specific systems:

  * :ref:`running_on_nersc`
  * :ref:`running_on_smdc`


.. _running_and_using_env:

Running and using the Environment
---------------------------------

With ``$RUNDIR`` as your current directory, run the launcher listed in the list of :ref:`database_list` with:

.. code-block:: console

   bash <dir>/<launcher>

where ``<dir>`` is the place to find launchers on the system (``/global/cfs/cdirs/m4358/env`` on NERSC and ``/data/snpit/env`` on SMDC), and ``<launcher>`` is the right launcher script from the list of databases.


If you're using a containerized enviornment, there will be several filesystems mounted inside the container:

  * ``/home`` inside the container is ``$RUNDIR`` outside of the container.
  * ``/packages`` inside the container is ``$RUNDIR/packages`` outside of the container, but it's probably easier just to use ``/home/packages`` inside the container, which is the same thing.
  * ``/data`` inside the container points to the standard database file store directory.  You should generally, **not** store any files here.  Rather, when you call ``snappl`` functions and methods to read and write files to the directory, it will read and write files underneath this directory.
  * ``/snpit_temp`` is a temporary directory.  This directory is where your code writes files that it doesn't care if the files continue to exist after the code exits.
  * ``/dev_storage`` is a semi-temporary directory.  This is where you should write output files that would not be "in" the database, but that you want to keep (probably only for a limited period of time) after the run.  Write diagonstic files, etc. here.
  * ``/photometry_test_data`` has a checkout of a recent version of the `SNPIT photometry test data <https://github.com/roman-Supernova-PIT/photometry_test_data>`_ github archive.
  * (there will be some others)


Depending on what you're doing, after starting the environment you might want to install some of your checked-out packages.  This is definitely true if you're developing one of the packages!  Remember that for containerized environments, anything you install only lives as long as that container lives; when you exit and restart it, you have a fresh environment.

For example, to install snappl in your currently running environment, do:

.. code-block:: console

  cd packages/snappl
  pip install -e .
  cd ../../

(That last line puts you back in ``$RUNDIR``, which is ``/home`` inside the container.)  For the second line, you *might* want instead do ``pip install -e .[test]``, if you want to try to run the tests.

**We recommend that you run all your code from ``$RUNDIR``**.  This will not always be practical, but do it if you can.  Ideally, all the examples we set up will be set to run this way.


.. _snappl_config_file:

Config Files
^^^^^^^^^^^^

If you use snappl to access the database, each environment is set up to point to a config file to point to the right database for that environment.  As such, everything in the :ref:`snappl_usage` chapter should "just work".

.. _need_own_config:

If you need your own config file
""""""""""""""""""""""""""""""""

**If you need your own config file**: you have to do a few extra things.  If you're using the ``snappl`` config system to set configuration options for your own code, then you will need a ``.yaml`` config file with those options.  At the top of your config file, put the following text:

.. code-block:: yaml

  preloads:
    - ${SNPIT_DEFAULT_CONFIG}

What that will do is make sure to load the standard environment configuration with paths and database connection information.  If you do it right, you may be able to use the same config file for your own code in multiple environments (and maybe even in tests in the self-contained test environment).

**Things not to put in your own config file**: do **not** override anything that is in the ``${SNPIT_DEFAULT_CONFIG}`` file.  You should **not** have a ``system.db`` section in your own config file.  If you have a ``system.paths`` section, it should **only** be to **add** paths that are specific to your code, you should **not** replace any of the paths that are in the default config file.


.. _running_on_nersc:

Running on NERSC
================

In additon to the :ref:`standard steps for running an environment<running_env>`, there are a couple of additional steps you have to do to run on NERSC.

Make a temporary directory
--------------------------

You only have to do this once:

.. code-block:: console

  mkdir $PSCRATCH/snpit_temp

This will be available inside the container at ``/snpit_temp``.

Make a dev storage directory
----------------------------

You only have to do this ocne:

.. code-block:: console

  mkdir $PSCRATCH/dev_storage

This will be available inside the container at ``/dev_storage``.


Clean up your containers when you're done
-----------------------------------------

When you're done, just ``exit`` on the command line to leave the container.  Your command-line prompt will change back to what you usually see on NERSC.  Probably also be a good citizen and clean up after yourself with:

.. code-block:: console

  podman-hpc system prune

(It's not really a big deal, but if you don't do that, somewhere the system keeps a record of your exited container, and you probably don't need that.)

.. _nersc_batch_jobs:


Submitting batch jobs
---------------------

This will be more involved.  You have to create *two* bash scripts.  First, create the script that actually does the stuff you want to do.  We'll call it ``dothings.sh`` here, but you can name it whatever you want.  It should live in the :ref:`directory you picked to work in ($RUNDIR)<env_rundir>`.

.. code-block:: bash

   #!/bin/bash

   cd /home
   python phrosty/phrosty/be_awesome.py --solve-cosmology --identify-dark-energy --nobel-prizes=3

This script will run *inside a container* running the snpit image.  If you :ref:`use your own custom config file<need_own_config>`, then you would add a line ``export SNPIT_CONFIG=...`` early in this script.  You can do whatever other environment setup you need to do.

Next, create a second script, which we shall call ``dothings_sbatch.sh``, though again you can name it whatever you want.

.. code-block:: bash

   #!/bin/bash
   #SBATCH --qos=debug
   #SBATCH --time=00:20:00
   #SBATCH --nodes=1
   #SBATCH --constraint=cpu

   bash /global/cfs/cdirs/m4385/env/<launcher> /home/dothings.sh

Where you replace ``<launcher>`` with the Launcher from :ref:`database_list`.  You should generally *not* add any commands other than the single ``bash`` command here.  (You can if you know what you're doing.)  You will want to edit the various ``#SBATCH`` directives to go to the queue you want, to get a GPU if you need it, to increase (or decrease) the time.  You may also want additional directives about number of tasks, number of cpus, memory (if you're on the shared queue).  All of this presumes you know how to use ``sbatch``.

If you didn't name your first script ``dothings.sh``, also change that name here.

Now, you should be able to submit your job with:

.. code-block:: console

   sbatch dothings_sbatch.sh

of course replacing ``dothings_sbatch.sh`` with whatever you named your second script.

.. _running_on_smdc:

Running on SMDC
===============

**WARNING**: Before you run anything, make sure you are on a compute node. If you run things on the login node, you may crash the login node, and then no one will be able to get on SMDC until it is rebooted. You can get on a compute node, for example, with:

.. code-block:: console

  salloc -p mem-med --time=04:00:00

In addition to the :ref:`standard things you do for running the environment<running_env>`, there are a few optional things you might want to do when runnig on SMDC.

Make your own temp directory
----------------------------

By default, the environments on SMDC uses ``/dev/shm`` for the temp directory (``/snpit_temp`` inside the container for containerized environments).  This is a RAM disk.  It has limited size, *and* it eats up system memory when you use it.  But, it's really fast.  If you know that the total size of temp files you'll have written at once is small enough (i.e. it won't fill the disk, and won't use up too much memory for what your code needs), then this is a great place for it.  However, if you write enough big temp files, you need to put them somewhere else.

The *right* place to put temp files is not immediately obvious.  *If* you're on a node with local storage, then you want to put it there.  (ROB WRITE MORE.)  If you have nothing else to do, then we recommend you make a directory:

.. code-block:: console

  /mnt/roman-science-internal/snpit/users/<yourloginname>/temp

Then, when :ref:`running the environment<running_and_using_env>`, instead of just launching the environment with ``bash``, instead run:

.. code-block:: console

  SNPIT_SCRATCH=/mnt/roman-science-itnernal/sinput/users/<yourloginname>/temp bash <dir>/<launcher>

Use a different dev storage directory
-------------------------------------

By default, the environments on SMDC will put the "dev storage" directory (the thing that is at ``/dev_storage`` inside the container, and that the ``system.paths.dev_storage`` config value points at, is at:

.. code-block:: console

  /mnt/roman-science-internal/snpit/users/<yourloginname>/dev_storage

This is probably fine.  If, for some reason you want it elsewhere, then make that directory, and then when you :ref:`run the environment<running_and_using_env>`, instead of just launching the environment with ``bash``, instead run:

.. code-block:: console

  DEV_STORAGE=/path/to/your/dev/storage bash <dir>/<launcher>

If you have changed *both* the temp and dev storage directories, set both env vars:

  DEV_STORAGE=/path/to/your/dev/storage SNPIT_SCRATDH=/path/to/your/tempdir bash <dir>/<launcher>


.. _running_locally:
=======
Using an interactive native environment
---------------------------------------

You can also run natively in a virtual environment. You have two options::

  # A premade static environment that you can't change (i.e., can't install anything)
  # Your own development environment where you can install stuff

Activating the premade static environment is very easy::

  source /data/snpit/env/environment_checkout_for_native/smdc-install-native-shared.sh

Done.

If you want to install stuff in a native environment, see :ref:`see below<native_development>`. 

.. _native_development:

Using an interactive native environment for development
-------------------------------------------------------

If you prefer to work in your own Python environment on SMDC, you can create a dedicated virtual environment for the Roman SNPIT photometry packages.  The commands below are intended to be run once to set up the environment, and can be activated again later with:

.. code-block:: console

   source ${HOME}/snpit/snpit-photometry/bin/activate

This setup is intended for the photometry packages ``sidecar``, ``phrosty``, and ``campari``.

In brief, the procedure is:

1. Load the Spack environment.
2. Load Miniconda.
3. Create a Python virtual environment.
4. Install the Roman SNPIT packages into that environment.

Run the following commands on SMDC:

Load the Spack environment (documentation on spack at https://spack-tutorial.readthedocs.io/en/latest/tutorial_environments.html
):


.. code-block:: bash

   source /shared/spack/share/spack/setup-env.sh

Get the Python environment from Miniconda:

.. code-block:: bash

   spack load miniconda3

Initialize Conda in your shell startup file:

.. code-block:: bash

   conda init

Start a new shell so the Conda initialization takes effect, or source ``~/.bashrc`` in the current shell if you prefer:

.. code-block:: bash

   source ~/.bashrc

We will not actually be using Conda after this.  We're just using it for the Python version (because the default Python on the login node image is a minimal version that doesn't have even a complete standard library).

Create the virtual environment in a directory under your home area:

.. code-block:: bash

   mkdir -p ${HOME}/snpit
   cd ${HOME}/snpit
   python -m venv snpit-photometry

Activate the environment whenever you want to work on the development setup:

.. code-block:: bash

   source snpit-photometry/bin/activate

Update ``pip`` once to avoid repeated upgrade notices:

.. code-block:: bash

   pip install --upgrade pip

Install the main Roman SNPIT package for the environment.  This may take a few minutes the first time, as dependencies are installed:

.. code-block:: bash

   pip install roman-snpit-snappl

Install ``roman_imsim`` explicitly, since it is not available from PyPI:

.. code-block:: bash

   pip install git+https://github.com/matroxel/roman_imsim.git@21ea15a

If you are on a GPU machine and want ``cupy``, install it explicitly.  This is not a required dependency of the photometry codes, which can run with either NumPy or CuPy.  Right now (2026-08-12), the SMDC GPU machines are using ``cupy-cuda12x``, but this may change in the future.  If you are on a different system, check the CuPy documentation for the correct version to install.

.. code-block:: bash

   # pip install cupy-cuda12x

Install useful development tools used in the project workflow:

.. code-block:: bash

   pip install pytest
   pip install ruff
   pip install towncrier

>>>>>>> main

Running locally on your machine
===============================

When running on your own machine, you're going to want to pick a ``$RUNDIR``, and make a ``packages`` subdirectory, as always when :ref:`running_env`.


Using pip or Conda
------------------

TODO

Using the Container
-------------------

**Warning**: Currently, we are only able to build our containers for ``x86_64`` (also called ``amd64``) systems.  We have not succeeded in building our containers for ``ARM`` (also called ``arm64``) systems— which includes all Macs.  You *might* be able to run a container from a different architecture on your machine, but performance is likely to be very poor.  This means that for development, you really want to be using an ``x86_64`` Linux machine if that's at all possible.  (We do hope to get the container working for ``ARM``, but it's a thorny problem and not a high priority.  If you want to figure out how to make it work, please do.)

TODO

Running a Test Environment
--------------------------

You need to check out both the `snappl <https://github.com/roman-Supernova-PIT/snappl>`_ and `environment <https://github.com/Roman-Supernova-PIT/environment>`_ github archives in your ``packages`` subdirectory.  You *might* want to check out a different branch of snappl than main one; presumably you will know if this is the case:

.. code-block:: console

   cd packages
   git clone https://github.com/Roman-Supernova-PIT/snappl.git
   git clone https://github.com/Roman-Supernova-PIT/environment.git
   cd ..

(If you know what you're doing, you may want to check out the ``git@github.com:`` versions of the archives instead of the ``https:`` versions of the archives.)  You may need to check out other things; for instance, if you want to run snappl tests, you will also need to clone ``photometry_test_data``.  And, of course, you'll want to have a git checkout of the code you're developing!

Next, you need to build the docker images on your local machine:

.. code-block:: console

  cd packages/environment/test-docker-environment
  docker compose build

Finally, run the environment and start a shell in it:

.. code-block:: console

  docker compose run webserver shell
  docker compose exec -it shell

(both of these should be within the ``test-docker-environment`` subdirectory).  The ``...run...`` command starts several different services (including a database, a web server, a mail server (needed for snappl tests, but you will probably ign ore it), and a shell server.  All of these are inside a private environment, and not accessible from outside.

The second command gets you a command-line on the shell server in the docker compose environment.

You will find ``$RUNDIR`` at ``/home`` in this environment.

Do your stuff.

When you're done, just ``exit`` to leave the environment, and then

.. code-block:: console

  docker compose down -v

to bring all the docker containers you started down.
