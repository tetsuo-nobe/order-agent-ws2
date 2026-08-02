"""Property テスト: 製品情報検索の正確性。

**Validates: Requirements 1.1, 1.4**

任意の有効な製品IDに対して get_product_info が返す情報が
ProductCatalog に定義されたデータと完全に一致することを検証する。
"""

from hypothesis import given
from hypothesis.strategies import sampled_from

from tools import get_product_info, PRODUCTS

# 有効な製品IDのリスト
VALID_PRODUCT_IDS = [p["id"] for p in PRODUCTS]


@given(product_id=sampled_from(VALID_PRODUCT_IDS))
def test_product_info_matches_catalog(product_id: str):
    """任意の有効な製品IDに対して、get_product_info が ProductCatalog と一致するデータを返す。

    **Validates: Requirements 1.1, 1.4**
    """
    result = get_product_info(product_id=product_id)

    # エラーではないこと
    assert "error" not in result
    assert "product" in result

    product = result["product"]

    # カタログから期待値を取得
    expected = next(p for p in PRODUCTS if p["id"] == product_id)

    # すべての必須フィールドが存在すること
    assert "id" in product
    assert "name" in product
    assert "unit_price" in product
    assert "currency" in product

    # カタログのデータと完全に一致すること
    assert product["id"] == expected["id"]
    assert product["name"] == expected["name"]
    assert product["unit_price"] == expected["unit_price"]
    assert product["currency"] == expected["currency"]

    # 通貨が "USD" または "JPY" のいずれかであること
    assert product["currency"] in ("USD", "JPY")
