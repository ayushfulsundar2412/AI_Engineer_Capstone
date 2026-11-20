import pytest

from app.generation import generate_layers, write_files
from app.ordering import LayerCycleError

SG = {"id": 3, "resource_type": "security_group", "resource_id": "sg-0def456",
      "name": "open-ssh", "app": "shared",
      "config": {"inbound": [{"port": 22, "cidr": "0.0.0.0/0"}]}}
SERVER = {"id": 2, "resource_type": "ec2_instance", "resource_id": "i-0abc123",
          "name": "web-server", "app": "billing",
          "config": {"instance_type": "t3.large", "ami": "ami-0123456789abcdef0"}}
BUCKET = {"id": 1, "resource_type": "s3_bucket", "resource_id": "site-assets",
          "name": "site-assets", "app": "website", "config": {}}
USES_SG = {"from_resource_id": 2, "to_resource_id": 3, "relationship": "uses_security_group"}


def test_each_layer_gets_its_own_folder():
    result = generate_layers("us-east-1", [SERVER, SG, BUCKET], [USES_SG])
    assert set(result.files) == {
        "shared/main.tf", "billing/main.tf", "website/main.tf", "APPLY_ORDER.md",
    }


def test_shared_resources_live_only_in_the_shared_folder():
    files = generate_layers("us-east-1", [SERVER, SG, BUCKET], [USES_SG]).files
    assert 'resource "aws_security_group"' in files["shared/main.tf"]
    assert 'resource "aws_security_group"' not in files["billing/main.tf"]


def test_cross_layer_reference_uses_a_data_source():
    billing = generate_layers("us-east-1", [SERVER, SG], [USES_SG]).files["billing/main.tf"]
    assert 'data "aws_security_group" "open_ssh"' in billing
    assert 'id = "sg-0def456"' in billing
    assert "vpc_security_group_ids = [data.aws_security_group.open_ssh.id]" in billing
    assert "to = aws_security_group" not in billing


def test_shared_is_applied_before_the_layers_that_need_it():
    result = generate_layers("us-east-1", [SERVER, SG, BUCKET], [USES_SG])
    names = [layer["layer"] for layer in result.plan["apply_order"]]
    assert names.index("shared") < names.index("billing")
    assert "`shared`" in result.files["APPLY_ORDER.md"]


def test_same_layer_references_stay_ordinary_resources():
    sg = {**SG, "app": "billing"}
    billing = generate_layers("us-east-1", [SERVER, sg], [USES_SG]).files["billing/main.tf"]
    assert "vpc_security_group_ids = [aws_security_group.open_ssh.id]" in billing
    assert 'data "aws_security_group"' not in billing


def test_resources_without_an_app_go_to_shared():
    loose = {k: v for k, v in BUCKET.items() if k != "app"}
    result = generate_layers("us-east-1", [loose], [])
    assert set(result.files) == {"shared/main.tf", "APPLY_ORDER.md"}


def test_missing_cross_layer_target_is_a_gap():
    nameless = {**SG, "name": None}
    result = generate_layers("us-east-1", [SERVER, nameless], [USES_SG])
    assert any("needs security group" in gap for gap in result.gaps)
    assert "vpc_security_group_ids" not in result.files["billing/main.tf"]


def test_layers_that_need_each_other_are_rejected():
    a = {**BUCKET, "id": 1, "app": "billing", "resource_id": "a-bucket", "name": "a-bucket"}
    b = {**BUCKET, "id": 2, "app": "website", "resource_id": "b-bucket", "name": "b-bucket"}
    loop = [
        {"from_resource_id": 1, "to_resource_id": 2, "relationship": "uses"},
        {"from_resource_id": 2, "to_resource_id": 1, "relationship": "uses"},
    ]
    with pytest.raises(LayerCycleError):
        generate_layers("us-east-1", [a, b], loop)


def test_layer_name_cannot_escape_the_output_folder():
    evil = {**BUCKET, "app": "../evil"}
    with pytest.raises(ValueError):
        generate_layers("us-east-1", [evil], [])


def test_write_files_stays_inside_the_folder(tmp_path):
    out = tmp_path / "out"
    write_files({"shared/main.tf": "ok"}, out)
    assert (out / "shared" / "main.tf").read_text(encoding="utf-8") == "ok"
    with pytest.raises(ValueError):
        write_files({"../escape.txt": "no"}, out)
    assert not (tmp_path / "escape.txt").exists()