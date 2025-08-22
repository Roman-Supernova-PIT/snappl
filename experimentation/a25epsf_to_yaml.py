import argparse
import pathlib
import yaml
import base64
import pickle


def a25epsf_to_yaml( infile, outfile, clobber=False ):
    outfile = pathlib.Path( outfile )
    if ( not clobber) and outfile.exists():
        raise RuntimeError( f"{outfile} exists, not overwriting" )

    with open( infile, 'rb' ) as ifp:
        psf_obj = pickle.load( ifp )

    # A25ePSF in snappl wants the oversampled data to be normalized such that its sm
    #   is the total flux encosed in the square.  The PSFs from the A25ePSF paper
    #   are normalized to oversampling_factor².

    data = psf_obj['psf'].data / ( psf_obj['psf'].oversampling[0] ** 2 )

    out = { 'x0': float( psf_obj['x_cen'] ),
            'y0': float( psf_obj['y_cen'] ),
            'oversamp': int( psf_obj['psf'].oversampling[0] ),
            'shape0': psf_obj['psf'].data.shape[0],
            'shape1': psf_obj['psf'].data.shape[1],
            'dtype': str( psf_obj['psf'].data.dtype ),
            'data': base64.b64encode( data.tobytes() ).decode( 'utf-8' ) }


    yaml.dump( out, open( outfile, 'w' ) )


def main():
    parser = argparse.ArgumentParser( 'a25epsf_to_yaml',
                                      description=( "Convert an A25ePSF pickle file to the yaml format "
                                                    "needed by snappl.psf.A25ePSF" ) )
    parser.add_argument( 'infile', help="Input pickle file" )
    parser.add_argument( 'outfile', help="Output yaml file" )
    args = parser.parse_args()

    a25epsf_to_yaml( args.infile, args.outfile )


# ======================================================================
if __name__ == "__main__":
    main()
