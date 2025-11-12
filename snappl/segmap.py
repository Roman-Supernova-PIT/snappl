__all__ = [ 'SegmentationMap' ]

import uuid

import simplejson

from snappl.dbclient import SNPITDBClient
from snappl.image import OpenUniverse2024FITSImage, FITSImageStdHeaders
from snappl.provenance import Provenance
from snappl.pathedobject import PathedObject
from snappl.utils import SNPITJsonEncoder, asUUID


class SegmentationMap( PathedObject ):
    """Encapsulate a single segmentation map.

    Properties of a SegmentationMap object are:

    * filepath : pathlib.Path ; path *relative to the base path* of the image file of the segmentation map
    * full_filepath : pathlib.Path ; absolute path to file on system.  (Same as base_path / filepath.)
    * base_path : base path for images; usually will be Config value system.paths.segmaps
    * base_dir : synonym for base_path
    * image : an Image object that holds the actual segmentation map data.  Get the 2d numpy
              data of segmap s in s.image.data

    """

    image_format_to_class = { 1: OpenUniverse2024FITSImage,
                              2: FITSImageStdHeaders
                             }

    _base_path_config_item = 'system.paths.segmaps'

    def __init__( self, id=None, provenance_id=None, format=None, l2image_id=None,
                  filepath=None, base_path=None, base_dir=None, full_filepath=None, no_base_path=False ):
        super().__init__( filepath=filepath, base_path=base_path, base_dir=base_dir,
                          full_filepath=full_filepath, no_base_path=no_base_path )
        self.id = asUUID(id) if id is not None else uuid.uuid4()
        self.provenance_id = ( provenance_id.id if isinstance( provenance_id, Provenance)
                               else asUUID(provenance_id) if provenance_id is not None else None )
        self.format = int(format) if format is not None else None
        self.l2image_id = asUUID(l2image_id) if l2image_id is not None else None

        self.band = None
        self.ra = None
        self.dec = None
        self.width = None
        self.height = None
        self._image = None
        for which in [ 'ra', 'dec' ]:
            for corner in [ '00', '01', '10', '11' ]:
                setattr( self, f'{which}_corner_{corner}', None )


    @property
    def image( self ):
        if self._image is None:
            self._load_image()
        return self._image


    def _load_image( self ):
        if self._image is not None:
            return

        if self.filepath is None:
            raise ValueError( "Can't load image when filepath is None." )
        fullpath = self.full_filepath

        if self.format in ( 1, 2 ):
            self._image = self.image_format_to_class[self.format]( fullpath, imagehdu=0, noisehdu=None, flagshdu=None )
        else:
            raise ValueError( f"Unknown format {self.format}" )

        self.width, self.height = self._image.image_shape
        self.band = self._image.band

        wcs = self._image.get_wcs()
        self.ra, self.dec = wcs.pixel_to_world( self.width/2., self.height/2. )
        self.ra_corner_00, self.dec_corner_00 = wcs.pixel_to_world( 0., 0. )
        self.ra_corner_01, self.dec_corner_01 = wcs.pixel_to_world( 0., self.height-1 )
        self.ra_corner_10, self.dec_corner_10 = wcs.pixel_to_world( self.width-1, 0. )
        self.ra_corner_11, self.dec_corner_11 = wcs.pixel_to_world( self.width-1, self.height-1 )

    def save_to_db( self, dbclient=None ):
        self._load_image()
        params = { 'id': self.id,
                   'provenance_id': self.provenance_id,
                   'band': self.band,
                   'ra': self.ra,
                   'dec': self.dec,
                   'ra_corner_00': self.ra_corner_00,
                   'ra_corner_01': self.ra_corner_01,
                   'ra_corner_10': self.ra_corner_10,
                   'ra_corner_11': self.ra_corner_11,
                   'dec_corner_00': self.dec_corner_00,
                   'dec_corner_01': self.dec_corner_01,
                   'dec_corner_10': self.dec_corner_10,
                   'dec_corner_11': self.dec_corner_11,
                   'filepath': str( self.filepath ),
                   'width': int( self.width ),
                   'height': int( self.height ),
                   'format': int( self.format ),
                   'l2image_id': self.l2image_id
                  }
        postdata = simplejson.dumps( params, cls=SNPITJsonEncoder )

        dbclient = SNPITDBClient.get() if dbclient is None else dbclient

        return dbclient.send( "savesegmap", data=postdata, headers={'Content-Type': 'application/json'} )

    @classmethod
    def _segmap_from_dbreturn( cls, res ):
        segmap = SegmentationMap( id=res['id'], provenance_id=res['provenance_id'], format=res['format'],
                                  filepath=res['filepath'], l2image_id=res['l2image_id'] )
        segmap.width = res['width']
        segmap.height = res['height']
        segmap.band = res['band']
        segmap.l2image_id = asUUID( res['l2image_id'] ) if res['l2image_id'] is not None else None
        segmap.ra = res['ra']
        segmap.dec = res['dec']
        for which in [ 'ra', 'dec' ]:
            for corner in [ '00', '01', '10', '11' ]:
                att = f'{which}_corner_{corner}'
                setattr( segmap, att, res[att] )

        return segmap


    @classmethod
    def get_by_id( cls, segmap_id, dbclient=None ):
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        res = dbclient.send( f"getsegmap/{segmap_id}" )
        if not isinstance( res, dict ):
            raise TypeError( f"Expected a dict from web server, got a {type(res)}" )
        return cls._segmap_from_dbreturn( res )

    @classmethod
    def find_segmaps( cls, provenance=None, provenance_tag=None, process=None, dbclient=None, **kwargs ):
        """Find segmentation maps.

        Parameters
        ----------
          provenance : Provenance, UUID, or str, default None
            The Provenacne, or the id of the Provenance, to search.
            Must specify either this, or both of provenance_tag and
            process.

          provenance_tag : str, default None
            The provenance tag to search.  Required if provenance is
            None.

          process : str, default None
            The process of the provenance_tag to search.  Required if
            provenance_tag is given.

          ra, dec : float, default None
            If ra and dec are given, will find all segmentation maps
            that include this point.

          ra_min, ra_max, dec_min, dec_max: float, default None
            If any of these are given, will limit images to things that
            fall within the relevant range.  It probably doesn't make
            sense to include any of these alongside (ra, dec).

            NOTE: this refers the the centra ra of the segmentation map;
            it does not consider the corners.  If you really want to be
            anal, you could include 16 parameters, ra_corner_00_min,
            ra_corner_00_max, etc.  Be aware, however, that corner_00
            refers to the lower-left of the image (i.e. pixel 0,0),
            which depending on rotation will *not* be an extremum of ra
            and dec.

            WARNING : ra ranges crossing 0 are not yet properly
            implemented.

          band : str, default None
            If given, only include segmentation maps that go with this band.

          l2image_id : str or UUID, default None
            If given, only find segmentation maps that go with this image.


        Returns
        -------
          list of SegmentationMap

        """
        if provenance is not None:
            params = { 'provenance': provenance.id if isinstance(provenance, Provenance) else asUUID( provenance ) }
        else:
            if ( provenance_tag is None ) or ( process is None ):
                raise ValueError( "Must specify either provenance, or both of provenance_tag and process" )
            params = { 'provenance_tag': str(provenance_tag),
                       'process': str(process)
                      }

        params.update( kwargs )
        dbclient = SNPITDBClient.get() if dbclient is None else dbclient
        postdata = simplejson.dumps( params, cls=SNPITJsonEncoder )
        res = dbclient.send( "findsegmaps", data=postdata, headers={'Content-Type': 'application/json'} )

        return [ cls._segmap_from_dbreturn(r) for r in res ]
