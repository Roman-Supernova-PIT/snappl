from snpit_utils.http import retry_post


class DiaObject:
    """Encapsulate a single supernova (or other transient).

    Standard properties:

    ra : ra in degrees (ICRS)
    dec : dec in degrees (ICRS)

    tdiscovery : when the object was first discovered; may be None if unknown (float MJD)
    tmax : peak of the object's lightcurve; may be None if unknown (float MJD)

    tstart : MJD when the lightcurve first exists.  Definition of this
             is class-dependent; it may be when it was actively
             simulated, but it may be when the lightcurve is above some
             cutoff.  May be None if unknown.

    tend : MJD when the lightcurve stops existing.  Definition like
           tstart.  May be None if unknown.

    Some subclasses may support additional properties, but use those
    with care, as you are making your code less generral when you use
    them.

    This is an abstract base class.  If you must, instantiate subclass
    objects directly.  If you want to find an existing object, use the
    find_objects class method.

    """

    def __init__( self, ra=None, dec=None, tdiscovery=None, tmax=None ):
        self.ra = ra
        self.dec = dec
        self.tdiscovery = None
        self.tmax = None
        self.tstart = None
        self.tend = None

    @classmethod
    def find_objects( cls, collection=None, subset=None, **kwargs ):
        """Find objects.

        Parameters
        ----------
          collection : str
            Which collection of object to search.  Currently only
            "ou2024" is implemented, but others will be later.

          subset : str
            Subset of collection to search.  Many collections (including
            ou2024) will ignore this.

          id : <something>
            The ID of the object.  Should work as a str.  This is an
            opaque thing that will be differnet for different
            collections.

          ra: float
            RA in degrees to search.

          dec: float
            Dec in degrees to search.

          radius: float, default 1.0
            Radius in arcseconds to search.  Ignored unless ra and dec are given.

          tmax_min, tmax_max: float
            Only return objects whose tmax is between these limits.
            Specify as MJD.  Will not return any objects with unknown
            tmax.

          tdiscovery_min, tdiscovery_max: float
            Only return objects whose tdiscovery is between these
            limits.  Specify as MJD.  Wil not return any objects with
            unknown tdiscovery.

          tstart_min, tstart_max: float

          tend_min, tend_max: float


        Returns
        -------
          list of DiaObject

          In reality, it will be a list of objects of a subclass of
          DiaObject, but the calling code should not know or depend on
          that, it should treat them all as just DiaObject objects.

        """

        if collection == 'ou2024':
            return DiaObjectOU2024._find_objects( subset=subset, **kwargs )
        else:
            raise ValueError( f"Unknown collection {collection}" )

    @classmethod
    def _find_objects( cls, subset=None, **kwargs ):
        raise NotImplementedError( f"{cls.__name__} needs to implement _find_objects" )


# ======================================================================

class DiaObjectOU2024:
    """A transient from the OpenUniverse 2024 sims."""

    def __init__( self, *args, **kwargs ):
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
                       ra=None,
                       dec=None,
                       radius=1.0,
                       tmax_min=None,
                       tmax_max=None,
                       tdiscovery_min=None,
                       tdiscovery_max=None,
                       tstart_min=None,
                       tstart_max=None,
                       tend_min=None,
                       tend_max=None,
                      ):
        if any( i is not None for i in [ tmax_min, tmax_max, tdiscovery_min, tdiscovery_max ] ):
            raise NotImplementedError( "DiaObjectOU2024 doesn't support searching on tmax or tdiscovery" )

        params = {}

        if ( ra is None ) != ( dec is None ):
            raise ValueError( "Pass both or neither of ra/dec, not just one." )

        if ra is not None:
            if radius is None:
                raise ValueError( "ra/dec requires a radius" )
            params['ra'] = float( ra )
            params['dec'] = float( dec )
            params['radius'] = float( radius )

        if tstart_min is not None:
            params['tstart_min'] = float( tstart_min )

        if tstart_max is not None:
            params['tstart_max'] = float( tstart_max )

        if tend_min is not None:
            params['tend_min'] = float( tend_min )

        if tend_min is not None:
            params['tend_max'] = float( tend_max )


        res = retry_post( 'https://roman-desc-simdex.lbl.gov/findtransients', json=params )
        objinfo = res.json()

        diaobjects = []
        for i in range( len( res['id'] ) ):
            diaobj = DiaObjectOU2024( ra=objinfo['ra'][i], dec=objinfo['dec'][i], tmax=objinfo['peak_mjd'][i] )
            diaobj.tstart = objinfo['start_mjd'][i]
            diaobj.tend = objinfo['end_mjd'][i]
            for prop in ( [ 'healpix', 'host_id', 'gentype', 'model_name', 'z_cmb', 'mw_ebv', 'mw_extinction_applied',
                            'av', 'rv', 'v_paec', 'host_ra', 'host_dec', 'host_mag_g', 'host_mag_i', 'host_mag_f',
                            'host_sn_sep', 'peak_mag_g', 'peak_mag_i', 'peak_mag_f', 'lens_dmu',
                            'lens_dmu_applied', 'model_params' ] ):
                setattr( diaobj, res[prop][i] )
            diaobjects.append( diaobj )

        return diaobjects
