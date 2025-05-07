snappl Documentation
--------------------

This is the documentation for snappl.

**Version**: |version|


This package contains the Python software suite developed for use with the Roman Telescope project, as part of the Roman Supernova Project Implementation Team (PIT) project.


If you have questions or concerns regarding the software, please create an issue in
the github package repository at https://github.com/Roman-Supernova-PIT/snappl/snappl

--------------------------------

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   installation.rst
   usage.rst
   config.rst

snappl Overview
===============

snappl is a package designed to combine together functions that will be used by multiple different photometry codes for the Roman SN-PIT: things like image reading, WCS interpretation, PSF rendering.  The quesiton arises, why bother?  Doesn't ``roman_datamodel`` already support all of this?  As of the current development, given the test files we've had, everything has been developed using OpenUniverse FITS files.  The goal of snappl is to abtract away things like image acquisition, WCS transformations, and PSF rendering so that codes will be able to continue to work with FITS files, but when we implement other files (e.g. things built using ``roman_datamodel``), we can put those changes in ``snappl`` and the two to three other codes that use it will require only minimal changes.  Meanwhile, the will still continue to work with pre-existing FITS files.

snappl also has some functionality that will potentially be of interest to the entire Roman SN PIT, in particular the



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
