from pathlib import Path

from app.generation import generate_terraform

# Same shape as rows from the database. The AMI below is invented for the demo.
resources = [
    {"id": 1, "resource_type": "s3_bucket", "resource_id": "company-logs",
     "name": "company-logs", "config": {"versioning": True}},
    {"id": 2, "resource_type": "ec2_instance", "resource_id": "i-0abc123",
     "name": "web-server",
     "config": {"instance_type": "t3.large", "ami": "ami-0123456789abcdef0"}},
    {"id": 3, "resource_type": "security_group", "resource_id": "sg-0def456",
     "name": "open-ssh",
     "config": {"inbound": [{"port": 22, "cidr": "0.0.0.0/0"}]}},
    {"id": 4, "resource_type": "ec2_instance", "resource_id": "i-0bad999",
     "name": "mystery-box", "config": {"instance_type": "t3.small"}},
]
dependencies = [
    {"from_resource_id": 2, "to_resource_id": 3, "relationship": "uses_security_group"},
]

result = generate_terraform("us-east-1", resources, dependencies)

out = Path("build/demo")
out.mkdir(parents=True, exist_ok=True)
(out / "main.tf").write_text(result.main_tf, encoding="utf-8")

print(result.main_tf)
print("Gaps:")
for gap in result.gaps or ["none"]:
    print(" -", gap)