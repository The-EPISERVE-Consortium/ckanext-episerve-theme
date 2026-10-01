from ckanext.episerve_theme import signing

BASE = "https://doip.example/doip/retrieve/"
SECRET = "link-secret"
NOW = 1_000_000


def test_signature_matches_the_doip_server_test_vector():
    # Same vector as tests/shared/test_signing.py in episerve_doip_server.
    assert signing.sign(SECRET, "Q1", "data.parquet", NOW + 600) == "e90b05f212fb9c17a2cad863061dfbf3aba1830fdb1ba5b946744f35b3b7d1d2"


def test_doip_url_is_signed():
    url = signing.sign_doip_url(BASE + "Q1/data.parquet", BASE, SECRET, ttl=600, now=NOW)
    sig = signing.sign(SECRET, "Q1", "data.parquet", NOW + 600)
    assert url == f"{BASE}Q1/data.parquet?exp={NOW + 600}&sig={sig}"


def test_signature_uses_the_percent_decoded_component():
    url = signing.sign_doip_url(BASE + "Q1/my%20file.parquet", BASE, SECRET, ttl=600, now=NOW)
    assert signing.sign(SECRET, "Q1", "my file.parquet", NOW + 600) in url


def test_other_urls_are_left_alone():
    for url in ["https://elsewhere.example/Q1/data.parquet", BASE + "Q1", BASE + "Q1/", BASE + "Q1/f?x=1", ""]:
        assert signing.sign_doip_url(url, BASE, SECRET, now=NOW) == url


def test_no_secret_means_no_signing():
    assert signing.sign_doip_url(BASE + "Q1/data.parquet", BASE, "", now=NOW) == BASE + "Q1/data.parquet"
