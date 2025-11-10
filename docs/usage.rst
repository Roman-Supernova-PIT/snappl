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
* Find segmentation maps in the database
* Saving newly discovered DiaObjects to the database
* Finding DiaObjects
* Saving updated positions for DiaObjects
* Saving lightcurves to the database
* Finding and reading lightcurves from the database
* Saving 1d transient spectra to the database
* Finding and reading 1d transient spectra from the database
  
This section describes what you need to do in order to connect to the database.

**WARNING**: because everything is under heavy development, it's possible that interfaces will change.  We will try to avoid doing this, because it's a pain when everybody has to adapt, but we're still building this, so it may be inevitable.

Recipes
=======

Read everything to understand what's going on, but these are intended as a quick start.

Prerequisites
-------------

These recipes assume you have a working environment (see :ref:`nov2025-working-env`), which hopefully is as simple as ``pip install roman-snpit-snappl``, but see that section for all the details and where you eventually need to be heading.

They also assume you have set up a config file.  If you're on NERSC, *not* running in a container, then save `the config file for running natively on NERSC <https://raw.githubusercontent.com/Roman-Supernova-PIT/environment/refs/heads/main/nov2025_nersc_native_config.yaml>`_.  (This is the file ``nov2025_nersc_native_config.yaml`` from the top level of the ``environment`` roman snpit github archive).  Note that you will need to do two small edits in this file!  If you are running in a podman container, then look at `the in-container config file <https://raw.githubusercontent.com/Roman-Supernova-PIT/environment/refs/heads/main/nov2025_container_config.yaml>`_. (This is the file ``nov2025_nersc_container_config.yaml`` from the top level of the ``environment`` roman snpit github archive); you will also need to download `interactive-podman-nov2025.sh <https://raw.githubusercontent.com/Roman-Supernova-PIT/environment/refs/heads/main/interactive-podman-nov2025.sh>`_.   If you are elsewhere, you will need to edit the config file to have the right paths to find things on your system.

You need to set the environment variable ``SNPIT_CONFIG`` to point to where this configuration file lives.

Finally, once at the top of your code you need to do::
  
  from snappl.dbclient import SNPITDBClient

  dbclient = SNPITDBClient.get()

You can then make futher connections to the database using this ``dbclient`` variable.  Many ``snappl`` functions that connect to the database take an optional ``dbclient`` parameter, to which you can pass this.  By default, most of them will, in the background, just use the first one that was created with the first call to ``SNPITDBClient.get()``.   (See the docstring for ``SNPITDBClient.get`` if you are morbidly curious.)

  
.. _recipe-command-line-args:

Variables/Arguments for IDs and Provenances
-------------------------------------------

Below, you will be told you need to know a number of object ids and/or provenance-related values.  These will generally be provided by orchestration.  You should make them things that can be passed on the command line.  I recommend using the following command-line arguments — choose the ones that you need (they are all string values)::

  --diaobject-id
  --diaobject-provenance-tag
  --diaobject-process
  --diaobject-position-provenance-tag
  --diaobject-position-process
  --image-id
  --image-provenance-tag
  --image-process
  --segmap-provenance-tag
  --segmap-process
  --ltcv-provenance-tag
  --ltcv-process
  --spec1d-provenance-tag
  --spec1d-process

If you just plan to call functions from python, then you can make the things you need keyword arguments.  I recommend using the same names as above, only replacing the dashes with underscores (and removing the two dashes at the beginning).  The examples below all assume that the variables have these names.

For a list of provenance tags we will be using during the November 2025 run, see :ref:`nov2025-provtags`.


.. _recipe-find-diaobject:

Finding a DiaObject
-------------------

You need to know *either* the ``diaobjectd_id`` of the object (which you will generally be given), or you need to know the ``diaobject_provenance_tag`` and ``diaobject_process``, and you must have enough search criteria to find the object.  If you're doing the latter, read the docstring on ``snappl.diaobject.DiaObject.find_objects``.  For the former::

  from snappl.diaobject import DiaObject

  diaobject = DiaObject.get_object( diaobject_id=diaobject_id )

The returned ``DiaObject`` object has, among other things, properties ``.id``, ``.ra`` and ``.dec``.


