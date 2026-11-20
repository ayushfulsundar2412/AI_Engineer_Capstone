from pathlib import Path

from app.generation import generate_layers, write_files

# Invented data in the same shape as database rows. The AMI is a placeholder.
resources = [
    {"id": 1, "resource_type": "s3_bucket", "resource_id": "company-logs",
     "name": "company-logs", "app": "shared", "config": {"versioning": True}},
    {"id": 2, "resource_type": "ec2_instance", "resource_id": "i-0abc123",
     "name": "web-server", "app": "billing",
     "config": {"instance_type": "t3.large", "ami": "ami-0123456789abcdef0"}},
    {"id": 3, "resource_type": "security_group", "resource_id": "sg-0def456",
     "name": "open-ssh", "app": "shared",
     "config": {"inbound": [{"port": 22, "cidr": "0.0.0.0/0"}]}},
    {"id": 4, "resource_type": "ec2_instance", "resource_id": "i-0bad999",
     "name": "mystery-box", "app": "billing", "config": {"instance_type": "t3.small"}},
]
dependencies = [
    {"from_resource_id": 2, "to_resource_id": 3, "relationship": "uses_security_group"},
]

result = generate_layers("us-east-1", resources, dependencies)
write_files(result.files, Path("build/layers"))

print(result.files["APPLY_ORDER.md"])
for path, text in result.files.items():
    if path.endswith(".tf"):
        print("=====", path)
        print(text)
print("Gaps:")
for gap in result.gaps or ["none"]:
    print(" -", gap)