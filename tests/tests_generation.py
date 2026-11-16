import pytest

from app.generation import generate_terraform
from app.generation.hcl import hcl_str, safe_name

BUCKET = {"id": 1, "resource_type": "s3_bucket", "resource_id": "company-logs",
          "name": "company-logs", "config": {"versioning": True}}
SG = {"id": 3, "resource_type": "security_group", "resource_id": "sg-0def456",
      "name": "open-ssh", "config": {"inbound": [{"port": 22, "cidr": "0.0.0.0/0"}]}}
SERVER = {"id": 2, "resource_type": "ec2_instance", "resource_id": "i-0abc123",
          "name": "web-server",
          "config": {"instance_type": "t3.large", "ami": "ami-0123456789abcdef0"}}
USES_SG = {"from_resource_id": 2, "to_resource_id": 3, "relationship": "uses_security_group"}


def test_hcl_str_neutralises_interpolation():
    assert hcl_str("a${b}") == '"a$${b}"'
    assert hcl_str("a%{b}") == '"a%%{b}"'
    assert hcl_str('say "hi"') == '"say \\"hi\\""'


def test_safe_name():
    assert safe_name("Web Server!", "x") == "web_server"
    assert safe_name("123abc", "x") == "r_123abc"
    assert safe_name("!!!", "fallback") == "fallback"
    assert safe_name(None, "fb") == "fb"


def test_bucket_with_versioning_and_import():
    result = generate_terraform("us-east-1", [BUCKET], [])
    text = result.main_tf
    assert 'resource "aws_s3_bucket" "company_logs"' in text
    assert 'bucket = "company-logs"' in text
    assert 'resource "aws_s3_bucket_versioning" "company_logs"' in text
    assert "to = aws_s3_bucket.company_logs" in text
    assert result.gaps == []


def test_security_group_ingress_rule():
    text = generate_terraform("us-east-1", [SG], []).main_tf
    assert "from_port   = 22" in text
    assert 'protocol    = "tcp"' in text
    assert 'cidr_blocks = ["0.0.0.0/0"]' in text


def test_instance_references_group_and_group_comes_first():
    text = generate_terraform("us-east-1", [SERVER, SG], [USES_SG]).main_tf
    assert "vpc_security_group_ids = [aws_security_group.open_ssh.id]" in text
    assert text.index('resource "aws_security_group"') < text.index('resource "aws_instance"')


def test_missing_ami_is_a_gap_not_invented():
    server = {**SERVER, "config": {"instance_type": "t3.large"}}
    result = generate_terraform("us-east-1", [server], [])
    assert "aws_instance" not in result.main_tf
    assert len(result.gaps) == 1 and "ami" in result.gaps[0]


def test_unsupported_type_is_reported():
    lam = {"id": 9, "resource_type": "lambda", "resource_id": "fn", "name": "fn", "config": {}}
    result = generate_terraform("us-east-1", [lam], [])
    assert "not supported" in result.gaps[0]


def test_instance_depending_on_skipped_group_is_reported():
    nameless = {**SG, "name": None}
    result = generate_terraform("us-east-1", [SERVER, nameless], [USES_SG])
    assert "vpc_security_group_ids" not in result.main_tf
    assert any("needs security group" in gap for gap in result.gaps)


def test_injection_in_names_is_escaped():
    evil = {**BUCKET, "resource_id": 'x${file("/etc/passwd")}', "config": {}}
    text = generate_terraform("us-east-1", [evil], []).main_tf
    assert "$${file" in text
    assert '"x${' not in text


def test_invalid_region_is_rejected():
    with pytest.raises(ValueError):
        generate_terraform('us-east-1"; evil', [], [])


def test_output_is_deterministic():
    first = generate_terraform("us-east-1", [SERVER, SG, BUCKET], [USES_SG]).main_tf
    second = generate_terraform("us-east-1", [BUCKET, SG, SERVER], [USES_SG]).main_tf
    assert first == second


def test_empty_scan_gives_header_only():
    text = generate_terraform("us-east-1", [], []).main_tf
    assert 'provider "aws"' in text
    assert 'resource "' not in text