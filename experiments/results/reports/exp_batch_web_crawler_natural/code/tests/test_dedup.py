from webcrawler.dedup import BloomFilter, ContentDeduper, SimHasher


def test_bloom_filter_membership():
    bf = BloomFilter(capacity=100_000, error_rate=0.001)
    bf.add("http://example.com/1")
    assert "http://example.com/1" in bf
    assert "http://example.com/2" not in bf


def test_bloom_filter_add_many():
    bf = BloomFilter(capacity=100_000, error_rate=0.001)
    urls = [f"http://example.com/{i}" for i in range(1000)]
    bf.add_many(urls)
    assert all(u in bf for u in urls)


def test_bloom_filter_no_false_negative():
    bf = BloomFilter(capacity=10_000, error_rate=0.001)
    items = [f"item-{i}" for i in range(500)]
    for i in items:
        bf.add(i)
    assert all(i in bf for i in items)


def test_simhash_identical():
    s = SimHasher()
    a = s.fingerprint("the quick brown fox jumps over the lazy dog")
    b = s.fingerprint("the quick brown fox jumps over the lazy dog")
    assert a == b
    assert s.hamming_distance(a, b) == 0


def test_simhash_near_duplicate():
    s = SimHasher()
    base = "the quick brown fox jumps over the lazy dog and keeps running around the green field near the tall oak tree " * 5
    near = base.replace("quick", "fast", 1)
    far = "completely unrelated scientific article about quantum mechanics and subatomic particles " * 30
    fp_base = s.fingerprint(base)
    fp_near = s.fingerprint(near)
    fp_far = s.fingerprint(far)
    d_near = s.hamming_distance(fp_base, fp_near)
    d_far = s.hamming_distance(fp_base, fp_far)
    assert d_near < d_far
    assert d_near <= 4


def test_content_deduper_exact():
    d = ContentDeduper()
    assert not d.is_duplicate("hello world this is a page")
    assert d.is_duplicate("hello world this is a page")


def test_content_deduper_near_duplicate():
    d = ContentDeduper(near_dup_threshold=4)
    base = "the quick brown fox jumps over the lazy dog and keeps running around the green field near the tall oak tree " * 5
    d.add(base)
    near = base.replace("quick", "fast", 1)
    assert d.is_duplicate(near)


def test_content_deduper_distinct():
    d = ContentDeduper()
    d.add("alpha beta gamma delta epsilon zeta eta theta iota kappa" * 20)
    assert not d.is_duplicate("zebra yak xray whiskey victor uniform tango sierra romeo papa" * 20)
