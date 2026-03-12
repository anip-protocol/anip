def test_jwks_endpoint_returns_valid_jwks(client):
    resp = client.get("/.well-known/jwks.json")
    assert resp.status_code == 200
    jwks = resp.json()
    assert "keys" in jwks
    assert len(jwks["keys"]) == 2
    for key in jwks["keys"]:
        assert key["kty"] == "EC"
        assert key["crv"] == "P-256"
        assert key["alg"] == "ES256"
        assert "d" not in key  # no private material
    uses = {k["use"] for k in jwks["keys"]}
    assert uses == {"sig", "audit"}


def test_jwks_is_stable_across_requests(client):
    resp1 = client.get("/.well-known/jwks.json")
    resp2 = client.get("/.well-known/jwks.json")
    assert resp1.json() == resp2.json()
