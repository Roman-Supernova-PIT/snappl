=====
Usage
=====

First, you need to :ref:`install it <installation-docs>`.  Eventually, snappl
will be installed in the Roman SN-PIT environment, but it's not yet.

Image
=====

The base ``Image`` class has all of the interface you need.  The various
subclasses of ``Image`` implement the actual image reading and such for
different formats of images.  As of this writing, the only implemented
``Image`` subclass is ``OpenUniverse2024FITSImage``.

To use snappl.image, you need to::

    import snappl.image

MORE NEEDS TO BE WRITTEN
