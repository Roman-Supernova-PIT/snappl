__all__ = [ 'DiaObject', 'DiaObjectOU2024', 'DiaObjectManual' ]

from snpit_utils.http import retry_post


class DiaObject:
    """Encapsulate a single supernova (or other transient).

    Standard properties:

    ra : ra in degrees (ICRS)
    dec : dec in degrees (ICRS)

    mjd_discovery : when the object was first discovered; may be None if unknown (float MJD)
    mjd_peak : peak of the object's lightcurve; may be None if unknown (float MJD)

    mjd_start : MJD when the lightcurve first exists.  Definition of this
                is class-dependent; it may be when it was actively
                simulated, but it may be when the lightcurve is above some
                cutoff.  May be None if unknown.

    mjd_end : MJD when the lightcurve stops existing.  Definition like
              mjd_start.  May be None if unknown.

    Some subclasses may support additional properties, but use those
    with care, as you are making your code less generral when you use
    them.

    This is an abstract base class.  If you must, instantiate subclass
    objects directly.  If you want to find an existing object, use the
    find_objects class method.

    """

    def __init__( self, id=None, ra=None, dec=None, mjd_discovery=None, mjd_peak=None,
                  mjd_start=None, mjd_end=None, _called_from_find_objects=False ):
        """Don't call a DiaObject or subclass constructor.  Use DiaOjbect.find_objects."""
        if not _called_from_find_objects:
            raise RuntimeError( "Don't call a DiaObject or subclass constructor.  Use DiaObject.find_objects." )
        self.id = id
        self.ra = ra
        self.dec = dec
        self.mjd_discovery = mjd_discovery
        self.mjd_peak = mjd_peak
        self.mjd_start = mjd_start
        self.mjd_end = mjd_end

    @classmethod
    def find_objects( cls, collection=None, subset=None, **kwargs ):
        """Find objects.

        Parameters
        ----------
          collection : str
            Which collection of object to search.  Currently only
            "ou2024" and "manuasl" are implemented, but others will be later.

          subset : str
            Subset of collection to search.  Many collections (including
            ou2024) will ignore this.

          id : <something>
            The ID of the object.  Should work as a str.  This is an
            opaque thing that will be different for different
            collections.

          ra: float
            RA in degrees to search.

          dec: float
            Dec in degrees to search.

          radius: float, default 1.0
            Radius in arcseconds to search.  Ignored unless ra and dec are given.

          mjd_peak_min, mjd_peak_max: float
            Only return objects whose mjd_peak is between these limits.
            Specify as MJD.  Will not return any objects with unknown
            mjd_peak.

          mjd_discovery_min, mjd_discovery_max: float
            Only return objects whose mjd_discovery is between these
            limits.  Specify as MJD.  Wil not return any objects with
            unknown mjd_discovery.

          mjd_start_min, mjd_start_max: float

          mjd_end_min, mjd_end_max: float


        Returns
        -------
          list of DiaObject

          In reality, it will be a list of objects of a subclass of
          DiaObject, but the calling code should not know or depend on
          that, it should treat them all as just DiaObject objects.

        """

        if collection == 'ou2024':
            return DiaObjectOU2024._find_objects( subset=subset, **kwargs )
        elif collection == 'manual':
            return DiaObjectManual._find_objects( subset=subset, **kwargs )
        else:
            raise ValueError( f"Unknown collection {collection}" )

    @classmethod
    def _find_objects( cls, subset=None, **kwargs ):
        raise NotImplementedError( f"{cls.__name__} needs to implement _find_objects" )


# ======================================================================

