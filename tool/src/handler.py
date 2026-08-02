"""見積書 PDF 生成 Lambda ハンドラー"""

import json
import os
import uuid
from datetime import datetime
from io import BytesIO

import boto3
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# 製品カタログデータ
PRODUCTS = [
    {"id": "PROD-001", "name": "ウィジェットA", "unit_price": 29.99, "currency": "USD"},
    {"id": "PROD-002", "name": "ガジェットB", "unit_price": 4500, "currency": "JPY"},
    {"id": "PROD-003", "name": "モジュールC", "unit_price": 89.50, "currency": "USD"},
]

# 通貨換算レート
EXCHANGE_RATES = {
    "USD_TO_JPY": 150.0,
    "JPY_TO_USD": 1 / 150.0,
}

# フォントファイルパス（Lambda 環境では /var/task 配下）
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "NotoSansJP-VariableFont_wght.ttf")

# S3 クライアント
s3_client = boto3.client("s3")


def _register_font():
    """日本語フォントを reportlab に登録する"""
    pdfmetrics.registerFont(TTFont("NotoSansJP", FONT_PATH))


def _find_product(product_id):
    """製品カタログから製品情報を取得する"""
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None


def _convert_price(price, from_currency, to_currency):
    """通貨換算を行う"""
    if from_currency == to_currency:
        return price
    rate_key = f"{from_currency}_TO_{to_currency}"
    rate = EXCHANGE_RATES.get(rate_key)
    if rate is None:
        return price
    return price * rate


def _generate_pdf(customer_name, product, unit_price, quantity, total, currency):
    """見積書 PDF を生成してバイトデータを返す"""
    _register_font()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    # スタイル定義
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "JapaneseTitle",
        parent=styles["Title"],
        fontName="NotoSansJP",
        fontSize=24,
    )
    normal_style = ParagraphStyle(
        "JapaneseNormal",
        parent=styles["Normal"],
        fontName="NotoSansJP",
        fontSize=12,
    )

    # 通貨記号
    currency_symbol = "¥" if currency == "JPY" else "$"

    # 金額フォーマット
    if currency == "JPY":
        unit_price_str = f"{currency_symbol}{int(unit_price):,}"
        total_str = f"{currency_symbol}{int(total):,}"
    else:
        unit_price_str = f"{currency_symbol}{unit_price:,.2f}"
        total_str = f"{currency_symbol}{total:,.2f}"

    # PDF コンテンツ構築
    elements = []

    # タイトル
    elements.append(Paragraph("注文見積書", title_style))
    elements.append(Spacer(1, 10 * mm))

    # 発行日
    issue_date = datetime.now().strftime("%Y年%m月%d日")
    elements.append(Paragraph(f"発行日: {issue_date}", normal_style))
    elements.append(Spacer(1, 5 * mm))

    # 顧客名
    elements.append(Paragraph(f"顧客名: {customer_name}", normal_style))
    elements.append(Spacer(1, 10 * mm))

    # 見積明細テーブル
    table_data = [
        ["項目", "内容"],
        ["製品名", product["name"]],
        ["単価", unit_price_str],
        ["数量", str(quantity)],
        ["合計金額（税抜き）", total_str],
        ["通貨", currency],
    ]

    table = Table(table_data, colWidths=[50 * mm, 80 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "NotoSansJP"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)

    # PDF 生成
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _upload_to_s3(pdf_bytes, bucket_name):
    """PDF を S3 にアップロードし、署名付き URL を返す"""
    file_key = f"quotes/{uuid.uuid4()}.pdf"

    s3_client.put_object(
        Bucket=bucket_name,
        Key=file_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    # 30日間有効な署名付き URL を発行
    presigned_url = s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": file_key},
        ExpiresIn=30 * 24 * 60 * 60,  # 30日（秒）
    )

    return presigned_url


def _build_response(status_code, body):
    """API Gateway レスポンスを構築する"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def lambda_handler(event, context):
    """Lambda エントリポイント: 見積書 PDF を生成して署名付き URL を返す"""
    try:
        # リクエストボディのパース
        body = event.get("body", "")
        if isinstance(body, str):
            body = json.loads(body) if body else {}

        # 必須パラメータのバリデーション
        required_params = ["product_id", "customer_name", "quantity", "currency"]
        for param in required_params:
            if param not in body or body[param] is None or body[param] == "":
                return _build_response(400, {"error": "必須パラメータが不足しています"})

        product_id = body["product_id"]
        customer_name = body["customer_name"]
        quantity = body["quantity"]
        currency = body["currency"]

        # 数量の型チェック
        if not isinstance(quantity, (int, float)) or quantity <= 0:
            return _build_response(400, {"error": "必須パラメータが不足しています"})

        # 通貨の検証
        if currency not in ("USD", "JPY"):
            return _build_response(400, {"error": "必須パラメータが不足しています"})

        # 製品情報の取得
        product = _find_product(product_id)
        if product is None:
            return _build_response(400, {"error": "製品が見つかりません"})

        # 通貨換算して単価を算出
        unit_price = _convert_price(product["unit_price"], product["currency"], currency)

        # 合計金額計算（税抜き）
        total = unit_price * quantity

        # PDF 生成
        try:
            pdf_bytes = _generate_pdf(customer_name, product, unit_price, quantity, total, currency)
        except Exception:
            return _build_response(500, {"error": "PDF生成に失敗しました"})

        # S3 アップロードと署名付き URL 発行
        try:
            bucket_name = os.environ["QUOTE_BUCKET_NAME"]
            quote_url = _upload_to_s3(pdf_bytes, bucket_name)
        except Exception:
            return _build_response(500, {"error": "ファイル保存に失敗しました"})

        # 成功レスポンス
        response_body = {
            "quote_url": quote_url,
            "product_name": product["name"],
            "unit_price": unit_price,
            "quantity": quantity,
            "total": total,
            "currency": currency,
        }
        return _build_response(200, response_body)

    except json.JSONDecodeError:
        return _build_response(400, {"error": "必須パラメータが不足しています"})
    except Exception:
        return _build_response(500, {"error": "PDF生成に失敗しました"})
