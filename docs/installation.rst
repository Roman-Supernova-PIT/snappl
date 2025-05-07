.. _installation-docs:
.. highlight:: shell

============
Installation
============

SN Pit Docker environment
-------------------------

As of this writing, ``snappl`` is not in the `SN PIT Docker envirionment
<https://github.com/Roman-Supernova-PIT/environment>`_.  However, before
long, we hope to integrate the production release of ``snappl`` into
that docker image.  Once that happnes, if you're using that image, you
will not need to do anyting; ``snappl`` will already be installed for you.


Stable release
--------------

**NOTE** -- as of this writing, there is not a stable release, so this
section won't work.

To install snappl, run this command in your terminal:

.. code-block:: console

    $ pip install snappl

This is the preferred method to install snappl, as it will always install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.

.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for snappl can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git@github.com:Roman-Supernov-PIT/snappl.git

Or download the `tarball`_:

.. code-block:: console

    $ curl -OJL https://github.com/Roman-Supernova-PIT/snappl/snappl/tarball/master

Once you have a copy of the source, you can install it with:

.. code-block:: console

    $ pip install .

This will install snappl in your current virtual environment.


.. _Github repo: https://github.com/Roman-Supernova-PIT/snappl/snappl
.. _tarball: https://github.com/Roman-Supernova-PIT/snappl/snappl/tarball/master