class DiaObjectOU2024( DiaObject ):
    """A transient from the OpenUniverse 2024 sims."""

    def __init__( self, *args, **kwargs ):
        """Don't call a DiaObject or subclass constructor.  Use DiaOjbect.find_objects."""
        super().__init__( *args, **kwargs )

        # Non-standard fields
        self.host_id = None
        self.gentype = None
        self.model_name = None
        self.start_mjd = None
        self.end_mjd = None
        self.z_cmb = None
        self.mw_ebv = None
        self.mw_extinction_applied = None
        self.av = None
        self.rv = None
        self.v_pec = None
        self.host_ra = None
        self.host_dec = None
        self.host_mag_g = None
        self.host_mag_i = None
        self.host_mag_f = None
        self.host_sn_sep = None
        self.peak_mag_g = None
        self.peak_mag_i = None
        self.peak_mag_f = None
        self.lens_dmu = None
        self.lens_dmu_applied = None
        self.model_params = None

    @classmethod
    def _find_objects( cls, subset=None,
                       id=None,
                       ra=None,
                       dec=None,
                       radius=1.0,
                       mjd_peak_min=None,
                       mjd_peak_max=None,
                       mjd_discovery_min=None,
                       mjd_discovery_max=None,
                       mjd_start_min=None,
                       mjd_start_max=None,
                       mjd_end_min=None,
                       mjd_end_max=None,
                      ):
        if any( i is not None for i in [ mjd_peak_min, mjd_peak_max, mjd_discovery_min, mjd_discovery_max ] ):
            raise NotImplementedError( "DiaObjectOU2024 doesn't support searching on mjd_peak or mjd_discovery" )

        params = {}

        if ( ra is None ) != ( dec is None ):
            raise ValueError( "Pass both or neither of ra/dec, not just one." )

        if ra is not None:
            if radius is None:
                raise ValueError( "ra/dec requires a radius" )
            params['ra'] = float( ra )
            params['dec'] = float( dec )
            params['radius'] = float( radius )

        if id is not None:
            params['id'] = int( id )

        if mjd_start_min is not None:
            params['mjd_start_min'] = float( mjd_start_min )

        if mjd_start_max is not None:
            params['mjd_start_max'] = float( mjd_start_max )

        if mjd_end_min is not None:
            params['mjd_end_min'] = float( mjd_end_min )

        if mjd_end_min is not None:
            params['mjd_end_max'] = float( mjd_end_max )


        res = retry_post( 'https://roman-desc-simdex.lbl.gov/findtransients', json=params )
        objinfo = res.json()

        diaobjects = []
        for i in range( len( objinfo['id'] ) ):
            diaobj = DiaObjectOU2024( id=objinfo['id'][i],
                                      ra=objinfo['ra'][i],
                                      dec=objinfo['dec'][i],
                                      mjd_peak=objinfo['peak_mjd'][i],
                                      mjd_start=objinfo['start_mjd'][i],
                                      mjd_end=objinfo['end_mjd'][i],
                                      _called_from_find_objects=True
                                     )
            for prop in ( [ 'healpix', 'host_id', 'gentype', 'model_name', 'z_cmb', 'mw_ebv', 'mw_extinction_applied',
                            'av', 'rv', 'v_pec', 'host_ra', 'host_dec', 'host_mag_g', 'host_mag_i', 'host_mag_f',
                            'host_sn_sep', 'peak_mag_g', 'peak_mag_i', 'peak_mag_f', 'lens_dmu',
                            'lens_dmu_applied', 'model_params' ] ):
                setattr( diaobj, prop, objinfo[prop][i] )
            diaobjects.append( diaobj )

        return diaobjects


# ======================================================================

class DiaObjectManual( DiaObject ):
    """A manually-specified object that's not saved anywhere."""

    def __init__( self, *args, **kwargs ):
        """Don't call a DiaObject or subclass constructor.  Use DiaOjbect.find_objects."""
        super().__init__( *args, **kwargs )


    @classmethod
    def _find_objects( cls, collection=None, subset=None, **kwargs ):
        if any( ( i not in kwargs ) or ( kwargs[i] is None ) for i in ('id', 'ra', 'dec') ):
            raise ValueError( "finding a manual DiaObject requires all of id, ra, and dec" )

        return [DiaObjectManual( _called_from_find_objects=True, ra=kwargs["ra"], dec=kwargs["dec"], id=kwargs["id"] )]
