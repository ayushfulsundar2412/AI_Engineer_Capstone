from collections import defaultdict, deque


class CycleError(Exception):
    """Raised when resources depend on each other in a loop."""

    def __init__(self, stuck: list[int]):
        self.stuck = stuck
        super().__init__(f"Dependency cycle involving resources: {stuck}")


def creation_order(resource_ids: list[int], edges: list[tuple[int, int]]) -> list[int]:
    """Return resource ids in a safe creation order.

    Each edge is (from_id, to_id), meaning "from depends on to",
    so `to` must be created before `from`.
    """
    waiting_on = {rid: 0 for rid in resource_ids}  # unmet dependencies per resource
    dependents = defaultdict(list)                 # to_id -> resources that need it
    for from_id, to_id in edges:
        waiting_on[from_id] += 1
        dependents[to_id].append(from_id)

    ready = deque(sorted(rid for rid, n in waiting_on.items() if n == 0))
    order = []
    while ready:
        rid = ready.popleft()
        order.append(rid)
        for dep in sorted(dependents[rid]):
            waiting_on[dep] -= 1
            if waiting_on[dep] == 0:
                ready.append(dep)

    if len(order) != len(resource_ids):
        stuck = sorted(rid for rid, n in waiting_on.items() if n > 0)
        raise CycleError(stuck)
    return order

def affected_by(resource_id: int, edges: list[tuple[int, int]]) -> list[int]:
    """Everything that directly or indirectly depends on resource_id."""
    dependents = defaultdict(list)  # to_id -> resources that need it
    for from_id, to_id in edges:
        dependents[to_id].append(from_id)

    seen = set()
    queue = deque([resource_id])
    while queue:
        current = queue.popleft()
        for dep in dependents[current]:
            if dep not in seen:
                seen.add(dep)
                queue.append(dep)
    seen.discard(resource_id)  # a loop must not list the resource as affecting itself
    return sorted(seen)

class LayerCycleError(Exception):
    """Raised when layers need each other in a loop."""

    def __init__(self, apps: list[str]):
        self.apps = apps
        super().__init__(f"Layers depend on each other in a loop: {apps}")


def layer_plan(resources: list[tuple[int, str]], edges: list[tuple[int, int]]) -> dict:
    """Group resources into layers (one per app) and order the layers.

    resources: (resource_id, app) pairs
    edges: (from_id, to_id) pairs, meaning "from needs to"
    """
    app_of = dict(resources)
    apps = sorted(set(app_of.values()), key=lambda a: (a != "shared", a))
    index = {app: i for i, app in enumerate(apps)}

    links = defaultdict(int)  # (from_app, to_app) -> number of arrows between them
    for from_id, to_id in edges:
        a, b = app_of[from_id], app_of[to_id]
        if a != b:
            links[(a, b)] += 1

    layer_edges = [(index[a], index[b]) for (a, b) in links]
    try:
        order = creation_order(list(range(len(apps))), layer_edges)
    except CycleError as exc:
        raise LayerCycleError([apps[i] for i in exc.stuck])

    members = defaultdict(list)
    for rid, app in sorted(resources):
        members[app].append(rid)

    warnings = []
    for (a, b), n in sorted(links.items()):
        if a == "shared":
            warnings.append(
                f"The shared layer depends on the '{b}' layer ({n} links). "
                "Shared resources should not depend on apps."
            )

    return {
        "apply_order": [
            {"layer": apps[i], "resource_ids": members[apps[i]]} for i in order
        ],
        "cross_layer_links": [
            {"from_layer": a, "to_layer": b, "links": n}
            for (a, b), n in sorted(links.items())
        ],
        "warnings": warnings,
    }