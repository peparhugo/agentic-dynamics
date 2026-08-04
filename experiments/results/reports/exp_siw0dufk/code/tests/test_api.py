import json


def test_shorten_and_redirect(client):
    rv = client.post('/shorten', json={'url': 'http://example.com'})
    assert rv.status_code == 201
    data = rv.get_json()
    assert 'code' in data
    code = data['code']

    # redirect
    r = client.get('/' + code, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers['Location'] == 'http://example.com'

    # analytics
    a = client.get('/analytics/' + code)
    assert a.status_code == 200
    ad = a.get_json()
    assert ad['clicks'] == 1


def test_rate_limit(client):
    env = {'REMOTE_ADDR': '9.9.9.9'}
    # rate limit set to 3 in conftest
    for i in range(3):
        r = client.post('/shorten', json={'url': f'http://example.com/{i}'}, environ_overrides=env)
        assert r.status_code == 201
    # next should be 429
    r = client.post('/shorten', json={'url': 'http://example.com/blocked'}, environ_overrides=env)
    assert r.status_code == 429


def test_custom_code_conflict(client):
    r = client.post('/shorten', json={'url': 'http://a.com', 'custom_code': 'mycode'})
    assert r.status_code == 201
    r2 = client.post('/shorten', json={'url': 'http://b.com', 'custom_code': 'mycode'})
    assert r2.status_code == 409


def test_multiple_clicks_recorded(client):
    r = client.post('/shorten', json={'url': 'http://clickme.test'})
    assert r.status_code == 201
    code = r.get_json()['code']
    for _ in range(5):
        rr = client.get('/' + code, headers={'User-Agent': 'pytest-agent'})
        assert rr.status_code == 302
    a = client.get('/analytics/' + code)
    ad = a.get_json()
    assert ad['clicks'] == 5
    assert len(ad['recent']) == 5
