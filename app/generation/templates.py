from app.generation.hcl import hcl_str


def _import_block(tf_type: str, local: str, import_id: str) -> str:
    return f"import {{\n  to = {tf_type}.{local}\n  id = {hcl_str(import_id)}\n}}"


def _s3_bucket(r: dict, local: str, refs: dict):
    bucket = r.get("resource_id")
    if not bucket:
        return [], [f"resource {r['id']}: s3 bucket has no name"]
    blocks = [
        f'resource "aws_s3_bucket" "{local}" {{\n  bucket = {hcl_str(bucket)}\n}}',
        _import_block("aws_s3_bucket", local, bucket),
    ]
    if r.get("config", {}).get("versioning") is True:
        blocks += [
            f'resource "aws_s3_bucket_versioning" "{local}" {{\n'
            f"  bucket = aws_s3_bucket.{local}.id\n"
            "  versioning_configuration {\n"
            '    status = "Enabled"\n'
            "  }\n"
            "}",
            _import_block("aws_s3_bucket_versioning", local, bucket),
        ]
    return blocks, []


def _security_group(r: dict, local: str, refs: dict):
    name = r.get("name")
    if not name:
        return [], [f"resource {r['id']}: security group has no name"]
    cfg = r.get("config", {})
    gaps = []
    lines = [f'resource "aws_security_group" "{local}" {{', f"  name = {hcl_str(name)}"]
    if cfg.get("description"):
        lines.append(f"  description = {hcl_str(cfg['description'])}")
    for rule in cfg.get("inbound", []):
        try:
            port = rule.get("port")
            from_port = int(rule.get("from_port", port))
            to_port = int(rule.get("to_port", port))
            cidr = str(rule["cidr"])
            if not (0 <= from_port <= 65535 and 0 <= to_port <= 65535):
                raise ValueError("port out of range")
        except (KeyError, TypeError, ValueError):
            gaps.append(f"resource {r['id']}: skipped an inbound rule that could not be read")
            continue
        lines += [
            "",
            "  ingress {",
            f"    from_port   = {from_port}",
            f"    to_port     = {to_port}",
            f"    protocol    = {hcl_str(rule.get('protocol', 'tcp'))}",
            f"    cidr_blocks = [{hcl_str(cidr)}]",
            "  }",
        ]
    lines.append("}")
    blocks = ["\n".join(lines), _import_block("aws_security_group", local, r["resource_id"])]
    return blocks, gaps


def _ec2_instance(r: dict, local: str, refs: dict):
    cfg = r.get("config", {})
    ami, instance_type = cfg.get("ami"), cfg.get("instance_type")
    missing = [k for k, v in (("ami", ami), ("instance_type", instance_type)) if not v]
    if missing:
        return [], [f"resource {r['id']}: instance skipped, missing {', '.join(missing)}"]
    lines = [
        f'resource "aws_instance" "{local}" {{',
        f"  ami           = {hcl_str(ami)}",
        f"  instance_type = {hcl_str(instance_type)}",
    ]
    if refs.get("security_groups"):
        ids = ", ".join(refs["security_groups"])
        lines.append(f"  vpc_security_group_ids = [{ids}]")
    if r.get("name"):
        lines += ["", "  tags = {", f"    Name = {hcl_str(r['name'])}", "  }"]
    lines.append("}")
    blocks = ["\n".join(lines), _import_block("aws_instance", local, r["resource_id"])]
    return blocks, []


# resource_type in our database -> the function that writes its Terraform
RENDERERS = {
    "s3_bucket": _s3_bucket,
    "security_group": _security_group,
    "ec2_instance": _ec2_instance,
}