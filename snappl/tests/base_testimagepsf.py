import pytest
import time

import numpy as np
import scipy
from astropy.io import fits
from photutils.psf import ImagePSF

from snpit_utils.logger import SNLogger


# This is a test class for tests of image-based PSFs that should all return
# the same results.  The actual classes that instantiate and make the actual
# tests run are (as of this writing) TestOversampledImagePSF and TestPhotutilsImagePSF.
class BaseTestImagePSF:
    __psfclass__ = object

    def test_create( self, testpsf ):
        assert isinstance( testpsf, self.__psfclass__ )
        assert testpsf._data.sum() == pytest.approx( 1., rel=1e-9 )
        # data array was 77×77, we are oversampled by 3x, so nominally
        #  it's 25.7×25.7 on the image.  But, the array size is an integer,
        #  and it floors, so we should get 25
        assert testpsf.stamp_size == 25
        assert testpsf.clip_size == 25
        assert testpsf.oversample_factor == 3
        assert testpsf.x == 3832.
        assert testpsf.y == 255.
        loaded = np.load( 'psf_test_data/testpsfarray.npz' )
        arr = loaded['args']
        assert np.all( arr / arr.sum() == testpsf.oversampled_data )
        # TODO : test that normalize=False works

        @pytest.mark.skip( reason="Comment out the skip to write some files for visual inspection" )
        def test_interactive_write_stamp_to_fits_for_visual_inspection( self, testpsf ):
            fits.writeto( 'test_deleteme_orig.fits', testpsf._data, overwrite=True )
            fits.writeto( 'test_deleteme_resamp.fits', testpsf.get_stamp(), overwrite=True )

    def make_psf_for_test_stamp( self, x=1023, y=511, oversamp=3, sigmax=1.2, sigmay=None ):
        """Create an oversampled PSF with a Gaussian profile centered at (x, y)

        Exactly what that means in terms of stored data will be different for different
        PSF subclasses.  However, in all cases, it should give consistent get_stamp
        behavior.

        Parameters
        ----------
          x, y : float, float
             The position on the source image where the PSF is found

          oversamp : integer
             The oversampling factor.  (Some subclasses,
             e.g. OversampledImagePSF, can handle a float oversamp, but
             some, e.g. photutilsImagePSF, can't.)

          sigmax : float
             1σ width in original image pixels of the Gaussian profile

          sigmay : float
             1σ width in original image pixels of the Gaussian profile
             along the y axis.  Set to sigmax if not passed.

        Returns
        -------
           psf, datacx, datacy

           psf is an object that is of the right subclass of PSF for the
           test being run

           (datacx, datacy) are the expected position of the center of
           mass of the psf on self.oversampled_data.  This will be
           different for different subclasses.
        """

        # Make a 3x oversampled PSF that's a gaussian with sigma 1.2 (in
        # image pixel units, not oversampled units).  2√(2ln2)*1.2 = FWHM of
        # 2.83, so for a radius of 5 FWHMs (to be really anal), we want a
        # 29×29 stamp in image units.
        #
        # 3× oversampled means an 87×87 data array.  87 // 2 = 43
        # 5× oversampled means a 145×145 data array.  145 // 2 = 72
        raise NotImplementedError( f"{self.__class__.__name} needs to implement make_psf_for_test_stamp" )

    def run_test_get_stamp_orientation( self, oversamp=3, sigmax=1.2, sigmay=2.4 ):
        psf, _, _ = self.make_psf_for_test_stamp( oversamp=oversamp, sigmax=sigmax, sigmay=sigmay )
        clip = psf.get_stamp()
        assert clip.sum() == pytest.approx( 1., abs=0.005 )
        cy, cx = scipy.ndimage.center_of_mass( clip )
        assert cy == pytest.approx( 14., abs=0.01 )
        assert cx == pytest.approx( 14., abs=0.01 )

    # "centered" here means the original PSF is centered; we're going to
    #   render it offset
    def run_test_get_stamp_centered_oversampled( self, oversamp=3, sigma=1.2 ):
        psf, _, _ = self.make_psf_for_test_stamp( oversamp=oversamp, sigmax=sigma )

        # If we just get_stamp(), we should get a 29×29 image centered on the middle
        # We don't actually really expect the stamp to be exactly expectedgauss, because
        #   the interpolation in get_stamp() is more sophisticated than just "evaluate
        #   the gaussian at the point".  We should be oversampled enough, though, that
        #   it's damn close.
        clipx = np.arange( -14, 15 )
        clipy = np.arange( -14, 15 )
        expectedgauss = np.exp( -( clipx[np.newaxis,:]**2 + clipy[:,np.newaxis]**2 ) / ( 2. * sigma**2 ) )
        expectedgauss /= expectedgauss.sum()
        clip = psf.get_stamp()
        assert clip.shape == ( 29, 29 )
        assert clip.sum() == pytest.approx( 1, abs=0.005 )
        # Doing an absolute, not a relative, comparison because where the gaussian is
        #   approximately zero, we don't need it to be identically 0
        assert np.all( clip == pytest.approx( expectedgauss, abs=0.001 / ( 29*29 ) ) )

        # Render a bunch that are offset and make sure they center up where
        # expected

        # When the relative position is offset by an integer from the place
        #   we evaluted the pixel at ((1023, 511) in this case), the PSF
        #   should still be centered on the center pixel of the image.
        # NOTICE : when the fractional part is exactly 0.5, the PSF is
        #   centered down and to the left of the center pixel of the clip.
        #   This is as documented in snappl.psf.PSF.get_stamp
        relpos = [ -2.5, -1.8, -1.4, -1.0,  -0.8, -0.1,  0.,  0.1,  0.8, 1.0, 1.4,   1.8,  2.5 ]
        ctrexp = [ 13.5, 14.2, 13.6,   14., 14.2, 13.9, 14., 14.1, 13.8, 14., 14.4, 13.8, 13.5 ]
        # relpos = [ -1.8, -1.4, -1.0,  -0.8, -0.1,  0.,  0.1,  0.8, 1.0, 1.4,   1.8 ]
        # ctrexp = [ 14.2, 13.6,   14., 14.2, 13.9, 14., 14.1, 13.8, 14., 14.4, 13.8 ]

        for xrel, xctr in zip( relpos, ctrexp ):
            for yrel, yctr in zip( relpos, ctrexp ):
                clip = psf.get_stamp( 1023 + xrel, 511 + yrel )
                assert clip.sum() == pytest.approx( 1, abs=0.005 )
                assert clip.shape == ( 29, 29 )
                cy, cx = scipy.ndimage.center_of_mass( clip )
                assert cx == pytest.approx( xctr, abs=0.01 )
                assert cy == pytest.approx( yctr, abs=0.01 )

        # Now try the case where we pass x0 and y0 to get_stamp.

        # A handful of specific cases with non-None x0 and y0 to help the
        #   writer of this test think about all the upcoming for loops.

        # First case: we have a PSF that we want centered three pixels up
        #   and to the right.  We'll pass x0 and y0 as (1023, 511) (which is
        #   the default), and then give x and y as 1026 and 514.  This is *different*
        #   from x=1026, y=514, x0=None, y=None; in that case the PSF would be
        #   centered, because it would determine a different x0 and y0 from what
        #   we pass in this example.

        clip = psf.get_stamp( 1026., 514., x0=1023, y0=511 )
        assert clip.sum() == pytest.approx( 1., abs=0.005 )
        assert clip.shape == ( 29, 29 )
        cy, cx = scipy.ndimage.center_of_mass( clip )
        assert cx == pytest.approx( 14.+3., abs=0.01 )
        assert cy == pytest.approx( 14.+3., abs=0.01 )
        # Uncomment for visual debugging
        # fits.writeto( "test_get_stamp_centered_oversampled_1.fits", clip, overwrite=True )

        # Second case: we're going to put the psf at its standard position
        # of 1023, 511, but then we want the center of the clip to
        # correspond to 1022, 512 on the image.  So, the PSF should be one
        # pixel to the right and one pixel down.

        clip = psf.get_stamp( 1023., 511., x0=1022, y0=512 )
        assert clip.sum() == pytest.approx( 1., abs=0.005 )
        assert clip.shape == ( 29, 29 )
        cy, cx = scipy.ndimage.center_of_mass( clip )
        assert cx == pytest.approx( 14.+1., abs=0.01 )
        assert cy == pytest.approx( 14.-1., abs=0.01 )
        # Uncomment for visual debugging
        # fits.writeto( "test_get_stamp_centered_oversampled_2.fits", clip, overwrite=True )

        # Third case: if we just ask for (x=1023.5, y=511.5), we'll get a
        # PSF centered down and to the left of the center of the clip,
        # because of the whole floor thing.  However, if we also give
        # x0=1023, y0=511, then we should get a PSF centered up and to the
        # right.

        clip = psf.get_stamp( 1023.5, 511.5 )
        assert clip.sum() == pytest.approx( 1., abs=0.005 )
        assert clip.shape == ( 29, 29 )
        cy, cx = scipy.ndimage.center_of_mass( clip )
        assert cx == pytest.approx( 14.-0.5, abs=0.01 )
        assert cy == pytest.approx( 14.-0.5, abs=0.01 )
        # Uncomment for visual debugging
        # fits.writeto( "test_get_stamp_centered_oversampled_3.fits", clip, overwrite=True )
        clip = psf.get_stamp( 1023.5, 511.5, x0=1023, y0=511 )
        assert clip.sum() == pytest.approx( 1., abs=0.005 )
        assert clip.shape == ( 29, 29 )
        cy, cx = scipy.ndimage.center_of_mass( clip )
        assert cx == pytest.approx( 14.+0.5, abs=0.01 )
        assert cy == pytest.approx( 14.+0.5, abs=0.01 )
        # Uncomment for visual debugging
        # fits.writeto( "test_get_stamp_centered_oversampled_4.fits", clip, overwrite=True )

        # Test a whole bunch in a four-loop.  When off is None then we
        #   expect the PSF to be centered on the clip at xctr, yctr (pulled
        #   from the ctrpos array), just as in tests above where we didn't
        #   pass x0 and y0.  Otherwise, it depends on both x and x0 (or y
        #   and y0 as appropriate).
        relpos = [ -2.5, -0.8,  0.,  0.1,  1.4,  1.5 ]
        ctrpos = [ 13.5, 14.2, 14., 14.1, 14.4, 13.5 ]
        off = [ -15, -1, 0, None, 3, 12 ]
        numnear = 0
        numnearish = 0
        numnotnear = 0
        punted = 0
        for xrel, xctr in zip( relpos, ctrpos ):
            for yrel, yctr in zip( relpos, ctrpos ):
                for xoff in off:
                    x0 = 1023 + xoff if xoff is not None else None
                    xpeak = 14. + xrel - xoff if xoff is not None else xctr
                    for yoff in off:
                        y0 = 511 + yoff if yoff is not None else None
                        ypeak = 14. + yrel - yoff if yoff is not None else yctr

                        clip = psf.get_stamp( 1023+xrel, 511+yrel, x0=x0, y0=y0 )
                        assert clip.shape == ( 29, 29 )
                        # ****
                        # For visual debugging.  Warning: writes a metric butt-ton of images.
                        # fits.writeto( f'deteleme_{xrel}_{yrel}_{xoff}_{yoff}.fits', clip, overwrite=True )
                        # ****

                        # If xpeak or ypeak is too close to the edge, then we don't
                        #   expect the sum to be 1, because flux will have slopped
                        #   off of the edge of the clip.  Also, finding the
                        #   center is fraught; scipy.ndiamge.center_of_mass won't
                        #   give us the center, because all the missing flux is
                        #   going to make the formal centroid offset towards
                        #   the center from the peak.  In that case, satisfy
                        #   ourself with making sure that the nominal peak
                        #   pixel is brighter than its neighbors.  (Well...
                        #   except when the fractional part relpos is 0.5, and
                        #   then we look at the two (or four) brightest pixels.)
                        nearishedge = ( xpeak < 3. ) or ( xpeak > 25. ) or ( ypeak < 3. ) or ( ypeak > 25. )
                        nearedge = ( ( ( xpeak < 2. ) or ( xpeak > 26. ) or ( ypeak < 2. ) or ( ypeak > 26. ) )
                                     or
                                     ( ( ( xpeak < 3. ) or ( xpeak > 25. ) )
                                       and
                                       ( ( ypeak < 3. ) or ( ypeak > 25. ) )
                                      )
                                    )
                        if nearedge:
                            numnear += 1
                            assert clip.sum() < 0.98
                            ixpeak = int( np.floor( xpeak + 0.5 ) )
                            iypeak = int( np.floor( ypeak + 0.5 ) )
                            # We're just gonna punt if the peak is off of the edge of the image
                            if ( iypeak >= 1 ) and ( iypeak <= 27 ) and ( ixpeak >= 1 ) and ( ixpeak <= 27 ):
                                if ( ixpeak - xpeak == 0.5 ) and ( iypeak - ypeak == 0.5 ):
                                    assert clip[iypeak, ixpeak] == pytest.approx( clip[iypeak-1, ixpeak], rel=1e-5 )
                                    assert clip[iypeak, ixpeak] == pytest.approx( clip[iypeak, ixpeak-1], rel=1e-5 )
                                    assert clip[iypeak, ixpeak] == pytest.approx( clip[iypeak-1, ixpeak-1], rel=1e-5 )
                                elif ixpeak - xpeak == 0.5:
                                    assert clip[iypeak, ixpeak] == pytest.approx( clip[ iypeak, ixpeak-1], rel=1e-5 )
                                    assert clip[iypeak+1, ixpeak] < clip[iypeak, ixpeak]
                                    assert clip[iypeak-1, ixpeak] < clip[iypeak, ixpeak]
                                    assert clip[iypeak+1, ixpeak-1] < clip[iypeak, ixpeak]
                                    assert clip[iypeak-1, ixpeak-1] < clip[iypeak, ixpeak]
                                elif iypeak - ypeak == 0.5:
                                    assert clip[iypeak, ixpeak] == pytest.approx( clip[ iypeak-1, ixpeak], rel=1e-5 )
                                    assert clip[iypeak, ixpeak+1] < clip[iypeak, ixpeak]
                                    assert clip[iypeak, ixpeak-1] < clip[iypeak, ixpeak]
                                    assert clip[iypeak-1, ixpeak-1] < clip[iypeak, ixpeak]
                                    assert clip[iypeak-1, ixpeak-1] < clip[iypeak, ixpeak]
                                else:
                                    assert clip[iypeak, ixpeak] > clip[iypeak-1, ixpeak]
                                    assert clip[iypeak, ixpeak] > clip[iypeak+1, ixpeak]
                                    assert clip[iypeak, ixpeak] > clip[iypeak, ixpeak+1]
                                    assert clip[iypeak, ixpeak] > clip[iypeak, ixpeak-1]
                            else:
                                punted += 1
                        else:
                            cy, cx = scipy.ndimage.center_of_mass( clip )
                            if nearishedge:
                                numnearish += 1
                                assert clip.sum() == pytest.approx( 0.99, abs=0.01 )
                                assert cx == pytest.approx( xpeak, abs=0.06 )
                                assert cy == pytest.approx( ypeak, abs=0.06 )
                            else:
                                numnotnear += 1
                                assert clip.sum() == pytest.approx( 1., abs=0.005 )
                                assert cx == pytest.approx( xpeak, abs=0.01 )
                                assert cy == pytest.approx( ypeak, abs=0.01 )

        SNLogger.debug( f"test_get_stamp_centered_oversampled: {numnear} near edge ({punted} punted), {numnearish} "
                        f"nearish edge, {numnotnear} not near edge" )


    # Test the scary case where we pass a PSF that's not centered on its natural clip.
    # (Why would you DO that?)
    def run_test_get_stamp_offset_oversampled( self, oversamp=3, sigma=1.2 ):
        n = 0
        t = 0

        psfposfracs = [ 0.3792, 0., 0.5, 0.8 ]
        for xposfrac in psfposfracs:
            xpos = 1023 + xposfrac
            for yposfrac in psfposfracs:
                ypos = 511 + yposfrac
                psf, datacx, datacy = self.make_psf_for_test_stamp( xpos, ypos, oversamp=oversamp, sigmax=sigma )
                # Make sure the raw data array we passed is at the right spot
                xround = np.floor( xpos + 0.5 )
                yround = np.floor( ypos + 0.5 )
                cy, cx = scipy.ndimage.center_of_mass( psf.oversampled_data )
                assert cy == pytest.approx( datacy, abs=0.01*oversamp )
                assert cx == pytest.approx( datacx, abs=0.01*oversamp )


                # If we just get_stamp(), it will get it at the x, y we created with
                t0 = time.perf_counter()
                clip = psf.get_stamp()
                t += time.perf_counter() - t0
                n += 1
                assert clip.shape == ( 29, 29 )
                cy, cx = scipy.ndimage.center_of_mass( clip )
                assert cx == pytest.approx( 14. + (xpos-xround), abs=0.01 )
                assert cy == pytest.approx( 14. + (ypos-yround), abs=0.01 )


                relpos = [ -2.5, -1.0,  -0.8, -0.1,  0.,  0.1,  0.8, 2.5 ]
                ctrexp = [ 13.5,  14.,  14.2, 13.9, 14., 14.1, 13.8, 13.5 ]
                # OMG, N⁴
                for xrel, xctr in zip( relpos, ctrexp ):
                    for yrel, yctr in zip( relpos, ctrexp ):
                        clip = psf.get_stamp( 1023 + xrel, 511 + yrel )
                        assert clip.shape == ( 29, 29 )
                        cy, cx = scipy.ndimage.center_of_mass( clip )
                        assert cx == pytest.approx( xctr, abs=0.01 )
                        assert cy == pytest.approx( yctr, abs=0.01 )

        # OMGOMG, N⁶
        # (Minimize number of cases, and don't bother testing near-the-edge
        #  stuff that got tested for intrinsically centered psfs.)
        psfposfracs = [ 0.3792, 0.8 ]
        for xposfrac in psfposfracs:
            xpos = 1023 + xposfrac
            for yposfrac in psfposfracs:
                ypos = 511 + yposfrac
                psf, _, _ = self.make_psf_for_test_stamp( xpos, ypos, oversamp=oversamp, sigmax=sigma )

                relpos = [ -2.5, -0.1,  0.2 ]
                ctrexp = [ 13.5, 13.9, 14.2 ]
                off = [ -3, 0, None, 2 ]
                for xrel, xctr in zip( relpos, ctrexp ):
                    for yrel, yctr in zip( relpos, ctrexp ):
                        for xoff in off:
                            x0 = 1023 + xoff if xoff is not None else None
                            xpeak = 14. + xrel - xoff if xoff is not None else xctr
                            for yoff in off:
                                y0 = 511 + yoff if yoff is not None else None
                                ypeak = 14. + yrel - yoff if yoff is not None else yctr

                                t0 = time.perf_counter()
                                clip = psf.get_stamp( 1023 + xrel, 511 + yrel, x0=x0, y0=y0 )
                                t += time.perf_counter() - t0
                                n += 1
                                assert clip.shape == ( 29, 29 )
                                cy, cx = scipy.ndimage.center_of_mass( clip )
                                assert cx == pytest.approx( xpeak, abs=0.01 )
                                assert cy == pytest.approx( ypeak, abs=0.01 )

        SNLogger.debug( f"test_get_stamp_offset_oversampled: average get_stamp runtime: {t/n} over {n} runs" )


    def run_test_get_imagepsf( self, testpsf, oversamp=1. ):
        impsf = testpsf.getImagePSF()
        assert isinstance( impsf, ImagePSF )
        assert ( impsf.oversampling == np.array( [ 1, 1 ] ) ).all()

        impsf = testpsf.getImagePSF( imagesampled=False )
        assert isinstance( impsf, ImagePSF )
        assert ( impsf.oversampling == np.array( [ int(oversamp), int(oversamp) ] ) ).all()

        # More?  Maybe run a simple PSF fit with it?
