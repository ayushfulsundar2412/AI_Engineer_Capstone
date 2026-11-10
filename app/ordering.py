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