import os
import pytest
import pathlib

from snappl.config import Config
from snappl.image import Image, FITSImage, FITSImageStdHeaders, CompressedFITSImage
from snappl.image import OpenUniverse2024FITSImage, RomanDatamodelImage
from snappl.segmap import SegmentationMap
from snappl.lightcurve import Lightcurve
from snappl.spectrum1d import Spectrum1d


# Try to make sure that all subclasses of PathedObject are behaving properly

class PathedObjectTestBase:
    def test_default_case( self ):
        obj = self._class( filepath="foo/bar", **self._necessary_extra_args )
        assert obj.filepath == pathlib.Path( "foo/bar" )
        assert obj.full_filepath == obj.base_path / obj.filepath
        assert not obj._no_base_path
        assert obj.base_path == self._expected_base_path

        obj = self._class( full_filepath=self._expected_base_path / "foo/bar", **self._necessary_extra_args )
        assert obj.filepath == pathlib.Path( "foo/bar" )
        assert obj.full_filepath == obj.base_path / obj.filepath
        assert not obj._no_base_path
        assert obj.base_path == self._expected_base_path

        obj = self._class( filepath="foo/bar", full_filepath=self._expected_base_path / "foo/bar",
                           **self._necessary_extra_args )
        assert obj.filepath == pathlib.Path( "foo/bar" )
        assert obj.full_filepath == obj.base_path / obj.filepath
        assert not obj._no_base_path
        assert obj.base_path == self._expected_base_path

        # Fails

        with pytest.raises( ValueError, match=( r"base_path is .*, but full_filepath .* "
                                                r"cannot be made relative to that" ) ):
            obj = self._class( full_filepath="foo/bar", **self._necessary_extra_args )

        with pytest.raises( ValueError, match=( r"base_path is .*, but full_filepath .* "
                                                r"cannot be made relative to that" ) ):
            obj = self._class( full_filepath="/kitten/foo/bar", **self._necessary_extra_args )


    def test_no_base_path( self ):
        with pytest.raises( ValueError, match=r"Cannot specify a base_path \(or base_dir\) if no_base_path is True" ):
            obj = self._class( base_dir="/foo", no_base_path=True, **self._necessary_extra_args )
        with pytest.raises( ValueError, match=r"Cannot specify a base_path \(or base_dir\) if no_base_path is True" ):
            obj = self._class( base_path="/foo", no_base_path=True, **self._necessary_extra_args )

        obj = self._class( filepath="foo/bar", no_base_path=True, **self._necessary_extra_args )
        cwd = pathlib.Path( os.getcwd() )
        assert obj.base_path is None
        assert obj.filepath == cwd / "foo/bar"
        assert obj.full_filepath == obj.filepath

        obj = self._class( filepath="/foo/bar", no_base_path=True, **self._necessary_extra_args )
        assert obj.base_path is None
        assert obj.filepath == pathlib.Path( "/foo/bar" )
        assert obj.full_filepath == obj.filepath

        obj = self._class( full_filepath="foo/bar", no_base_path=True, **self._necessary_extra_args )
        assert obj.base_path is None
        assert obj.filepath == cwd / "foo/bar"
        assert obj.full_filepath == obj.filepath

        obj = self._class( full_filepath="/foo/bar", no_base_path=True, **self._necessary_extra_args )
        assert obj.base_path is None
        assert obj.filepath == pathlib.Path( "/foo/bar" )
        assert obj.full_filepath == obj.filepath

    def test_custom_base_path( self ):
        obj = self._class( filepath="foo/bar", base_path="/kitten", **self._necessary_extra_args )
        assert obj.base_path == pathlib.Path( "/kitten" )
        assert obj.filepath == pathlib.Path( "foo/bar" )
        assert obj.full_filepath == pathlib.Path( "/kitten/foo/bar" )

        obj = self._class( filepath="foo/bar", base_dir="/kitten", **self._necessary_extra_args )
        assert obj.base_path == pathlib.Path( "/kitten" )
        assert obj.filepath == pathlib.Path( "foo/bar" )
        assert obj.full_filepath == pathlib.Path( "/kitten/foo/bar" )

        obj = self._class( base_path="/kitten", full_filepath="/kitten/foo/bar", **self._necessary_extra_args )
        assert obj.base_path == pathlib.Path( "/kitten" )
        assert obj.filepath == pathlib.Path( "foo/bar" )
        assert obj.full_filepath == pathlib.Path( "/kitten/foo/bar" )

        obj = self._class( base_path="/kitten", filepath="foo/bar", full_filepath="/kitten/foo/bar",
                           **self._necessary_extra_args )

        # Fails

        with pytest.raises( ValueError, match=( r"base_path is /kitten, but full_filepath /puppy/foo/bar "
                                                r"cannot be made relative to that" ) ):
            obj = self._class( base_path="/kitten", full_filepath="/puppy/foo/bar", **self._necessary_extra_args )

        with pytest.raises( ValueError, match=( r"Error, filepath is kaglorky, but given base path "
                                                r"/kitten and full path /kitten/foo/bar, this is inconsistent" ) ):
            obj = self._class( base_path="/kitten", full_filepath="/kitten/foo/bar", filepath="kaglorky",
                               **self._necessary_extra_args )




class TestPathedObject_Image( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = Image
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
        self._necessary_extra_args = { 'format': 1 }


class TestPathedObject_FITSImage( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = FITSImage
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
        self._necessary_extra_args = { 'format': 1 }


class TestPathedObject_FITSImageStdHeaders( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = FITSImageStdHeaders
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
        self._necessary_extra_args = { 'format': 1 }


class TestPathedObject_CompressedFITSImage( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = CompressedFITSImage
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
        self._necessary_extra_args = { 'format': 1 }


class TestPathedObject_OpenUniverse2024FITSImage_format1( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = OpenUniverse2024FITSImage
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
        self._necessary_extra_args = { 'format': 1 }


class TestPathedObject_OpenUniverse2024FITSImage_format2( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = OpenUniverse2024FITSImage
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.ou24.images' ) )
        self._necessary_extra_args = { 'format': 2 }


class TestPathedObject_RomanDatamodelImage( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = RomanDatamodelImage
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.images' ) )
        self._necessary_extra_args = { 'format': 100 }


class TestPathedObject_SegmentationMap( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = SegmentationMap
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.segmaps' ) )
        self._necessary_extra_args = {}


class TestPathedObject_Lightcurve( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = Lightcurve
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.lightcurves' ) )
        self._necessary_extra_args = {}


class TestPathedObject_Spectrum1d( PathedObjectTestBase ):
    @pytest.fixture( autouse=True )
    def setup( self ):
        self._class = Spectrum1d
        self._expected_base_path = pathlib.Path( Config.get().value( 'system.paths.spectra1d' ) )
        self._necessary_extra_args = {}
