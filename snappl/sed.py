__all__ = [ 'SED_collection', 'Flat_SED', 'Single_CSV_SED', 'OU2024_Truth_SED' ]

# Put in necessary imports
import numpy as np
import os
import h5py
import galsim
import pathlib
import pandas as pd


from snappl.config import Config
from snappl.logger import SNLogger


class SED_collection:
    def __init__(self, *args, **kwargs):
        pass

    def get_sed(self, filename=None, snid=None, mjd=None):
        """Return a galsim SED."""
        raise NotImplementedError( f"{self.__class__.__name__} needs to implement get_sed" )


class Flat_SED( SED_collection ):
    def __init__( self ):
        self.sed = galsim.SED( galsim.LookupTable( [1000, 26000], [1, 1], interpolant='linear' ),
                               wave_type='Angstrom', flux_type='fphotons' )

    def get_sed( self, **kwargs):
        return self.sed


class Single_CSV_SED( SED_collection ):
    def __init__( self, csv_file ):
        # READ THE CSV FILE, make a galsim SED in self.sed
        raise NotImplementedError( "Single_CSV_SED is not implemented yet.")

    def get_sed( self, **kwargs ):
        return self.sed


class OU2024_Truth_SED(SED_collection):
    def __init__(self, snid=None, isstar=False):
        # if (snid is None) or (sn_path is None):
        #     raise ValueError("Must specify all of snid, sn_path")

        self.snid = snid
        cfg = Config.get()
        self.sn_path = cfg.value("system.ou24.sn_truth_dir")
        self.isstar = isstar

        if isstar:
            self.lam_array, self.flambda_array = \
                self._ou24_get_star_SED()
        else:
            self.lam_array, self.flambda_array, self.mjd_array = \
                self._ou24_get_SN_SED()

    def get_sed(self, snid=None, mjd=None):
        """Return an SED for the given snid and mjd.
        Inputs:
        snid: the ID of the object
        mjd: the MJD of the observation (only used if this is a SN)

        Returns:
        galsim.SED: the SED for the given snid and mjd, if a supernova, for the ID if a star.
        """
        assert snid == self.snid, "ID does not match the SED collection ID."

        if not self.isstar:
            # If this is a SN, we need to find the closest SED to the given MJD.
            bestindex = np.argmin(np.abs(np.array(self.mjd_array) - mjd))
            max_days_cutoff = 10
            closest_days_away = np.min(np.abs(np.array(self.mjd_array) - mjd))

            if closest_days_away > max_days_cutoff:
                SNLogger.warning(f"WARNING: No SED data within {max_days_cutoff} days of "
                                 + f"date. \n The closest SED is {closest_days_away} days away.")

            return galsim.SED(
                galsim.LookupTable(np.array(self.lam_array), (self.flambda_array[bestindex]), interpolant="linear"),
                wave_type="Angstrom",
                flux_type="fphotons",
            )

        else:
            # If this is a star, we just return the SED
            return galsim.SED(
                galsim.LookupTable(np.array(self.lam_array), (self.flambda_array), interpolant="linear"),
                wave_type="Angstrom",
                flux_type="fphotons",
            )

    def _ou24_open_parquet(self, parq, obj_type="SN", engine="fastparquet"):
        """Convenience function to open a parquet file given its number."""
        path = self.sn_path
        file_prefix = {"SN": "snana", "star": "pointsource"}
        base_name = "{:s}_{}.parquet".format(file_prefix[obj_type], parq)
        file_path = os.path.join(path, base_name)
        df = pd.read_parquet(file_path, engine=engine)
        return df

    def _ou24_find_parquet(self, obj_type="SN"):
        """Find the parquet file that contains a given supernova ID."""
        path = self.sn_path
        ID = self.snid
        files = os.listdir(path)
        SNLogger.debug(f"Looking for parquet files in {path} for {obj_type} with ID {ID}")
        file_prefix = {"SN": "snana", "star": "pointsource"}
        files = [f for f in files if file_prefix[obj_type] in f]
        files = [f for f in files if ".parquet" in f]
        files = [f for f in files if "flux" not in f]

        for f in files:
            pqfile = int(f.split("_")[1].split(".")[0])
            df = self._ou24_open_parquet(pqfile, obj_type=obj_type)
            if ID in df.id.values or str(ID) in df.id.values:
                return pqfile

    def _ou24_get_star_SED(self):
        """Return the appropriate SED for the star.
        Inputs:
        SNID: the ID of the object
        sn_path: the path to the supernova data

        Returns:
        lam: the wavelength of the SED in Angstrom (numpy  array of floats)
        flambda: the flux of the SED units in erg/s/cm^2/Angstrom
                (numpy array of floats)
        """

        filenum = self._ou24_find_parquet(obj_type="star")
        pqfile = self._ou24_open_parquet(filenum, obj_type="star")
        file_name = pqfile[pqfile["id"] == str(self.snid)]["sed_filepath"].values[0]
        fullpath = pathlib.Path(Config.get().value("system.ou24.sims_sed_library")) / file_name
        sed_table = pd.read_csv(fullpath,  compression="gzip", sep=r"\s+", comment="#")
        lam = sed_table.iloc[:, 0]
        flambda = sed_table.iloc[:, 1]
        return np.array(lam), np.array(flambda)

    def _ou24_get_SN_SED(self):
        """Return the appropriate SED for the supernova on the given day.

        Inputs:
        SNID: the ID of the object
        sn_path: the path to the supernova data

        Returns:
        lam: the wavelength of the SED in Angstrom
        flambda: the flux of the SED units in erg/s/cm^2/Angstrom
        """
        filenum = self._ou24_find_parquet(obj_type="SN")
        file_name = "snana" + "_" + str(filenum) + ".hdf5"
        fullpath = os.path.join(self.sn_path, file_name)
        # Setting locking=False on the next line becasue it seems that you can't
        #   open an h5py file unless you have write access to... something.
        #   Not sure what.  The directory where it exists?  We won't
        #   always have that.  It's scary to set locking to false, because it
        #   subverts all kinds of safety stuff that hdf5 does.  However,
        #   because these files were created once in this case, it's not actually
        #   scary, and we expect them to be static.  Locking only matters if you
        #   think somebody else might change the file
        #   while you're in the middle of reading bits of it.
        sed_table = h5py.File(fullpath, "r", locking=False)
        sed_table = sed_table[str(self.snid)]
        flambda = sed_table["flambda"]
        lam = sed_table["lambda"]
        mjd = sed_table["mjd"]

        return np.array(lam), np.array(flambda), np.array(mjd)
