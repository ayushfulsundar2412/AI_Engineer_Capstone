WORLD = {"0.0.0.0/0", "::/0"}
ADMIN_PORTS = {22: "SSH", 3389: "remote desktop"}


def _open_to_world(permission: dict) -> bool:
    cidrs = [r.get("CidrIp") for r in permission.get("IpRanges", [])]
    cidrs += [r.get("CidrIpv6") for r in permission.get("Ipv6Ranges", [])]
    return any(c in WORLD for c in cidrs)


def admin_ports_open_to_world(group: dict) -> list[str]:
    """Describe every inbound rule that exposes admin access to the internet."""
    findings = []
    for perm in group.get("IpPermissions", []):
        if not _open_to_world(perm):
            continue
        if perm.get("IpProtocol") == "-1":
            findings.append("all traffic allowed from anywhere")
            continue
        if perm.get("IpProtocol") != "tcp":
            continue
        low, high = perm.get("FromPort"), perm.get("ToPort")
        if low is None or high is None:
            continue
        names = [name for port, name in ADMIN_PORTS.items() if low <= port <= high]
        if names:
            findings.append(f"ports {low}-{high} open to the world ({', '.join(names)})")
    return findings