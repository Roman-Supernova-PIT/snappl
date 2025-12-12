import pytest
from snappl.snappl_http import retry_post


def test_retry_post( dbclient ):
    res = retry_post( 'https://webserver:8080/test/blah', verify=False )
    data = res.json()
    assert isinstance( data, dict )
    assert set( data.keys() ) == { 'param' }
    assert data['param'] == 'blah'

    res = retry_post( 'https://webserver:8080/test/blah', { 'answer': 42 }, verify=False )
    data = res.json()
    assert isinstance( data, dict )
    assert set( data.keys() ) == { 'param', 'json' }
    assert data['param'] == 'blah'
    assert data['json']['answer'] == 42

    with pytest.raises( RuntimeError, match="Got status 404 trying to connect" ):
        retry_post( 'https://webserver:8080/this_endpoint_does_not_exist', retries=3, initsleep=0.2, verify=False )