.. _recipe-diaobject-position:

Getting an updated diaobject position
-------------------------------------

You need the ``diaobject_position_provenance_tag`` and ``diaobject_position_process``.

Do::

  diaobj_pos = diaobject.get_position( provenance_tag=diaobject_position_provenance_tag,
                                       process=diaobject_position_process )

You get back a dictionary that has a number of keys including ``ra`` and ``dec``.

   


Getting a Specific Image
------------------------

Orchestration has given you a ``image_id`` that you are supposed to do something with.  E.g.,, you are running sidecar, and you're supposed to subtract and search this image.

  from snappl.image import Image

  image = Image.get_image( image_id )

You will get back an ``Image`` object (really, an object of a class that is a subclass of ``Image``).  It has a number of properties.  Most important are ``.data``, ``.noise``, and ``.flags``, which hold 2d numpy arrays.  There is also a ``.get_fits_header()`` method that currently works, **but be careful using this as this method will not work in the future when we're using ASDF files**.  See the docstrings in ``snappl.image.Image`` for more details.  Some of the stuff you might want is available directly as properties of and ``Image`` object.
                                               

Finding Images
--------------

You need to know the ``image_provenance_tag`` and ``image_process``.

See the docstring on ``snappl.imagecollection.ImageCollection.find_images`` if you want to do more than what's below.


Finding all images in a given band that include a ra and dec
************************************************************

Do::

  from snappl.image import Image

  images = Image.find_images( provenance_tag=image_provenacne_tag, process=image_process,
                              ra=ra, dec=dec, band=band )

