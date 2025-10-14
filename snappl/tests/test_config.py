import pytest
import argparse
import os
import pathlib

from snappl.config import Config

_rundir = pathlib.Path( __file__ ).parent.resolve()


@pytest.fixture( autouse=True )
def config_cleanup():
    # This fixture gives us a blank slate for testing configs, but also
    # restores the original state of the Config class variables so we
    # don't screw up the work of other fixtures (like the init_config
    # autouse session fixture in conftest.py).

    orig_def_def = Config._default_default
    orig_def = Config._default

    # Give us a blank slate in case another fixture already loaded the config

    Config._default = None
    Config._configs= {}

    yield True

    Config._default_default = orig_def_def
    Config._default = orig_def
    # This next one is OK, things that need it will just reload.
    Config._configs = {}


@pytest.fixture
def cfg():
    return Config.get( _rundir / "config_test_data/test.yaml" )


# It would be nice to use this test, but it's not really consistenet
#   with the init_config() autouse fixture.  I haven't figured out
#   a way to meaningfully test this without removing that fixture,
#   and removing that fixture introduces other pain.
@pytest.mark.skip( "This test doesn't work" )
def test_default_default():
    # make sure that when we load a config without parameters,
    # it uses the default config file
    default_config_path = os.getenv( 'SNPIT_CONFIG' )
    assert default_config_path is not None
    assert Config._default_default == str(default_config_path)
    cfg = Config.get()
    assert cfg._path == pathlib.Path( default_config_path ).resolve()


def test_set_default():
    # We want to have no defaults to start
    # (The autouse fixture will clean up the
    # damage we're doing here.)
    Config._default_default = None

    env_exists = 'SNPIT_CONFIG' in os.environ
    if env_exists:
        orig_env = os.getenv( 'SNPIT_CONFIG' )
        del os.environ[ 'SNPIT_CONFIG' ]

    try:
        # Normally, will not set the default
        _ = Config.get( _rundir / "config_test_data/test.yaml" )
        assert Config._default is None

        # Will set the default it we tell it to
        _ = Config.get( _rundir / "config_test_data/test.yaml", setdefault=True )
        assert Config._default == str( ( _rundir / "config_test_data/test.yaml" ).resolve() )

        # Will set the default to something else if we tell it to
        _ = Config.get( _rundir / "config_test_data/testpreload1.yaml", setdefault=True )
        assert Config._default == str( ( _rundir / "config_test_data/testpreload1.yaml" ).resolve() )

        # Reset everything
        Config._default = None
        Config._configs = {}

        # If there's a default default, but we load something else,
        #   make sure the default isn't set.
        Config._default_default = str( ( _rundir / "config_test_data/test.yaml" ).resolve() )
        _ = Config.get( _rundir / "config_test_data/testpreload1.yaml" )
        assert Config._default is None

        # If there's a default default and we just get config,
        #   make sure it gets set to the default.
        cfg = Config.get()
        assert Config._default == Config._default_default
        # ...and make sure we got the exact Config object
        assert cfg is Config._configs[ Config._default ]
        assert cfg._static

        # If we call it again, we get the same object
        cfg2 = Config.get()
        assert cfg is cfg2
    finally:
        if env_exists:
            os.environ['SNPIT_CONFIG'] = orig_env
        elif 'SNPIT_CONFIG' in os.environ:
            del os.environ['SNPIT_CONFIG']


def test_config_path( cfg ):
    assert cfg._path == (_rundir / "config_test_data/test.yaml").resolve()


