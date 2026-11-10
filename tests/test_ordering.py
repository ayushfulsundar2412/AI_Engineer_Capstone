import pytest
from app.ordering import CycleError, affected_by, creation_order


def test_no_dependencies_keeps_id_order():
    assert creation_order([3, 1, 2], []) == [1,2,3]


def test_dependency_is_created_first():
    # resource 2 (web-server) depends on resource 3 (security group)
    assert creation_order([1, 2, 3], [(2, 3)]) == [1, 3, 2]


def test_chain():
    # 1 needs 2, and 2 needs 3
    assert creation_order([1, 2, 3], [(1, 2), (2, 3)]) == [3,2,1]


def test_cycle_is_detected():
    with pytest.raises(CycleError):
        creation_order([1, 2], [(1, 2), (2, 1)])

def test_affected_by_follows_chains():
    # 1 needs 2, and 2 needs 3: changing 3 affects both 2 and 1
    assert affected_by(3, [(1, 2), (2, 3)]) == [1, 2]


def test_affected_by_leaf_is_empty():
    assert affected_by(1, [(1, 2), (2, 3)]) == []


def test_affected_by_diamond():
    # 1 needs 2 and 3, and both need 4
    assert affected_by(4, [(1, 2), (1, 3), (2, 4), (3, 4)]) == [1, 2, 3]