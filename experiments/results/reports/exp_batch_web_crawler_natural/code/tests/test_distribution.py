import pytest

from webcrawler.distribution import Distributor, HashRing


def test_hash_ring_deterministic():
    ring = HashRing(["w1", "w2", "w3"])
    assert ring.get_node("example.com") == ring.get_node("example.com")


def test_hash_ring_distributes():
    ring = HashRing(["w1", "w2", "w3"])
    nodes = {ring.get_node(str(i)) for i in range(2000)}
    assert nodes <= {"w1", "w2", "w3"}
    assert len(nodes) == 3


def test_hash_ring_requires_nodes():
    with pytest.raises(ValueError):
        HashRing([])


def test_hash_ring_add_remove_node():
    ring = HashRing(["w1", "w2"])
    ring.add_node("w3")
    assert "w3" in ring.nodes
    ring.remove_node("w3")
    assert "w3" not in ring.nodes
    assert ring.get_node("any") in {"w1", "w2"}


def test_distributor_host_locality():
    d = Distributor(["w1", "w2", "w3"])
    w = d.worker_for("http://example.com/a")
    assert d.worker_for("http://example.com/b") == w
    assert w in {"w1", "w2", "w3"}


def test_distributor_assign_partitions():
    d = Distributor(["w1", "w2", "w3"])
    urls = [f"http://host{i % 50}.com/page/{i}" for i in range(1000)]
    batches = d.assign(urls)
    assert set(batches) <= {"w1", "w2", "w3"}
    assert sum(len(v) for v in batches.values()) == len(urls)
    # same host always lands in the same worker
    for url in urls:
        assert d.worker_for(url) in batches