def test_loading_and_getting( cfg ):
    # preload1dict1 is set in testpreload1 and augmented in testpreload2 and again in test, and testaugment1 and 2
    assert cfg.value( 'preload1dict1.preload1_1val1' ) == '1_1val1'
    assert cfg.value( 'preload1dict1.preload1_1val2' ) == '1_1val2'
    assert cfg.value( 'preload1dict1.preload2_1val1' ) == '2_1val1'
    assert cfg.value( 'preload1dict1.preload2_1val2' ) == '2_1val2'
    assert cfg.value( 'preload1dict1.preload2_1val3' ) == 'main1val3'
    assert cfg.value( 'preload1dict1.main1val3') == 'main1val3'
    assert cfg.value( 'preload1dict1.augment1val1' ) == 'a1_1val1'
    assert cfg.value( 'preload1dict1.augment2val1' ) == 'a2_1val1'
    assert cfg.value( 'preload1dict1' ) == { 'preload1_1val1': '1_1val1',
                                             'preload1_1val2': '1_1val2',
                                             'preload2_1val1': '2_1val1',
                                             'preload2_1val2': '2_1val2',
                                             'preload2_1val3': 'main1val3',
                                             'main1val3': 'main1val3',
                                             'augment1val1': 'a1_1val1',
                                             'augment2val1': 'a2_1val1' }

    # preload1dict2 is set in testpreload1 and not modified
    assert cfg.value( 'preload1dict2.preload1_2val1' ) == '1_2val1'
    assert cfg.value( 'preload1dict2.preload1_2val2' ) == '1_2val2'
    assert cfg.value( 'preload1dict2' ) == { 'preload1_2val1': '1_2val1', 'preload1_2val2': '1_2val2' }

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
    assert cfg.value( 'replpreload1dict1.replpreload1_1val2' ) == '2_1val2'
    assert cfg.value( 'replpreload1dict1.replpreload2_1val3' ) == '2_1val3'

    # replpreload1dict2 is a dict in testreplpreload1 and destrictively appended in testreplpreload2 and test.yaml
    assert cfg.value( 'replpreload1dict2.replpreload1_2val1' ) == 'main1'
    assert cfg.value( 'replpreload1dict2.replpreload1_2val2' ) == '1_2val2'
    assert cfg.value( 'replpreload1dict2.replpreload1_2val3' ) == 'main3'
    assert cfg.value( 'replpreload1dict2' ) == { 'replpreload1_2val1': 'main1',
                                                 'replpreload1_2val2': '1_2val2',
                                                 'replpreload1_2val3': 'main3' }

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
    assert cfg.value( 'maindict' ) == { 'mainval1': 'val1', 'mainval2': 'val2', 'mainval3': 'val3',
                                        'bool_value': True, 'false_bool_value': False }
    assert cfg.value( 'maindict.mainval2' ) == 'val2'

    # mainlist1 is in test.yaml and not modified
    assert cfg.value( 'mainlist1' ) == [ 'main1', 'main2', 'main3' ]

    # mainlist2 is in test.yaml and replacd testoverride1
    assert cfg.value( 'mainlist2' ) == [ 'override1', 'override2' ]
    assert cfg.value( 'mainlist2.1') == 'override2'

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
    assert cfg.value( 'nest' ) == { 'nest1': [ { 'nest1a': { 'val': 'foo' } }, 42 ],
                                    'nest2': { 'val': 'bar' } }
    assert cfg.value( 'nest.nest1' ) == [ { 'nest1a': { 'val': 'foo' } }, 42 ]
    assert cfg.value( 'nest.nest1.1' ) == 42
    assert cfg.value( 'nest.nest1.0.nest1a' ) == { 'val': 'foo' }
    assert cfg.value( 'nest.nest1.0.nest1a.val' ) == 'foo'
    assert cfg.value( 'nest.nest2' ) == { 'val': 'bar' }
    assert cfg.value( 'nest.nest2.val' ) == 'bar'

    # augment1dict1 is set in testaugment1 and augmented in testaugment2
    assert cfg.value( 'augment1dict1.augment1val1' ) == 'a1_1val1'
    assert cfg.value( 'augment1dict1.augment2val1' ) == 'a2_1val1'

    # augmemt2dict2 is set in testaugment2 and not modified
    assert cfg.value( 'augment2dict2' ) == { 'augment2val2': 'a2_2val2' }

    # destrapplist is set in testdestrapp1 and added to in destrapplist2
    assert cfg.value( 'destrapplist.0' ) == 'app1_1'
    assert cfg.value( 'destrapplist.1' ) == 'app1_2'
    assert cfg.value( 'destrapplist.2' ) == 'app2_1'
    with pytest.raises( ValueError, match="3 >= 3, the length of the list for destrapplist.3" ):
        _ = cfg.value( 'destrapplist.3' )
    with pytest.raises( ValueError, match="10 >= 3, the length of the list for destrapplist.10" ):
        _ = cfg.value( 'destrapplist.10' )

    # destrappdict is set in testdestrapp1 and modified and added to in testdestrapp2
    assert cfg.value( 'destrappdict.val1' ) == 'app1_1'
    assert cfg.value( 'destrappdict.val2' ) == 'app2_2'
    assert cfg.value( 'destrappdict.val3' ) == 'app2_3'
    assert cfg.value( 'destrappdict' ) == { 'val1': 'app1_1', 'val2': 'app2_2', 'val3': 'app2_3' }

    # desterappascalar1 is set in testdestrapp1 and replaced in testdestrapp2
    assert cfg.value( 'destrappscalar1' ) == 'world'


def test_no_overrides():
    with pytest.raises( RuntimeError, match="Error combining key scalar with mode augment" ):
        _cfg = Config.get( "config_test_data/testfail1.yaml" )

    with pytest.raises( RuntimeError, match="Error combining key preloaddict2.main with mode augment" ):
        _cfg = Config.get( "config_test_data/testfail2.yaml" )

    with pytest.raises( RuntimeError, match="Error combining key mainscalar with mode append" ):
        _cfg = Config.get( "config_test_data/testfail3.yaml" )

    with pytest.raises( RuntimeError, match=("Error combining key maindict with mode append; "
                                             "left is a <class 'dict'> and right is a <class 'list'>" ) ):
        _cfg = Config.get( "config_test_data/testfail4.yaml" )


