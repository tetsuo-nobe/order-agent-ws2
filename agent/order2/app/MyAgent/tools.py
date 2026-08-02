"""注文見積りエージェントのツール定義。

製品カタログ検索、通貨換算、見積書作成のツールを提供する。
"""

import os
import json
import urllib.request
import urllib.parse

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.session import get_session
from strands import tool

# ToolAPI のエンドポイント URL（環境変数で設定）
QUOTE_API_URL = os.environ.get("QUOTE_API_URL", "")

# 製品カタログ（Python 変数としてエージェント内に定義）
PRODUCTS = [
    {"id": "PROD-001", "name": "ウィジェットA", "unit_price": 29.99, "currency": "USD"},
    {"id": "PROD-002", "name": "ガジェットB", "unit_price": 4500, "currency": "JPY"},
    {"id": "PROD-003", "name": "モジュールC", "unit_price": 89.50, "currency": "USD"},
]

# 固定換算レート
EXCHANGE_RATES = {
    "USD_TO_JPY": 150.0,
    "JPY_TO_USD": 1 / 150.0,
}


@tool
def get_product_info(product_id: str = None) -> dict:
    """製品情報を取得する。product_idを指定しない場合は全製品を返す。

    Args:
        product_id: 製品ID（例: PROD-001）。省略時は全製品を返す。

    Returns:
        製品情報の辞書。product_id指定時は単一製品、省略時は全製品リスト。
    """
    if product_id is None:
        return {"products": PRODUCTS}

    for product in PRODUCTS:
        if product["id"] == product_id:
            return {"product": product}

    return {"error": f"製品が見つかりません: {product_id}"}


@tool
def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """通貨を換算する。固定レートを使用。

    Args:
        amount: 換算する金額
        from_currency: 換算元の通貨コード（USD または JPY）
        to_currency: 換算先の通貨コード（USD または JPY）

    Returns:
        換算結果の辞書（元金額、換算後金額、レート情報を含む）。
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return {
            "original_amount": amount,
            "converted_amount": amount,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate": 1.0,
        }

    rate_key = f"{from_currency}_TO_{to_currency}"
    rate = EXCHANGE_RATES.get(rate_key)

    if rate is None:
        return {"error": f"サポートされていない通貨ペアです: {from_currency} → {to_currency}"}

    converted_amount = round(amount * rate, 2)

    return {
        "original_amount": amount,
        "converted_amount": converted_amount,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate": rate,
    }


@tool
def create_quote(product_id: str, customer_name: str, quantity: int, currency: str) -> dict:
    """注文見積り書（PDF）を作成する。ToolAPI を呼び出して PDF を生成し、ダウンロード URL を返す。

    Args:
        product_id: 製品ID（例: PROD-001）
        customer_name: 顧客名
        quantity: 注文数量（1以上の整数）
        currency: 見積り通貨（USD または JPY）

    Returns:
        見積書情報（quote_url, product_name, unit_price, quantity, total, currency）を含む辞書。
    """
    if not QUOTE_API_URL:
        return {"error": "見積書作成APIのURLが設定されていません（QUOTE_API_URL環境変数）"}

    # リクエストボディ
    body = json.dumps({
        "product_id": product_id,
        "customer_name": customer_name,
        "quantity": quantity,
        "currency": currency.upper(),
    })

    # SigV4 署名付きリクエストの作成
    session = get_session()
    credentials = session.get_credentials().get_frozen_credentials()
    region = os.environ.get("AWS_REGION", "ap-northeast-1")

    request = AWSRequest(
        method="POST",
        url=QUOTE_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
        },
    )
    SigV4Auth(credentials, "execute-api", region).add_auth(request)

    # HTTP リクエストの送信
    try:
        req = urllib.request.Request(
            url=QUOTE_API_URL,
            data=body.encode("utf-8"),
            headers=dict(request.headers),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        try:
            error_data = json.loads(error_body)
            return {"error": error_data.get("error", f"APIエラー: {e.code}")}
        except json.JSONDecodeError:
            return {"error": f"APIエラー: {e.code} - {error_body}"}
    except Exception as e:
        return {"error": f"見積書作成に失敗しました: {str(e)}"}
