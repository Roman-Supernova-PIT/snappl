import pytest
import sys
import os
import pathlib

_rundir = pathlib.Path( __file__ ).parent.resolve()
# Make sure the parent to this directory is in the path
sys.path.insert( 0, str( _rundir.parent ) )
from config import Config

# A note about pytest: Things aren't completely sandboxed.  When I call
# config.Config.get(), it sets Config._default, and that carries over
# from one test to the next even if the call wasn't in a fixture with
# class scope.  (The tests below are ordered with this in mind.)


class TestConfig:
    @pytest.fixture(scope='class')
    def cfg(self):
        # We don't want to set the default config, because the config
        #   here is just for these tests.  Other tests might
        #   need a different config, so make sure that global variables
        #   in the Config class aren't set.
        return Config.get(_rundir / 'test.yaml', setdefault=False)

    @pytest.mark.skip( "Remove this skip if/when the env var is set" )
    def test_default_default( self ):
        # make sure that when we load a config without parameters,
        # it uses the default config file
        default_config_path = os.getenv( 'SNAPPL_CONFIG' )
        assert default_config_path is not None
        assert Config._default_default == str(default_config_path)

    def test_config_path( self, cfg ):
        assert cfg._path == (_rundir / "test.yaml").resolve()

    def test_loading_and_getting( self, cfg ):
        # preload1dict1 is set in testpreload1 and augmented in testpreload2 and again in testaugment1 and 2
        assert cfg.value( 'preload1dict1.preload1_1val1' ) == '1_1val1'
        assert cfg.value( 'preload1dict1.preload1_1val2' ) == '1_1val2'
        assert cfg.value( 'preload1dict1.preload2_1val1' ) == '2_1val1'
        assert cfg.value( 'preload1dict1.preload2_1val2' ) == '2_1val2'
        assert cfg.value( 'preload1dict1.augment1val1' ) == 'a1_1val1'
        assert cfg.value( 'preload1dict1.augment2val1' ) == 'a2_1val1'
        assert cfg.value( 'preload1dict1' ) == { 'preload1_1val1': '1_1val1',
                                                 'preload1_1val2': '1_1val2',
                                                 'preload2_1val1': '2_1val1',
                                                 'preload2_1val2': '2_1val2',
                                                 'augment1val1': 'a1_1val1',
                                                 'augment2val1': 'a2_1val1' }

        # preload1dict2 is set in testpreload1 and not modified
        assert cfg.value( 'preload1dict2.preload1_2val1' ) == '1_2val1'
        assert cfg.value( 'preload1dict2.preload1_2val2' ) == '1_2val2'
        assert cfg.value( 'preload1dict1' ) == { 'preload1_2val1': '1_2val1', 'preload1_2val2': '1_2val2' }

        # preload1list1 is set in testpreload and mot modified
        assert cfg.value( 'preload1list1' ) == [ '1_1val0', '1_1val1', '1_1val2' ]
        assert cfg.value( 'preload1list1.0' ) == '1_1val0'
        assert cfg.value( 'preload1list1.1' ) == '1_1val1'
        assert cfg.value( 'preload1list1.2' ) == '1_1val2'

        # preload1scalar1 is set in testpreload1
        assert cfg.value( 'preload1scalar1' ) == '1scalar1'

        # preload1scalar2 is set in testpreload1 but overridden in testoverride1
        assert cfg.value( 'preload1scalar2' ) == 'override2'

        # preload2scalar2 is set in testpreload2
        assert cfg.value( 'preload2scalar2' ) == '2scalar2'

        # reppreload1dict1 is set in testreppreload1 and destructively appended in testreplpreload2
        assert cfg.value( 'replpreload1dict1.replpreload1_1val1' ) == '1_1val1'
        assert cfg.value( 'replpreload1dict1.replpreload1_1val1' ) == '2_1val2'
        assert cfg.value( 'replpreload1dict1.replpreload2_1val3' ) == '2_1val3'

        # replpreload1dict2 is a dict in testreplpreload1 and destrictively appended in test.yaml
        assert cfg.value( 'replpreload1dict2.replpreload1_2val1' ) == 'main1'
        assert cfg.value( 'replpreload1dict2.replpreload1_2val2' ) == '1_2val2'
        assert cfg.value( 'replpreload1dict2.replpreload1_2val3' ) == 'main3'
        assert cfg.value( 'replpreload1dict2' ) == { 'replpreload1_2val1': 'main1',
                                                     'replpreload1_2val2': '1_2val2',
                                                     'replprelaod1_2val3': 'main3' }

        # replpreload1list1 is set in testreppreload1 and appended in testreplpreload2 and again in test.yaml
        assert cfg.value( 'replpreload1list1' ) == [ '1_1val0', '1_1val1', '1_1val2',
                                                     '2_1val0', '2_1val1', '2_2val2',
                                                     'main1' ]

        # replpreload1scalar1 is set in replpreload1 but replaced by testreplpreload2
        assert cfg.value( 'replpreload1scalar1' ) == '2scalar1'

        # replpreload1scalar2 is set in replpreload1 but replaced by testprelpreload2 and then again by test.yaml
        assert cfg.value( 'replpreload1scalar2' ) == 'main2'

        # Others not replaced
        assert cfg.value( 'replpreload1scalar3' ) == '1scalar3'
        assert cfg.value( 'replpreload2scalar2' ) == '2scalar2'

        # maindict is in test.yaml and not modified
        assert cfg.value( 'maindict' ) == { 'mainval1': 'val1', 'mainval2': 'val2', 'mainval3': 'val3' }
        assert cfg.value( 'maindict.val2' ) == 'val2'

        # mainlist1 is in test.yaml and not modified
        assert cfg.value( 'mainlist1' ) == [ 'main1', 'main2', 'main3' ]

        # mainlist2 is in test.yaml and added to by testoverride1
        assert cfg.value( 'mainlist2' ) == [ 'main2', 'main2', 'main3', 'override1', 'override2' ]
        assert cfg.value( 'mainlist2.3') == 'override1'

        # mainlist3 is a list in test.yaml but blown away by a scalar in testoverride1
        assert cfg.value( 'mainlist3' ) == 'this_is_not_a_list'

        # mainlist4 is set in test.yaml and added to in testdestrapp1
        assert cfg.value( 'mainlist4' ) == [ 'main1', 'main2', 'app1' ]
        
        # mainlist for is in test.yaml and added to in testdestrapp1.yaml
        assert cfg.value( 'mainlist4' ) == [ 'main1', 'main2', 'app1' ]

        # mainscalar1 is in test.yaml and not modified
        assert cfg.value( 'mainscalar1' ) == 'main1'

        # mainscalar2 is in test.yaml and overridden in testoverride1
        assert cfg.value( 'mainscalar2' ) == 'override1'

        # mainscalar3 is in test.yaml and overridden in testoverride1, and then again in testoverride2
        assert cfg.value( 'mainscalar3' ) == 'override2'

        # Make sure none works
        assert cfg.value( 'mainnull' ) is None

        # Check nesting
        assert isinstance( cfg.value( 'nest' ), dict )
        assert cfg.value( 'nest' ) == { 'nest1': [ { 'nest1': { 'val': 'foo' } }, 42 ],
                                        'nest2': { 'val': 'bar' } }
        assert cfg.value( 'nest.nest1' ) == [ { 'nest1': { 'val': 'foo' } }, 42 ]
        assert cfg.value( 'nest.nest1.1' ) == 42
        assert cfg.value( 'nest.nest1.0.nest1a' ) == { 'val': 'foo' }
        assert cfg.value( 'nest.nest1.1.nest1a.val' ) == 'foo'
        assert cfg.value( 'nest.nest2' ) == { 'val': 'bar' }
        assert cfg.value( 'nest.nest2.val' ) == 'bar'

        # augment1dict1 is set in testaugment1 and augmented in testaugment2
        assert cfg.value( 'augment1dict1.augment1val1' ) == 'a1_1val1'
        assert cfg.value( 'augment1dict1.augment2val1' ) == 'a2_1val1'

        # augmemt2dict2 is set in testaugment2 and not modified
        assert cfg.value( 'augment2dict2' ) == { 'agument2val2': 'a2_2val2' }

        # destrapplist is set in testdestrapp1 and added to in destrapplist2
        assert cfg.value( 'destrapplist.0' ) == 'app1_1'
        assert cfg.value( 'destrapplist.1' ) == 'app1_2'
        assert cfg.value( 'destrapplist.2' ) == 'app2_1'
        with pytest.raises( ValueError, match="3 > 3, the length of the list" ):
            _ = cfg.value( 'destrapplist.3' )
        with pytest.raises( ValueError, match="10 > 3, the length of the list" ):
            _ = cfg.value( 'destrapplist.10' )

        # destrappdict is set in testdestrapp1 and modified and added to in testdestrapp2
        assert cfg.value( 'destrappdict.val1' ) == 'app1_1'
        assert cfg.value( 'destrappdict.val2' ) == 'app2_2'
        assert cfg.value( 'destrappdict.val3' ) == 'app2_3'
        assert cfg.value( 'destrappdict' ) == { 'val1': 'app1_1', 'val2': 'app2_2', 'val3': 'app2_3' }

        # desterappascalar1 is set in testdestrapp1 and replaced in testdestrapp2
        assert cfg.value( 'destrappscalar1' ) == 'world'

    # TODO : tests that things can't override stuff they aren't supposed to be able to
        
    def test_fieldsep( self, cfg ):
        fields, isleaf, curfield, ifield = cfg._fieldsep( 'nest.nest1.0.nest1a' )
        assert isleaf == False
        assert curfield == 'nest'
        assert fields == ['nest', 'nest1', '0', 'nest1a' ]
        assert ifield is None
        fields, isleaf, curfield, ifield = cfg._fieldsep( '0.test' )
        assert isleaf == False
        assert ifield == 0
        fields, isleaf, curfield, ifield = cfg._fieldsep( 'mainlist2' )
        assert isleaf
        fields, isleaf, curfield, ifield = cfg._fieldsep( 'mainscalar1' )
        assert isleaf

    def test_nest(self, cfg):
        assert cfg.value( 'nest' ) ==  { 'nest1': [ { 'nest1a': { 'val': 'foo' } }, 42 ],
                                         'nest2': { 'val': 'bar' } }
        assert cfg.value( 'nest.nest1.0.nest1a.val' ) == 'foo'

    def test_missing_value_with_default(self, cfg):
        with pytest.raises(ValueError, match="Field .* doesn't exist"):
            cfg.value( 'nest_foo' )
        assert cfg.value( 'nest_foo', 'default' ) == 'default'

        with pytest.raises(ValueError, match="Error getting field .*"):
            cfg.value( 'nest.nest15' )
        assert cfg.value( 'nest.nest15', 15) == 15

        with pytest.raises(ValueError, match="Error getting field .*"):
            cfg.value( 'nest.nest1.99' )
        assert cfg.value( 'nest.nest1.99', None) is None

        with pytest.raises(ValueError, match="Error getting field .*"):
            cfg.value( 'nest.nest1.0.nest1a.foo' )
        assert cfg.value( 'nest.nest1.0.nest1a.foo', 'bar') == 'bar'

    def test_set(self, cfg):
        clone = Config.get( cfg._path, static=False )
        assert Config.get( cfg._path ) is cfg
        assert Config.get( cfg._path ) is not clone

        with pytest.raises( RuntimeError, match="Not permitted to modify static Config object." ):
            cfg.set_value( 'mainscalar1', 'this_should_not_work' )
        assert cfg.value( 'mainscalar1' ) != 'this_should_not_work'

        with pytest.raises( TypeError, match="Tried to add a non-integer field to a list." ):
            clone.set_value( 'settest.list.notanumber', 'kitten', appendlists=True )
        with pytest.raises( TypeError, match="Tried to add an integer field to a dict." ):
            clone.set_value( 'settest.0', 'puppy' )
        with pytest.raises( TypeError, match="Tried to add an integer field to a dict." ):
            clone.set_value( 'settest.0.subset', 'bunny' )
        with pytest.raises( TypeError, match="Tried to add an integer field to a dict." ):
            clone.set_value( 'settest.dict.0', 'iguana' )
        with pytest.raises( TypeError, match="Tried to add an integer field to a dict." ):
            clone.set_value( 'settest.dict.2.something', 'tarantula' )

        clone.set_value( 'settest.list.0', 'mouse', appendlists=True )
        assert clone.value('settest.list.2') == 'mouse'
        assert cfg.value('settest.list') == [ 'a', 'b' ]
        clone.set_value( 'settest.list.5', 'mongoose' )
        assert clone.value('settest.list') == [ 'mongoose' ]
        assert cfg.value('settest.list') == [ 'a', 'b' ]

        clone.set_value( 'settest.dict.newkey', 'newval' )
        assert clone.value( 'settest.dict' ) == { 'key1': 'val1',
                                                'key2': 'val2',
                                                'newkey': 'newval' }
        assert 'newkey' not in cfg.value( 'settest.dict' )
        assert clone.value( 'settest.dict.newkey' ) == 'newval'

        clone.set_value( 'settest.dict2', 'scalar' )
        assert clone.value('settest.dict2') == 'scalar'
        assert cfg.value( 'settest.dict2' ) == { 'key1': '2val1', 'key2': '2val2' }

        clone.set_value( 'settest.scalar', 'notathing' )
        assert clone.value('settest.scalar') == 'notathing'
        assert cfg.value( 'settest.scalar' ) == 'thing'

        clone.set_value( 'settest.scalar.thing1', 'thing1' )
        clone.set_value( 'settest.scalar.thing2', 'thing2' )
        assert clone.value('settest.scalar') == { 'thing1': 'thing1', 'thing2': 'thing2' }
        assert cfg.value( 'settest.scalar' ) == 'thing'

        clone.set_value( 'settest.scalar2.0.key', "that wasn't a scalar" )
        assert clone.value('settest.scalar2') == [ { "key": "that wasn't a scalar" } ]
        assert cfg.value( 'settest.scalar2' ) == 'foobar'

        clone.set_value( 'totallynewvalue.one', 'one' )
        clone.set_value( 'totallynewvalue.two', 'two' )
        assert clone.value('totallynewvalue') == { 'one': 'one', 'two': 'two' }
        with pytest.raises( ValueError, match="Field totallynewvalue doesn't exist" ):
            _ = cfg.value( 'totallynewvalue' )



