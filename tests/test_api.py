def make_scan(client, account_id="123456789012", region="us-east-1"):
    r = client.post("/scans", json={"account_id": account_id, "region": region})
    assert r.status_code == 201
    return r.json()


def make_resource(client, scan_id, **overrides):
    body = {
        "resource_type": "ec2_instance",
        "resource_id": "i-1",
        "name": "web",
        "config": {},
        "monthly_cost_usd": 10,
    }
    body.update(overrides)
    r = client.post(f"/scans/{scan_id}/resources", json=body)
    assert r.status_code == 201
    return r.json()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["database"] == "connected"


def test_create_and_get_scan(client):
    scan = make_scan(client)
    r = client.get(f"/scans/{scan['id']}")
    assert r.status_code == 200
    assert r.json()["region"] == "us-east-1"


def test_invalid_account_id_is_rejected(client):
    r = client.post("/scans", json={"account_id": "abc", "region": "us-east-1"})
    assert r.status_code == 422


def test_missing_scan_returns_404(client):
    assert client.get("/scans/999").status_code == 404


def test_negative_cost_is_rejected(client):
    scan = make_scan(client)
    r = client.post(
        f"/scans/{scan['id']}/resources",
        json={"resource_type": "s3_bucket", "resource_id": "b", "monthly_cost_usd": -5},
    )
    assert r.status_code == 422


def test_resource_filter_by_type(client):
    scan = make_scan(client)
    make_resource(client, scan["id"], resource_type="ec2_instance", resource_id="i-1")
    make_resource(client, scan["id"], resource_type="s3_bucket", resource_id="b-1")
    r = client.get(f"/scans/{scan['id']}/resources", params={"resource_type": "s3_bucket"})
    assert r.status_code == 200
    assert [x["resource_id"] for x in r.json()] == ["b-1"]


def test_add_and_list_dependency(client):
    scan = make_scan(client)
    server = make_resource(client, scan["id"], resource_id="i-1")
    sg = make_resource(client, scan["id"], resource_type="security_group", resource_id="sg-1")
    body = {
        "from_resource_id": server["id"],
        "to_resource_id": sg["id"],
        "relationship": "uses_security_group",
    }
    assert client.post(f"/scans/{scan['id']}/dependencies", json=body).status_code == 201
    deps = client.get(f"/scans/{scan['id']}/dependencies").json()
    assert len(deps) == 1
    assert deps[0]["relationship"] == "uses_security_group"


def test_duplicate_dependency_returns_409(client):
    scan = make_scan(client)
    a = make_resource(client, scan["id"], resource_id="i-1")
    b = make_resource(client, scan["id"], resource_id="i-2")
    body = {"from_resource_id": a["id"], "to_resource_id": b["id"], "relationship": "uses"}
    assert client.post(f"/scans/{scan['id']}/dependencies", json=body).status_code == 201
    assert client.post(f"/scans/{scan['id']}/dependencies", json=body).status_code == 409


def test_self_dependency_returns_422(client):
    scan = make_scan(client)
    a = make_resource(client, scan["id"])
    body = {"from_resource_id": a["id"], "to_resource_id": a["id"], "relationship": "uses"}
    assert client.post(f"/scans/{scan['id']}/dependencies", json=body).status_code == 422


def test_dependency_across_scans_returns_404(client):
    scan1, scan2 = make_scan(client), make_scan(client)
    a = make_resource(client, scan1["id"], resource_id="i-1")
    b = make_resource(client, scan2["id"], resource_id="i-2")
    body = {"from_resource_id": a["id"], "to_resource_id": b["id"], "relationship": "uses"}
    assert client.post(f"/scans/{scan1['id']}/dependencies", json=body).status_code == 404

def test_scan_summary(client):
    scan = make_scan(client)
    make_resource(client, scan["id"], resource_id="i-1", monthly_cost_usd=10)
    make_resource(client, scan["id"], resource_type="s3_bucket",
                  resource_id="b-1", monthly_cost_usd=5.5)

    r = client.get(f"/scans/{scan['id']}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["resource_count"] == 2
    assert body["total_monthly_cost_usd"] == 15.5
    assert body["by_type"] == {"ec2_instance": 1, "s3_bucket": 1}


def test_summary_missing_scan_returns_404(client):
    assert client.get("/scans/999/summary").status_code == 404

def test_creation_order_endpoint(client):
    scan = make_scan(client)
    server = make_resource(client, scan["id"], resource_id="i-1", name="web-server")
    sg = make_resource(client, scan["id"], resource_type="security_group",
                       resource_id="sg-1", name="open-ssh")
    client.post(
        f"/scans/{scan['id']}/dependencies",
        json={"from_resource_id": server["id"], "to_resource_id": sg["id"],
              "relationship": "uses_security_group"},
    )
    r = client.get(f"/scans/{scan['id']}/creation-order")
    assert r.status_code == 200
    names = [x["name"] for x in r.json()]
    assert names.index("open-ssh") < names.index("web-server")


def test_creation_order_cycle_returns_409(client):
    scan = make_scan(client)
    a = make_resource(client, scan["id"], resource_id="i-1")
    b = make_resource(client, scan["id"], resource_id="i-2")
    for src, dst in [(a, b), (b, a)]:
        client.post(
            f"/scans/{scan['id']}/dependencies",
            json={"from_resource_id": src["id"], "to_resource_id": dst["id"],
                  "relationship": "uses"},
        )
    assert client.get(f"/scans/{scan['id']}/creation-order").status_code == 409

def test_summary_cache_is_filled_and_invalidated(client, monkeypatch):
    from app import cache

    store = {}
    monkeypatch.setattr(cache, "get_json", lambda key: store.get(key))
    monkeypatch.setattr(cache, "set_json", lambda key, value, ttl=300: store.__setitem__(key, value))
    monkeypatch.setattr(cache, "delete", lambda *keys: [store.pop(k, None) for k in keys])

    scan = make_scan(client)
    make_resource(client, scan["id"], monthly_cost_usd=10)
    key = f"scan:{scan['id']}:summary"

    client.get(f"/scans/{scan['id']}/summary")
    assert key in store                      # the first call fills the cache
    assert store[key]["resource_count"] == 1

    make_resource(client, scan["id"], resource_id="i-2", monthly_cost_usd=5)
    assert key not in store                  # adding a resource clears it
    assert client.get(f"/scans/{scan['id']}/summary").json()["resource_count"] == 2

def test_resource_impact(client):
    scan = make_scan(client)
    server = make_resource(client, scan["id"], resource_id="i-1", name="web-server")
    sg = make_resource(client, scan["id"], resource_type="security_group",
                       resource_id="sg-1", name="open-ssh")
    client.post(
        f"/scans/{scan['id']}/dependencies",
        json={"from_resource_id": server["id"], "to_resource_id": sg["id"],
              "relationship": "uses_security_group"},
    )
    r = client.get(f"/scans/{scan['id']}/resources/{sg['id']}/impact")
    assert r.status_code == 200
    assert [x["name"] for x in r.json()["affected"]] == ["web-server"]
    assert client.get(f"/scans/{scan['id']}/resources/999/impact").status_code == 404