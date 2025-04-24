# Run this example in this directory with 
#    SNAPPL_CONFIG=config_example.yaml python config_example.py
#
# then try
#    SNAPPL_CONFIG=config_example.yaml python config_example.py --help
#
# then try
#    SNAPPL_CONFIG=config.example.yaml python config_example.py --swallow-african_or_european European

import sys
import pathlib
import argparse

# This is a little bit ugly, but so that this example will work "in place"
# we make sure that the directory where config.py is found is in our
# PYTHONPATH.  Do NOT do this in your own code.  Make sure that things
# are installed right, and that the PYTHONPATH includes all the snappl
# path
sys.path.insert( 0, str( pathlib.Path(__file__).parent.parent ) )
from snappl.config import Config


def main():
    cfg = Config.get()

    parser = argparse.ArgumentParser( 'config_example.py', description='Demonstrate config' )
    parser.add_argument( '-g', '--gratuitous', default='not_given', help="Your own argument" )
    cfg.augment_argparse( parser )
    args = parser.parse_args()
    cfg.parse_args( args )

    print( f"Gratuitous is {args.gratuitous}" )

    # Examples of extracting config values
    
    print( f"cfg.value('cat') is {cfg.value('cat')}" )
    print( f"cfg.value('swallow.unladen.airspeed') is {cfg.value('swallow.unladen.airspeed')} "
           f"with units {cfg.value('swallow.unladen.airspeed_units')}" )
    birdtype = cfg.value( 'swallow.african_or_european' )
    qt = "'"
    print( f"cfg.value('swallow.african_or_european') is "
           f"{f'I don{qt}t know that!.... AAAAAAAA!' if birdtype is None else birdtype}" )
    print( f"cfg.value('list') is {cfg.value('list')}" )


if __name__ == "__main__":
    main()
           
