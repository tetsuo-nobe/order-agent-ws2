"""ToolAPI ユニットテスト: バリデーション、PDF生成、S3操作"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

# ダミー PDF バイトデータ（テスト用）
DUMMY_PDF_BYTES = b"%PDF-1.4 dummy content for testing"


# テスト実行前に環境変数を設定
@pytest.fixture(autouse=True)
def set_env():
    """テスト共通の環境変数をセットする"""
    with patch.dict(os.environ, {"QUOTE_BUCKET_NAME": "test-bucket"}):
        yield


@pytest.fixture(autouse=True)
def mock_pdf_generation():
    """PDF 生成をモックして、フォントファイル不在でもテスト可能にする"""
    with patch("handler._generate_pdf", return_value=DUMMY_PDF_BYTES) as mock_gen:
        yield mock_gen


@pytest.fixture
def mock_s3():
    """boto3 S3 クライアントのモック"""
    with patch("handler.s3_client") as mock_client:
        mock_client.put_object.return_value = {}
        mock_client.generate_presigned_url.return_value = "https://s3.example.com/quotes/test.pdf"
        yield mock_client


def _make_event(body: dict | str | None = None) -> dict:
    """API Gateway プロキシ統合形式のイベントを構築する"""
    if body is None:
        return {"body": ""}
    if isinstance(body, dict):
        return {"body": json.dumps(body)}
    return {"body": body}


def _parse_response(response: dict) -> tuple[int, dict]:
    """レスポンスのステータスコードとボディを取得する"""
    return response["statusCode"], json.loads(response["body"])


# =============================================================================
# バリデーションテスト (Requirements 3.1)
# =============================================================================


class TestValidation:
    """リクエストパラメータのバリデーションテスト"""

    def test_missing_body(self, mock_s3):
        """ボディが空の場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event(None)
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_missing_product_id(self, mock_s3):
        """product_id が欠落している場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "customer_name": "テスト顧客",
            "quantity": 5,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_missing_customer_name(self, mock_s3):
        """customer_name が欠落している場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "quantity": 5,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_missing_quantity(self, mock_s3):
        """quantity が欠落している場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_missing_currency(self, mock_s3):
        """currency が欠落している場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 5,
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_invalid_quantity_zero(self, mock_s3):
        """quantity が 0 の場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 0,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_invalid_quantity_negative(self, mock_s3):
        """quantity が負数の場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": -3,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_invalid_quantity_string(self, mock_s3):
        """quantity が文字列の場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": "abc",
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_invalid_currency(self, mock_s3):
        """無効な通貨コードの場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 5,
            "currency": "EUR",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"

    def test_invalid_product_id(self, mock_s3):
        """存在しない製品IDの場合は 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-999",
            "customer_name": "テスト顧客",
            "quantity": 5,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "製品が見つかりません"

    def test_invalid_json_body(self, mock_s3):
        """JSON パース不可のボディは 400 エラーを返す"""
        from handler import lambda_handler

        event = _make_event("not-valid-json{{{")
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 400
        assert body["error"] == "必須パラメータが不足しています"


# =============================================================================
# PDF 生成テスト (Requirements 3.2, 3.3)
# =============================================================================


class TestPdfGeneration:
    """PDF 生成の正常系テスト"""

    def test_successful_quote_usd(self, mock_s3):
        """USD で見積書が正常に生成され、正しい金額が返される"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 10,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 200
        assert body["quote_url"] == "https://s3.example.com/quotes/test.pdf"
        assert body["product_name"] == "ウィジェットA"
        assert body["unit_price"] == 29.99
        assert body["quantity"] == 10
        # 合計金額: 29.99 * 10 = 299.9（税抜き）
        assert body["total"] == pytest.approx(299.9)
        assert body["currency"] == "USD"

    def test_successful_quote_jpy(self, mock_s3):
        """JPY で見積書が正常に生成され、通貨換算が正しい"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 5,
            "currency": "JPY",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 200
        # PROD-001 は USD 29.99 → JPY: 29.99 * 150.0 = 4498.5
        assert body["unit_price"] == pytest.approx(29.99 * 150.0)
        assert body["total"] == pytest.approx(29.99 * 150.0 * 5)
        assert body["currency"] == "JPY"

    def test_successful_quote_same_currency(self, mock_s3):
        """製品の通貨と指定通貨が同じ場合は換算なし"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-002",
            "customer_name": "日本太郎",
            "quantity": 3,
            "currency": "JPY",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 200
        # PROD-002 は JPY 4500、換算なし
        assert body["unit_price"] == 4500
        assert body["total"] == 4500 * 3
        assert body["currency"] == "JPY"

    def test_pdf_generation_failure(self, mock_s3, mock_pdf_generation):
        """PDF 生成で例外が発生した場合は 500 エラーを返す"""
        from handler import lambda_handler

        mock_pdf_generation.side_effect = Exception("PDF error")

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 1,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 500
        assert body["error"] == "PDF生成に失敗しました"


# =============================================================================
# S3 操作テスト (Requirements 3.3)
# =============================================================================


class TestS3Operations:
    """S3 アップロードと署名付き URL 発行のテスト"""

    def test_s3_put_object_called(self, mock_s3):
        """PDF 生成後に S3 put_object が呼ばれる"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 1,
            "currency": "USD",
        })
        lambda_handler(event, None)

        # put_object が呼ばれたことを確認
        mock_s3.put_object.assert_called_once()
        call_kwargs = mock_s3.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "test-bucket"
        assert call_kwargs["Key"].startswith("quotes/")
        assert call_kwargs["Key"].endswith(".pdf")
        assert call_kwargs["ContentType"] == "application/pdf"
        # PDF バイトデータが渡されている
        assert isinstance(call_kwargs["Body"], bytes)
        assert len(call_kwargs["Body"]) > 0

    def test_s3_presigned_url_called(self, mock_s3):
        """PDF 保存後に署名付き URL 生成が呼ばれる"""
        from handler import lambda_handler

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 1,
            "currency": "USD",
        })
        lambda_handler(event, None)

        # generate_presigned_url が呼ばれたことを確認
        mock_s3.generate_presigned_url.assert_called_once()
        call_args = mock_s3.generate_presigned_url.call_args
        assert call_args[0][0] == "get_object"
        params = call_args[1]["Params"]
        assert params["Bucket"] == "test-bucket"
        assert params["Key"].startswith("quotes/")
        # 30日間（秒）の有効期限
        assert call_args[1]["ExpiresIn"] == 30 * 24 * 60 * 60

    def test_s3_upload_failure(self, mock_s3):
        """S3 アップロード失敗時は 500 エラーを返す"""
        from handler import lambda_handler

        mock_s3.put_object.side_effect = Exception("S3 upload error")

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 1,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 500
        assert body["error"] == "ファイル保存に失敗しました"

    def test_s3_presigned_url_failure(self, mock_s3):
        """署名付き URL 生成失敗時は 500 エラーを返す"""
        from handler import lambda_handler

        mock_s3.generate_presigned_url.side_effect = Exception("Presign error")

        event = _make_event({
            "product_id": "PROD-001",
            "customer_name": "テスト顧客",
            "quantity": 1,
            "currency": "USD",
        })
        response = lambda_handler(event, None)
        status, body = _parse_response(response)

        assert status == 500
        assert body["error"] == "ファイル保存に失敗しました"
