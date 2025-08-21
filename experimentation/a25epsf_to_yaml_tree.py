import pathlib
from a25epsf_to_yaml import a25epsf_to_yaml

def dodir( indir, outdir, clobber=False ):
    indir = pathlib.Path( indir )
    outdir = pathlib.Path( outdir )
    subdirs = [ x for x in indir.iterdir() if x.is_dir() ]
    for subdir in subdirs:
        outsubdir = outdir / subdir.name
        if outsubdir.exists() and not outsubdir.is_dir():
            raise RuntimeError( f"{outsubdir.resolve()} exists but is not a directory!" )
        outsubdir.mkdir( parents=True, exist_ok=True )
        dodir( subdir, outsubdir )

    for psf in indir.glob( "*.psf" ):
        outpath = outdir / psf.name
        a25epsf_to_yaml( psf, outpath, clobber=clobber )


def main():
    parser = argparse.ArgumentParser( 'a25epsf_to_yaml',
                                      decsription=( "Convert all A25ePSF files in a directory tree from pickle "
                                                    "files to the yaml format needed by snappl.psf.A25ePSF" ) )
    parser.add_argument( "indir", help="Base input directory" )
    parser.add_argument( "outdir", help="Base output directory" )
    parser.add_argument( "--clobber", action='store_true', default=False, help="Overwrite existing files" )
    args = parser.parse_args

    dodir( args.indir, args.outdir, clobber=args.clobber )

# ======================================================================
if __name__ == "__main__":
    main()

