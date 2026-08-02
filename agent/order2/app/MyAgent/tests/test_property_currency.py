"""Property テスト: 通貨換算ラウンドトリップ。

**Validates: Requirements 2.1, 2.2**

任意の正の金額に対して、JPY→USD→JPY および USD→JPY→USD の変換が
許容誤差内で元の金額に戻ることを検証する。
"""

from hypothesis import given
from hypothesis.strategies import floats

from tools import convert_currency


@given(amount=floats(min_value=0.01, max_value=1_000_000, allow_nan=False, allow_infinity=False))
def test_jpy_usd_jpy_roundtrip(amount: float):
    """JPY→USD→JPY のラウンドトリップが許容誤差内で元の金額に戻る。

    **Validates: Requirements 2.1, 2.2**
    """
    # JPY → USD
    jpy_to_usd = convert_currency(amount=amount, from_currency="JPY", to_currency="USD")
    assert "error" not in jpy_to_usd
    usd_amount = jpy_to_usd["converted_amount"]

    # USD → JPY
    usd_to_jpy = convert_currency(amount=usd_amount, from_currency="USD", to_currency="JPY")
    assert "error" not in usd_to_jpy
    final_amount = usd_to_jpy["converted_amount"]

    # 丸め誤差の許容範囲内で元の金額に戻ること
    # round(amount * (1/150) * 150, 2) の丸め誤差を許容
    tolerance = 1.0  # JPY の丸め誤差を考慮して 1 円以内
    assert abs(final_amount - amount) <= tolerance, (
        f"ラウンドトリップ失敗: {amount} JPY → {usd_amount} USD → {final_amount} JPY "
        f"(差: {abs(final_amount - amount)})"
    )


@given(amount=floats(min_value=0.01, max_value=1_000_000, allow_nan=False, allow_infinity=False))
def test_usd_jpy_usd_roundtrip(amount: float):
    """USD→JPY→USD のラウンドトリップが許容誤差内で元の金額に戻る。

    **Validates: Requirements 2.1, 2.2**
    """
    # USD → JPY
    usd_to_jpy = convert_currency(amount=amount, from_currency="USD", to_currency="JPY")
    assert "error" not in usd_to_jpy
    jpy_amount = usd_to_jpy["converted_amount"]

    # JPY → USD
    jpy_to_usd = convert_currency(amount=jpy_amount, from_currency="JPY", to_currency="USD")
    assert "error" not in jpy_to_usd
    final_amount = jpy_to_usd["converted_amount"]

    # 丸め誤差の許容範囲内で元の金額に戻ること
    # round(amount * 150 * (1/150), 2) の丸め誤差を許容
    tolerance = 0.01  # USD の丸め誤差を考慮して 0.01 ドル以内
    assert abs(final_amount - amount) <= tolerance, (
        f"ラウンドトリップ失敗: {amount} USD → {jpy_amount} JPY → {final_amount} USD "
        f"(差: {abs(final_amount - amount)})"
    )
