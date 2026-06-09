from analytics_mcp.remote.ratelimit import TokenBucket


def test_bucket_allows_burst_then_blocks():
    times = iter([0.0, 0.0, 0.0])
    bucket = TokenBucket(rate=1, burst=2, now=lambda: next(times))
    assert bucket.allow("ip") is True
    assert bucket.allow("ip") is True
    assert bucket.allow("ip") is False  # burst exhausted, no time elapsed


def test_bucket_refills_over_time():
    clock = {"t": 0.0}
    bucket = TokenBucket(rate=1, burst=1, now=lambda: clock["t"])
    assert bucket.allow("ip") is True
    assert bucket.allow("ip") is False
    clock["t"] = 1.0  # one token refilled
    assert bucket.allow("ip") is True


def test_separate_keys_have_separate_buckets():
    bucket = TokenBucket(rate=1, burst=1, now=lambda: 0.0)
    assert bucket.allow("a") is True
    assert bucket.allow("b") is True
