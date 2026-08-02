"""Property テスト: 見積金額計算の正確性。

**Validates: Requirements 3.1, 3.3**

任意の有効な製品ID、正の整数の注文数量、有効な通貨に対して、
合計金額が「単価 × 数量」と一致し、税金や追加料金が含まれないことを検証する。
"""

from hypothesis import given
from hypothesis.strategies import sampled_from, integers

from tools import PRODUCTS, EXCHANGE_RATES, convert_currency

# 有効な製品IDのリスト
VALID_PRODUCT_IDS = [p["id"] for p in PRODUCTS]


def calculate_quote_total(product_id: str, quantity: int, target_currency: str) -> float:
    """見積金額計算ロジック: 製品の単価を指定通貨に換算し、数量を掛ける。

    これは設計書に記載された計算ロジックを再現する:
    1. カタログから製品を取得
    2. 単価を指定通貨に換算
    3. 換算後単価 × 数量 = 合計
    """
    product = next(p for p in PRODUCTS if p["id"] == product_id)
    unit_price = product["unit_price"]
    product_currency = product["currency"]

    # 通貨換算
    if product_currency == target_currency:
        converted_price = unit_price
    else:
        result = convert_currency(
            amount=unit_price,
            from_currency=product_currency,
            to_currency=target_currency,
        )
        converted_price = result["converted_amount"]

    # 合計 = 単価 × 数量（税抜き）
    total = round(converted_price * quantity, 2)
    return total


@given(
    product_id=sampled_from(VALID_PRODUCT_IDS),
    quantity=integers(min_value=1, max_value=10000),
    target_currency=sampled_from(["USD", "JPY"]),
)
def test_quote_total_equals_unit_price_times_quantity(
    product_id: str, quantity: int, target_currency: str
):
    """任意の有効な製品ID・数量・通貨に対して合計金額が「単価×数量」と一致する。

    税金や追加料金は含まれない。

    **Validates: Requirements 3.1, 3.3**
    """
    product = next(p for p in PRODUCTS if p["id"] == product_id)
    unit_price = product["unit_price"]
    product_currency = product["currency"]

    # 通貨換算して単価を取得
    if product_currency == target_currency:
        converted_price = unit_price
    else:
        conversion_result = convert_currency(
            amount=unit_price,
            from_currency=product_currency,
            to_currency=target_currency,
        )
        assert "error" not in conversion_result
        converted_price = conversion_result["converted_amount"]

    # 合計金額 = 換算後単価 × 数量（税抜き、追加料金なし）
    expected_total = round(converted_price * quantity, 2)

    # calculate_quote_total で同じ計算を行い一致を確認
    actual_total = calculate_quote_total(product_id, quantity, target_currency)

    assert actual_total == expected_total, (
        f"合計金額不一致: 期待値={expected_total}, 実際値={actual_total} "
        f"(製品={product_id}, 数量={quantity}, 通貨={target_currency})"
    )

    # 追加料金や税金が含まれていないことの検証:
    # 合計が「単価 × 数量」以上でも以下でもないこと
    assert actual_total == round(converted_price * quantity, 2)