where ``band=band`` is optional but often useful.  (If you don't specify it, you will get back images from all bands.) You will get back a list of ``Image`` objects, which have a number of properties (some of which may be ``None`` if they are unknown):

  * ``data`` : the data array, in ADU, a 2d numpy array
  * ``noise`` : the ADU uncertainty on the data, a 2d numpy array
  * ``flags`` : pixel flags, a 2d numpy array of ints [we are still working on definining these]
  * ``width`` : int, the width of the image in pixels; horizontal as viewed on ds9; corresponds to data.shape[1]
  * ``height`` : int, the height of the image in pixels; vertical as viewed on ds9; corresponds to data.shape[0]
  * ``image_shape`` : tuple of ints, (height, width)
  * ``pointing`` : int or str, the pointing; **warning** this property name will change when we know more
  * ``sca`` : int, the chip of the image
  * ``ra`` : float, the nominal center of the image in decimal degrees (usu. from the header)
  * ``dec`` : float, the nominal center of the image in decimal degrees (usu. from the header)
  * ``coord_center`` : tuple of (ra, dec) [I THINK], calcualted from the image WCS
  * ``ra_corner_00`` : float, decimal degrees, the RA of pixel (0, 0)
  * ``ra_corner_01`` : float, decimal degrees, the RA of pixel (0, height-1)
  * ``ra_corner_10`` : float, decimal degrees, the RA of pixel (width-1, 0)
  * ``ra_corner_11`` : float, decimal degrees, the RA of pixel (width-1, height-1)
  * ``dec_corner_00`` : float, decimal degrees, the Dec of pixel (0, 0)
  * ``dec_corner_01`` : float, decimal degrees, the Dec of pixel (0, height-1)
  * ``dec_corner_10`` : float, decimal degrees, the Dec of pixel (width-1, 0)
  * ``dec_corner_11`` : float, decimal degrees, the Dec of pixel (width-1, height-1)
  * ``band`` : str, the filter/band/whatever you call it for this image
  * ``mjd`` : float, mjd (days) when the image exposure started
  * ``position_angle`` : float, position angle in degrees north of east (CHECK THIS)
  * ``exptime`` float, exposure time in seconds
  * ``sky_level`` float; an estimate of the sky level (in ADU) if known, None otherwise
  * ``zeropoint`` : float; convert ADU to AB magnitudes with ``m = -2.5*log10(adu) + zeropoint``

**Warning**: because of how numpy arrays are indexed, if you want to get the flux value in pixel ``(ix, iy)``, you would look at ``.data[iy, ix]``.
  
There is also a ``.get_fits_header()`` method that currently works, **but be careful using this as this method will not work in the future when we're using ASDF files**.  See the docstrings in ``snappl.image.Image`` for more details.

Finding Segmentation Maps
-------------------------

You need to know the ``segmap_provenance_tag`` and the ``segmap_process``.

See the docstring on ``snappl.segmap.SegmentationMap.find_segmaps`` for more information on searches you can do beyond what's below.

Finding all segmaps that include a ra and dec
*********************************************

Do::

  from snappl.segmap import SegmentationMap

  segmaps = SegmentationMap.find_segmaps( provenance_tag=segmap_provenance_tag,
                                          process=segmap_process,
                                          ra=ra, dec=dec )

You get back a list of ``SegmentationMap`` objects.  These have a number of properties, most import of which is ``image``, which holds an ``Image`` object.  You can get the image data for the segmentation map for the first element of the list with ``segmaps[0].image.data`` (a 2d numpy array).


Saving a new DiaObject
----------------------

You are running sidecar and you've found a new diaobject you want to save.  You need a ``process`` (we shall assume ``process='sidecar'`` here), the ``major`` and ``minor`` version of your code, and the ``params`` that define how the code runs.  The latter is just a dictionary; you can build it yourself, but see :ref:`nov2025-making-prov` below.  Finally, assume that ``images`` is an list that has the ``snappl.image.Image`` objects of the images that you've used; replace ``images[0]`` below with wherever you have your ``Image`` object::

  from snappl.provenance import Provenance
  from snappl.diaobject import DiaObject

  imageprov = Provenance.get_by_id( images[0].provenance_id )
  prov = Provenance( process='sidecar', major=major, minor=minor, params=params,
                     upstreams=[ imageprov ] )
  # You only have to do this next line once for a given provenance;
  #   once the provenance is in the database, you never need to save it again.
  prov.save_to_db( tag=diaobject_provenance_tag )   # See note below

  diaobj = DiaObject( provenance_id=prov.id, ra=ra, dec=dec, name=optional, mjd_discovery=mjd )
  diaobj.save_object()
  

This will save the object to the database.  You can then look at ``diaobj.id`` to see what UUID it was assigned.  You do not need to give it a ``name``, but you can if you want to.  (The database uses the ``id`` as the unique identifier.)  ``mjd_discovery`` should be the MJD of the science image that the object was found on.

Finding and reading lightcurves
-------------------------------

You need to know the ``ltcv_provenance_tag`` and ``ltcv_process``, and the ``diaobject_id`` of the object for which you want to get lightcurves::

  from snappl.lightcurve import Lightcurve

  ltcvs = Lightcurve.find_lightcurves( provenance_tag=ltcv_provenance_tag,
                                       process=ltcv_process,
                                       diaobject=diaobject_id,
                                       band=band,         # optional
                                     )

You will get back a list of ``Lightcurve`` objects.  You can find the actual lightcurve data of the first lightcurve from the list with ``ltcvs[0].lightcurve``.  This is an astropy QTable.  You can read the metadata from ``ltcvs[0].lightcurve.meta``.

**Coming soon**: a way to read a combined lightcurve that has all of the bands mixed together.  (Not implemented yet.)


Saving lightcurves
------------------

You need to make sure you've created a dictionary with `all the necessary metadata <https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/lightcurve>`_.  Also make sure you've created a data table with the necessary columns; this can be an astropy Table, a pandas DataFrame, or a dict of lists.  We shall call these two things ``meta`` and ``data``.

Assume that you've made the lightcurve for object ``diaobject`` (a ``DiaObject`` object), and that you have a list of your images in ``images``.  Adjust below for the variables where you really have things.  Finally, if you used an updated :ref:`DiaObject position <recipe-diaobject-position>`, make sure you have set the ``ra`` and ``dec`` in ``meta`` from that.

Finally, you will need to know the ``ltcv_provenance_tag`` we're using.

Below, ``process`` is probably either ``campari`` or ``phrosty``.  ``major`` and ``minor`` are the major and minor parts of the version, which you should parse from ``campari.__version__`` or ``phrosty.__version__``.  ``params`` are the parameters as described below in :ref:`nov2025-making-prov`.

Do::

  from snappl.provenance import Provenance
  from snappl.lightcurve import Lightcurve

  imgprov = Provenance.get_by_id( images[0].provenance_id )
  objprov = Provenance.get_by_id( diaobject.provenance_id )
  objposprov = Provenance.get_by_id( diaobj_pos['provenance_id'] )

  ltcvprov = Provenance( process=process, major=major, minor=minor, params=params,
                         upstreams=[imgprov, objprov, objposprov] )
  # The next line only needs to be run once.  Once you've saved it to the database,
  #   you never need to do this again.
  ltcvprov.save_to_db( tag=ltcv_provenance_tag )

  meta['provenance_id'] = ltcvprov.id
  meta['diaobject_id'] = diaobject.id
  meta['diaobject_position_id'] = diaobj_pos['id']
  for att in [ 'ra', 'dec', 'ra_err', 'dec_err', 'ra_dec_covar' ]:
      meta[att] = diaobj_pos[att]

  ltcv = Lightcurve( data=data, meta=meta )
  ltcv.write()
  ltcv.save_to_db()

You can look at ``ltcv.id`` to see the ``UUID`` of the lightcurve you saved, in case you are curious.
  
If you used the ``ra`` and ``dec`` that was in ``DiaObject``, then ``meta['diaobject_position_id']`` should be ``None``.  Skip everything else above that refers to ``diaobj_pos``.
  


Finding and reading 1d Spectra
------------------------------

Right now we only have 1-d transient spectra, defined by `the schema here <https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/spectrum_1d>`_.

If you already know the ID of the spectrum you want, you can just do::

  from snappl.spectrum1d import Spectrum1d

  spec = Spectrum1d.get_spectrum1d( spectrum1d_id )

That will return a ``Spectrum1d`` object.  See its docstring for more information.  The most important property is probably ``combined_data``, which has dictionary with four elements; each value of the dictionary is a numpy array of the same length:
  * ``lamb`` : the wavelength (in Å)
  * ``flam`` : the flux (in what erg/s/cm²/Å)
  * ``func`` : the uncertainty on ``flam``
  * ``count`` : an integer, the number of individual image spectra that contributed to this data point.
    

The ``data_dict`` property has the full dictionary of data defined in the 1d spectrum schema.

You can find a spectra for a given object with::

  from snappl.spectrum1d import Spectrum1d

  specs = Spectrum1d.find_spectra( provenance_tag=spec1d_provenance_tag,
                                   process=spec1d_process,
                                   diaobject_id=diaobject_id,
                                   mjd_start_min=mjd0,       # optional
                                   mjd_end_max=mjd1        # optional
                                 )

The ``mjd...`` parmaeters are optional; include these if you want to provide a time window into which all the images that went into the spectra fit.  See the ``find_spectra`` docstring for more optional parameters you can supply for the search.  You will get back a list of ``Spectrum1d`` objects.


Saving 1d Spectra
-----------------

You need to have the ``diaobject`` (a ``DiaObject`` object) for which you made the spectrum, potentially a ``diaobj_pos``, an improved position for the object, and ``images``, a list of ``Image`` object that held the dispersed images from which you are making the spectrum.  You need to know the ``spec1d_provenance_tag``.

You need to know the ``process`` (which is probably just the name of your code), and the ``major`` and ``minor`` versions of your code.  Finally, you need to know the ``params`` that define how your code runs.   The latter is just a dictionary; you can build it yourself, but see :ref:`nov2025-making-prov` below.

You build a data structure that is described on `the wiki <https://github.com/Roman-Supernova-PIT/Roman-Supernova-PIT/wiki/spectrum_1d>`_; call that ``spec_struct``.  Note that if you pass all of ``provenance``, ``diaobject``, and ``diaobject_position_id`` to the ``Spectrum1d`` constructor, you do not necessarily need to have all those IDs in the ``spec_struct`` ahead of time; the constructor will fill out what is necessary.  If you do both pass them and put them in the ``spec_struct``, they must be consistent.  You do *not* need to (and should not) set ``meta['id']`` or ``meta['filepath']`` yourself.  ``id`` will be generated when you construct the ``Spectrum1d`` object, and ``filepath`` will be set automatically when you save the spectrum.

Do::

  from snappl.provenance import Provenance
  from snappl.spec1d import Spectrum1d

  diaobj_prov = Provenance.get_by_id( diaobject.provenance_id )
  imageprov = Provenance.get_by_id( images[0].provenance_id )
  diaobj_pos_prov = Provenance.get_by_id( diaobj_pos['id'] )

  spec1d_prov = Provenance( process=process, major=major, minor=minor, params=params,
                            upstreams=[ diaobj_prov, imageprov, diaobj_pos_prov ] )
  # The next line only needs to be run once.  Once
  #   you have saved a Provenance to the database you
  #   never need to save it again
  spec1d_prov.save_to_db( tag=spec1d_provenance_tag )

  # Make sure that all the mandatory metadata is there.  In particular, it is necessary
  #   for each spec_struct['individual][n]['meta']['image_id'] to be set (where n is an
  #   integer).  You could do this with:
  for i in range( len(images) ):
      spec_struct['individual'][i]['meta']['image_id'] = images[i].id

  spec1d = Spectrum1d( spec_struct )
  spec1d.save_to_db( write=True )


Note that when you create a ``Spectrum1d``, it will keep a *copy* of the ``spec_struct`` object you passed in its ``spec_struct`` property.  It will also modify this object, adding the ``id`` and ``filepath`` attributes, as well other things based on what you pass to the constructor.  You can always get back at the internally stored structure with the ``data_dict`` property of the ``Spectrum1d`` object.

----------------------------


.. _nov2025-working-env:

Choose a working environment
============================

Whatever it is, you will need to ``pip install roman-snpit-snappl``.  *This package is under heavy development, so you will want to update your install often*.  This provides the ``snappl`` modules that you are currently reading the documentation for.

**We strongly recommend you think ahead towards developing your code to run in a container.  The SNPIT will probably eventually need to run everything it does in containers.**  On your desktop or laptop, you can use Docker.  On NERSC, you can use ``podman-hpc``.  On many other HPC clusters, you can use Singularity.

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

**WARNING:** The snpit docker environment does not currently work on ARM architecture machines (because of issues with Galsim and fftw).  This means that if you're on a Mac, you're SOL.  If you're on a Linux machine, do ``uname -a`` and look towards the end of the output to see if you're on ``x86_64`` or ARM.  We hope to resolve this eventually.  For now, as much as possible run on ``x86_64`` machines.  (However, reports are that ``pip instasll roman-snpit-snappl`` *does* work on ARM Macs, so the issue may just be we need to figure out how to get the docker images to build for ARM.)

You can, of course, create your own containerized environment for your code to run in, but you will need to support it, and eventually you will need to deliver it for the PIT to run in production.  For that reason, we strongly recommend you start trying to use the standard SNPIT environment.  Ideally, your code should be pip installable from PyPI, and eventually your code will be included in the environment just like ``snappl`` currently is.

.. _nov2025-making-prov:

Making Provenances
==================

Before you save anything to the database, you need to make a :ref:`provenance` for it.  For example, consider the difference imaging lightcurve package ``phrosty``.  It will need to have a diaobject (let's assume it's in the variable ``obj``), and it will need to have a list of images (let's assume they're in the variable ``images``; we'll leave aside details of template vs. science images for now).  Let's assume ``phrosty`` is using the :ref:`config` system in ``snappl``, and has put all of its configuration under ``photometry.phrosty``.  (There are details here you must be careful about; things like paths on your current system should *not* go under ``photometry.phrosty``, but should go somewhere underneath ``system.``.  The current object and list of images you're working on should not be in the configuration, but should just be passed via command-line parameters.  The idea is that the configuration has all of, but only, the things that are the same for a large number of runs on a large number of input files which guarantee (as much as possible) the same output files.)

phrosty could then determine its own provenance with::

  from snappl.config import Config
  from snappl.provenance import Provenance

  objprov = Provenance.get_by_id( obj.provenance_id )
  improv = Provenance.get_by_id( images[0].provenance_id )
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

  phrostyprov.save_to_db( tag=PROVENANCE_TAG )

where ``PROVENANCE_TAG`` is a string; see :ref:`nov2025-provtags` below for a list of what we plan to use.

.. _nov2025-provtags:

Provenance Tags We Will Use In November 2025
============================================

**WARNING**: View this list as preliminary.  It may all change at any moment.


+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| provenance_tag          | process                    | for                | produced by     | notes           |
+=========================+============================+====================+=================+=================+
| ``ou2024_truth``        | ``load_ou2024_diaobject``  | diaobject          | (primordial)    | Truth-table     |
|                         |                            |                    |                 | objects         |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``ou2204_truth``        | ``diaobject_position``     | diaobject_position | (primordial)    | Truth-table     |
|                         |                            |                    |                 | positions (1)   |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``ou2024``              | ``load_ou2024_image``      | direct image       | (primordial)    | l2 images       |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``ou2024``              | ``load_ou2024_dispimages`` | prism image        | (primordial)    | l2 prism images |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025``             | ``sidecar``                | diaobject          | sidecar         | objects found   |
|                         |                            |                    |                 | by sidecar dia  |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025``             | ``phrosty``                | lightcurve         | phrosty         | forced-phot     |
|                         |                            |                    |                 | lightcurves     |
|                         |                            |                    |                 | on sidecar objs |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025_ou2024``      | ``phrosty``                | lightcurve         | phrosty         | forced-phot     |
|                         |                            |                    |                 | lightcurves     |
|                         |                            |                    |                 | on ou2024 objs  |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025``             | ``phrosty_position``       | diaobject_position | phrosty         | improved        |
|                         |                            |                    |                 | positions of    |
|                         |                            |                    |                 | sidecar objs    |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025``             | ``campari``                | lightcurve         | campari         | scene-modelling |
|                         |                            |                    |                 | lightcurve      |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025``             | (something)                | spectrum1d         | (something)     | spectra of      |
|                         |                            |                    |                 | sidecar objs w/ |
|                         |                            |                    |                 | phrosty poses   |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+
| ``nov2025_ou2024``      | (something)                | spectrum1d         | (something)     | spectra of      |
|                         |                            |                    |                 | ou2024 truth    |
|                         |                            |                    |                 | objs w/ truth   |
|                         |                            |                    |                 | poses           |
+-------------------------+----------------------------+--------------------+-----------------+-----------------+



**(1)** These positions will be identical to the positions in the ``DiaObject`` object for the ``ou2024_truth`` provenance tag.  However, they are still here so you can write the code to use the positions table.



.. _connecting-to-the-database:

--------------------------
Connecting to the Database
--------------------------

To connect to the database, you need three things.  First, you have to know the url of the web API front-end to the database.  You must also have a username and a password for that web API.  (NOTE: the config system is likely to change in the future, so exactly how this works may change.)  If you're using :ref:`test_env`, then the test fixture ``dbclient`` configures a user with username ``test`` and password ``test_password``, and in that environment the url of the web API is ``https://webserver:8080/``.

You configure all of these things by setting the ``system.db.url``, ``system.db.username``, and either ``system.db.password`` or ``system.db.password_file`` in the configuration yaml files.  (See :ref:`config` below.)  For example, see the default `snpit_system_config.yaml <https://github.com/Roman-Supernova-PIT/environment/blob/main/snpit_system_config.yaml>`_ in the Roman SNPIT environment.  *Do not save passwords to any git archive, and do not leave them sitting about in insecure places.*  Of course, having to type it all the time is a pain.  A reasonable compromise is to have a ``secrets`` directory under your home directory **that is not world-readable** (``chown 700 secrets``).  Then you can create files in there.  Put your password in a file, and set the location of that file in the ``system.db.password_file`` config.  (Make ``system.db.password`` to be ``null`` so the password file will be used.)  If you're using a docker container, of course you'll need to bind-mount your secrets directory.

Once you've configured these things, you should be able to connect to the database.  You can get a connection object with::

  from snappl.dbclient import SNPITDBClient

  dbclient = SNPITDBClient.get()

Thereafter, you can pass this ``dbclient`` as an optional argument to any ``snappl`` function that accesses the database.  (Lots of the examples below do not explicitly include this argument, but you could add it to them.)  Most of these functions will just use the first ``dbclient`` you created (which is cached in the background) if you don't pass one, or create one themselves if one doesn't already exists, so usually passing one isn't necessary.

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