def test_command_line( cfg ):
    parser = argparse.ArgumentParser()
    parser.add_argument( "--gratuitous", type=int, default=42 )
    cfg.augment_argparse( parser)

    arglist = [ '--mainlist2', 'cat', 'dog', '--mainscalar2', 'arg', '--nest-nest2-val', 'arg',
                '--nest-nest1', 'mouse', 'wombat' ]

    args = parser.parse_args( arglist )

    # Just spot check a few
    assert hasattr( args, "replpreload1scalar2" )
    assert hasattr( args, "mainlist1" )
    assert hasattr( args, "nest_nest2_val" )

    cfg.parse_args( args )

    # Make sure that our things that should have been overridden were overridden

    assert cfg.value( 'mainlist2' ) == [ 'cat', 'dog' ]
    assert cfg.value( 'mainscalar2' ) == 'arg'
    assert cfg.value( 'nest.nest2.val' ) == 'arg'
    assert cfg.value( 'nest.nest1' ) == [ 'mouse', 'wombat' ]


def test_command_line_boolean_not_given( cfg ):
    parser = argparse.ArgumentParser()
    cfg.augment_argparse( parser )
    arglist = []
    args = parser.parse_args( arglist )
    cfg.parse_args( args )
    assert cfg.value( 'maindict.bool_value' )
    assert not cfg.value( 'maindict.false_bool_value' )


def test_command_line_boolean_set_true( cfg ):
    parser = argparse.ArgumentParser()
    cfg.augment_argparse( parser )
    arglist = [ '--maindict-bool_value', '--maindict-false_bool_value' ]
    args = parser.parse_args( arglist )
    cfg.parse_args( args )
    assert cfg.value( 'maindict.bool_value' )
    assert cfg.value( 'maindict.false_bool_value' )


def test_command_line_boolean_set_false( cfg ):
    parser = argparse.ArgumentParser()
    cfg.augment_argparse( parser )
    arglist = [ '--no-maindict-bool_value', '--no-maindict-false_bool_value' ]
    args = parser.parse_args( arglist )
    cfg.parse_args( args )
    assert not cfg.value( 'maindict.bool_value' )
    assert not cfg.value( 'maindict.false_bool_value' )


def test_no_direct_instantiation():
    with pytest.raises( RuntimeError, match="Don't instantiate a Config directly; use configobj=Config.get(...)." ):
        _ = Config()


def test_fieldsep( cfg ):
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


def test_nest( cfg ):
    assert cfg.value( 'nest' ) ==  { 'nest1': [ { 'nest1a': { 'val': 'foo' } }, 42 ],
                                     'nest2': { 'val': 'bar' } }
    assert cfg.value( 'nest.nest1.0.nest1a.val' ) == 'foo'


def test_missing_value_with_default( cfg ):
    with pytest.raises(ValueError, match="Can't find field nest_foo"):
        cfg.value( 'nest_foo' )
    assert cfg.value( 'nest_foo', 'default' ) == 'default'

    with pytest.raises(ValueError, match="Can't find field nest.nest15"):
        cfg.value( 'nest.nest15' )
    assert cfg.value( 'nest.nest15', 15) == 15

    with pytest.raises(ValueError, match="99 >= 2, the length of the list for nest.nest1.99"):
        cfg.value( 'nest.nest1.99' )
    assert cfg.value( 'nest.nest1.99', None) is None

    with pytest.raises(ValueError, match="Can't find field nest.nest1.0.nest1a.foo"):
        cfg.value( 'nest.nest1.0.nest1a.foo' )
    assert cfg.value( 'nest.nest1.0.nest1a.foo', 'bar') == 'bar'


def test_set( cfg ):
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
    with pytest.raises( ValueError, match="Can't find field totallynewvalue" ):
        _ = cfg.value( 'totallynewvalue' )


def test_delete_field( cfg ):
    with pytest.raises( RuntimeError, match="Not permitted to modify static Config object." ):
        cfg.delete_field( 'override1list1' )

    newcfg = Config.get( clone=cfg )

    with pytest.raises( TypeError, match="Can't remove elements of lists: override1list1.0" ):
        newcfg.delete_field( 'override1list1.0' )
    assert newcfg.value( 'override1list1' ) == cfg.value( 'override1list1' )

    with pytest.raises( ValueError, match="Can't find config field does.not.exist to delete it." ):
        newcfg.delete_field( "does.not.exist" )
    newcfg.delete_field( "does.not.exist", missing_ok=True )
    assert newcfg._data == cfg._data

    newcfg.delete_field( 'maindict.mainval2' )
    assert set( newcfg.value( 'maindict' ).keys() ) == { 'bool_value', 'false_bool_value', 'mainval1', 'mainval3' }

    for kw in [ k for k in newcfg._data.keys() if k != 'mainscalar1' ]:
        newcfg.delete_field( kw )
    assert set( newcfg._data.keys() ) == { 'mainscalar1' }
    assert newcfg.value( 'mainscalar1' ) == 'main1'
