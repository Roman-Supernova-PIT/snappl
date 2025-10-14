import pytest
import os

import numpy as np

from snappl.utils import isSequence, parse_bool, env_as_bool


def test_isSequence():
    assert isSequence( [1] )
    assert isSequence( [1, 2, 3] )
    assert isSequence( (1, 2, 3) )
    assert isSequence( np.array( [1, 2, 3] ) )
    assert not isSequence( 1 )
    assert not isSequence( "a" )
    assert not isSequence( "abcde" )
    assert not isSequence( bytes("abcde", encoding="utf-8") )


def test_parse_bool():
    trues = [ 1, 2, -1, np.int64(1), "1", "true", "True", "TRUE", "yes", "Yes", "YES", True ]
    falses = [ 0, np.int64(0), "false", "False", "FALSE", "no", "No", "NO", False ]
    fails = [ "2", "kittens", ["o", "m", "g"], 1.0, "1.0", np.float32( 1.0 )  ]

    for val in trues:
        assert parse_bool( val )

    for val in falses:
        assert not parse_bool( val )

    for val in fails:
        with pytest.raises( ValueError, match="Cannot parse boolean value from" ):
            parse_bool( val )


def test_env_as_bool():
    trues = [ '1', 'true', 'True', 'TRUE', 'yes', 'Yes', 'YES' ]
    falses = [ '0', 'false', 'False', 'FALSE', 'no', 'No', 'NO' ]
    fails =  [ 'kittens', '1.0' ]

    assert 'TEST_ENV_AS_BOOL' not in os.environ
    try:
        for val in trues:
            os.environ[ 'TEST_ENV_AS_BOOL' ] = val
            assert env_as_bool( 'TEST_ENV_AS_BOOL' )

        for val in falses:
            os.environ[ 'TEST_ENV_AS_BOOL' ] = val
            assert not env_as_bool( 'TEST_ENV_AS_BOOL' )

        for val in fails:
            os.environ[ 'TEST_ENV_AS_BOOL' ] = val
            with pytest.raises( ValueError, match="Cannot parse boolean value from" ):
                env_as_bool( 'TEST_ENV_AS_BOOL' )

    finally:
        del os.environ[ 'TEST_ENV_AS_BOOL' ]
