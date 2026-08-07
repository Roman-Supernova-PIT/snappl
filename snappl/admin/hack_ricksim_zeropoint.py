import pathlib
import re
from matplotlib import pyplot

import numpy as np
import pandas
import photutils.aperture
import photutils.background

from snappl.image import Image
from snappl.imagecollection import ImageCollectionDB
from snappl.logger import SNLogger
from snappl.utils import asUUID

# apers=[2, 3, 5, 10, 15, 20, 25, 30]

def get_image_zeropoint( image, apers=[2, 3, 5, 10, 15, 20, 25, 30], confusionrad=45, minstars=50,
                         plotzp=False, plotcog=False, omgplots=False ):
    if not isinstance( image, Image ):
        imageid = asUUID( image )
        imcol = ImageCollectionDB()
        image = imcol.get_image( imageid )
    SNLogger.info( f"Working on {image.filepath}" )

    bg = photutils.background.Background2D( image.data, 500 )
    bgsub = image.data - bg.background

    mat = re.search( r'roll(\d\d)/SNPIT_(.*)_L2.asdf$', str(image.filepath) )
    if mat is None:
        raise ValueError( f"Failed to parse {image.filepath}" )
    truthpath = ( pathlib.Path( '/ricksims/output_images_2026-08_LBNL_mtg' )
                  / f"DEEP_18SCA_RA9.5_DEC-44_ROLL{mat.group(1)}" / f"TRUTH_{mat.group(2)}_L1.dat.gz" )
    truth = pandas.read_csv( truthpath )
    stars = truth[ truth.label == 'STAR' ]

    # omg n²
    dx = stars.x_det.values[:, np.newaxis] - truth.x_det.values[np.newaxis, :]
    dy = stars.y_det.values[:, np.newaxis] - truth.y_det.values[np.newaxis, :]
    rad = np.sqrt( dx*dx + dy*dy )
    rad.sort( axis=1 )
    if not all( rad[:, 0] == 0. ):
        raise RuntimeError( "I am surprised." )
    rad = rad[:, 1]
    unconfusedstars = stars.iloc[ np.where(rad > confusionrad)[0] ]
    SNLogger.info( f"{len(unconfusedstars)} of {len(stars)} are unconfused." )
    if len(unconfusedstars) < 30:
        SNLogger.debug( "...which is not enough" )
        raise ValueError( "Not enough unconfused stars!" )

    positions = [ ( s.x_det, s.y_det ) for s in unconfusedstars.itertuples() ]
    apphot = []

    for aprad in apers:
        aps = photutils.aperture.CircularAperture( positions, aprad )
        apphot.append( photutils.aperture.aperture_photometry( bgsub, aps, error=image.noise ) )

    fluxen = np.array( [ [ apphot[i]['aperture_sum'][j] for j in range(len(positions)) ]
                         for i in range(len(apers)) ] )
    dfluxen = np.array( [ [ apphot[i]['aperture_sum_err'][j] for j in range(len(positions)) ]
                          for i in range(len(apers)) ] )
    # Making the rash assumption that if the biggest aperture is not nan, none of them will be
    keep = ( ~np.isnan(fluxen[-1]) ) & ( ~np.isnan(dfluxen[-1]) ) & ( (fluxen[-1] / dfluxen[-1]) > 3 )
    mags = unconfusedstars.iloc[ keep ].mag.values
    fluxrats = fluxen[ :, keep ] / fluxen[ -1, keep ]
    dfluxrats = np.sqrt( ( dfluxen[:, keep] / fluxen[-1, keep] )**2 +
                         ( dfluxen[-1, keep] * fluxen[:, keep] / ( fluxen[-1, keep]**2 ) )**2 )
    sn = fluxen[ :, keep ] / dfluxen[ :, keep ]
    zpraw = mags[np.newaxis, :] + 2.5 * np.log10( fluxen[:, keep] )
    dzpraw = 2.5 / np.log(10) * np.fabs( dfluxen[:, keep] / fluxen[:, keep] )
    SNLogger.info( f"{len(fluxrats[0])} stars are S/N>5 in smallest aperture and non-nan" )

    # Figure out aperture corrections

    meanfluxrat = []
    dfluxrat = []
    sigfluxrat = []
    # 3 iterations of outlier rejection
    for i in range( fluxrats.shape[0] ) :
        # Start by rejecting at the median of the highest-sn things to use as the center for our rejection
        sortedsn = sn[i].copy()
        sortedsn.sort()
        sncut = 20. if len(sortedsn) < 11 else sortedsn[-11]
        tmpmean = np.median( fluxrats[i, sn[i] >= sncut] )
        for sigrej in [ 5., 5., 3. ]:
            userat = np.fabs( ( fluxrats[i] - tmpmean ) / dfluxrats[i] ) < sigrej
            # Thereafer, reject relative to the previous iteration's weighted mean
            tmpmean = ( ( fluxrats[i, userat] / (dfluxrats[i, userat]**2) ).sum()
                        / ( 1. / ( dfluxrats[i, userat]**2) ).sum()
                       )

        SNLogger.debug( f"For aperture {apers[i]}, used {userat.sum()} flux ratios to find mean" )
        meanfluxrat.append( tmpmean )
        dfluxrat.append( np.sqrt( 1. / ( 1. / ( dfluxrats[i, userat]**2) ).sum() ) )
        sigfluxrat.append( fluxrats[i, userat].std() )

    # Get zeropoint using largest aperture
    # Again, outlier rejection
    sn = fluxen[-1, keep] / dfluxen[-1, keep]
    sortedsn = sn.copy()
    sncut = 20. if len(sortedsn) < 11 else sortedsn[-11]
    tmpmean = np.median( zpraw[-1, sn >= sncut] )
    for sigrej in [ 5., 5., 3. ]:
        usemean = np.fabs( ( zpraw[-1, :] - tmpmean ) / dzpraw[-1, :] ) < sigrej
        tmpmean = ( ( zpraw[-1, usemean] / dzpraw[-1, usemean]**2 ).sum() /
                    ( 1. / ( dzpraw[-1, usemean]**2 ) ).sum()
                   )
    zp = tmpmean
    dzp = np.sqrt( 1. / ( 1. / ( dzpraw[-1, usemean]**2 ) ).sum() )

    if omgplots:
        for i in range( len(apers) - 1 ):
            fig = pyplot.Figure( figsize=(10, 6), tight_layout=True )
            ax = fig.add_subplot( 1, 1, 1 )
            ax.set_title( f"wtmean flux(aper={apers[i]}) / flux(aper={apers[-1]}) = "
                          f"{meanfluxrat[i]:.4f} ± {dfluxrat[i]:.4f}" )
            ax.set_xlabel( "mag" )
            ax.set_ylabel( f"flux(aper={apers[i]}) / flux(aper={apers[-1]})" )
            ax.errorbar( mags, fluxrats[i], dfluxrats[i], color='blue', linestyle='none', marker='o' )
            ax.plot( ax.get_xlim(), [ meanfluxrat[i], meanfluxrat[i] ], color='grey', linestyle='dashed' )
            # ax.set_ylim( meanfluxrat[i] - sigfluxrat[i], 1. + sigfluxrat[i] )
            ax.set_ylim( 0.6, 1.2 )
            fig.savefig( f'{pathlib.Path(image.filepath).name}_aper{apers[i]}_ratios.png' )
            pyplot.close( fig )

    if plotcog:
        fig = pyplot.Figure( figsize=(10, 6), tight_layout=True )
        ax = fig.add_subplot( 1, 1, 1 )
        ax.set_xlabel( "Aper r (pix)" )
        ax.set_ylabel( f"wtmean flux(aper=r) / flux(aper={apers[-1]})" )
        ax.errorbar( apers, meanfluxrat, dfluxrat, color='blue', linestyle='none', marker='o' )
        ax.plot( ax.get_xlim(), [ 1.0, 1.0 ], color='grey', linestyle='dashed' )
        ax.set_ylim( 0.6, 1.05 )
        fig.savefig( f'{pathlib.Path(image.filepath).name}_cog.png' )
        pyplot.close( fig )

    if plotzp:
        fig = pyplot.Figure( figsize=(10, 6), tight_layout=True )
        ax =fig.add_subplot( 1, 1, 1 )
        ax.set_title( f"zp = {zp:.4f} ± {dzp:.4f}" )
        ax.set_xlabel( "mag" )
        ax.set_ylabel( "zp" )
        ax.errorbar( mags, zpraw[-1], dzpraw[-1], color='blue', linestyle='none', marker='o' )
        ax.plot( ax.get_xlim(), [ zp, zp ], color='grey', linestyle='dashed' )
        ax.set_ylim( zp - 1, zp + 1 )
        fig.savefig( f'{pathlib.Path(image.filepath).name}_zp.png' )
        ax.set_ylim( zp - 0.2, zp + 0.2 )
        fig.savefig( f'{pathlib.Path(image.filepath).name}_zpzoom.png' )
        pyplot.close( fig )

    return zp, dzp


# ======================================================================

def main():
    imgs = Image.find_images( provenance_tag='ricksim202608', process='load_ricksim',
                              mjd_min=60689.5, mjd_max=60690.5 )
    get_image_zeropoint( imgs[0], omgplots=True, plotcog=True, plotzp=True )


# ======================================================================
if __name__ == "__main__":
    main()
