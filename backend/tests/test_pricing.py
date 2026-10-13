from app.runtime.pricing import compute_cost, estimate_tokens


def test_estimate_tokens_empty_string():
    assert estimate_tokens("") == 0


def test_estimate_tokens_counts_cjk_as_one_each():
    assert estimate_tokens("一二三四五六七八九十") == 10


def test_estimate_tokens_counts_latin_as_quarter():
    assert estimate_tokens("abcdefgh") == 2


def test_estimate_tokens_mixed_text():
    text = "一二三四" + "abcd"
    assert estimate_tokens(text) == 5  # 4 CJK + ceil(4/4)


def test_estimate_tokens_is_at_least_one_for_nonempty():
    assert estimate_tokens("a") == 1


def test_compute_cost_with_both_prices():
    prices = {"input": 1.0, "output": 2.0}  # 每百万 token 单价
    cost = compute_cost(1_000_000, 500_000, prices)
    assert cost == 2.0


def test_compute_cost_zero_when_no_usage():
    assert compute_cost(0, 0, {"input": 1.0, "output": 2.0}) == 0.0


def test_compute_cost_zero_when_prices_missing():
    assert compute_cost(1000, 1000, None) == 0.0


def test_compute_cost_partial_prices_uses_zero_for_missing_side():
    assert compute_cost(1_000_000, 1_000_000, {"input": 3.0}) == 3.0
