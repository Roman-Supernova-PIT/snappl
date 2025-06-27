# Put in necessary imports

class SED_collection:
    def __init__( self, *args, **kwargs ):
        pass

    def get_sed( self, filename=None, snid=None, mjd=None ):
        """Return a galsim SED."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_sed" )


class Flat_SED( SED_Collection ):
    def __init__( self ):
        self.sed = galsim.SED( galsim.LookupTable( [1000, 26000], [1, 1], interpolant='linear' ),
                               wave_type='Angstrom', flux_type='fphotons' )

    def get_sed( sed, **kwargs):
        return self.sed
    

class Single_CSV_SED( SED_Collection ):
    def __init__( self, csv_file ):
        # READ THE CSV FILE, make a galsim SED in self.sed
        raise NotImplementedError( "Single_CSV_SED is not implemented yet." )

    def get_sed( self, **kwargs ):
        return self.sed


# Make a SED collection class or something
    
        
class OU2024_Truth_SED( SED_Collection ):
    def __init__( self, snid=None, pointings=None, scas=None, mjds=None, isstar=False ):
        if ( snid is None ) or ( pointings is None ) or ( scas is None ) or ( mjds is None ):
            raise ValueError( "Must specify all of snid, pointings, scas, mjds" )

        self.snid = None
        
        if isstar:
            # Load the star's SED into self.sed
        else:
            # Write code to load in all the requisite SEDs into dictionary self.seds
            # Dictionary is indexed by mjd, value is a galsim SED
            # Also make a  self.mjds that's a sorted array of available SEDs

    def get_sed( self, snid=None, mjd=None ):
        assert snid == self.snid

        # Write code to find the closest mjd in the array of self.mjds
        # Return self.seds[that_mjd]

