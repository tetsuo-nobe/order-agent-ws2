# Design Document

## Overview

注文見積り書作成エージェントは、4層のアーキテクチャで構成される。フロントエンド（SPA）→ バックエンド（Node.js Lambda + Function URL）→ エージェント（Strands Agents SDK on AgentCore Runtime）→ ツール（Python Lambda + API Gateway + AgentCore Gateway）の流れでリクエストが処理される。エージェントはユーザーとの対話を通じて製品情報の取得、通貨換算、見積書PDF生成を行う。

## Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐     ┌──────────────────────┐
│   WebApp    │────▶│   BackendFunction    │────▶│  AgentCore Runtime     │────▶│  AgentCore Gateway   │
│  (SPA/JS)  │◀────│  (Node.js Lambda)    │◀────│  (Strands Agent)       │◀────│  (ToolAPI)           │
│  Amplify   │     │  Function URL        │     │  AgentCore Memory      │     │  API GW + Lambda     │
└─────────────┘     └──────────────────────┘     └─────────────────────────┘     └──────────────────────┘
                                                                                          │
                                                                                          ▼
                                                                                   ┌──────────────┐
                                                                                   │   S3 Bucket  │
                                                                                   │  (QuotePDF)  │
                                                                                   └──────────────┘
```

### データフロー

1. **ユーザー → WebApp**: チャットメッセージ送信
2. **WebApp → BackendFunction**: HTTP POST（Function URL）、ストリームレスポンス受信
3. **BackendFunction → AgentCore Runtime**: BedrockAgentCoreClient 経由でエージェント呼出し
4. **AgentCore Runtime → Agent**: Strands Agents SDK がメッセージ処理
5. **Agent → AgentCore Gateway**: ツール呼出し（見積書作成時）
6. **AgentCore Gateway → ToolAPI**: API Gateway REST API（IAM認証）経由で Lambda 実行
7. **ToolAPI → S3**: PDF保存、署名付きURL発行
8. **Agent → BackendFunction → WebApp**: ストリーム形式で回答返却

## Components

### 1. ToolAPI（tool フォルダ）

見積書作成機能を提供する Lambda 関数と API Gateway。

#### Lambda 関数: CreateQuoteFunction

- **ランタイム**: Python 3.13
- **主要依存**: reportlab（PDF生成）, boto3（S3操作）
- **エントリポイント**: `handler.lambda_handler`

#### API Gateway

- **タイプ**: REST API
- **認証**: IAM
- **エンドポイント**: POST /quote
- **統合**: Lambda プロキシ統合

#### AgentCore Gateway

- CloudFormation リソースとして SAM テンプレートに記述
- API Gateway REST API を呼び出す形式

### 2. Agent（agent フォルダ）

AgentCore CLI で作成するプロジェクト。

#### エージェント実装

- **SDK**: Strands Agents SDK
- **モデル**: jp.anthropic.claude-sonnet-4-6
- **リージョン**: ap-northeast-1
- **セッション管理**: AgentCore Memory（短期記憶）
- **ツール**: ProductCatalog 検索、CurrencyConverter、見積書作成（AgentCore Gateway経由）

### 3. BackendFunction（backend フォルダ）

フロントエンドとエージェントを仲介する Lambda 関数。

- **ランタイム**: Node.js
- **アクセス方式**: Lambda Function URL
- **SDK**: @aws-sdk/client-bedrock-agent-core（BedrockAgentCoreClient）
- **レスポンス形式**: ストリーム
- **CORS**: 対応

### 4. WebApp（front フォルダ）

JavaScript ベースの SPA。

- **フレームワーク**: 不使用（Vanilla JS）
- **UI**: チャットインターフェース
- **通信**: Fetch API（ストリーミング読取り）
- **ホスティング**: AWS Amplify

## Interfaces

### ToolAPI エンドポイント

```
POST /quote
```

**リクエスト:**
```json
{
  "product_id": "string",
  "customer_name": "string",
  "quantity": "number",
  "currency": "USD | JPY"
}
```

**レスポンス:**
```json
{
  "statusCode": 200,
  "body": {
    "quote_url": "string (署名付きURL)",
    "product_name": "string",
    "unit_price": "number",
    "quantity": "number",
    "total": "number",
    "currency": "string"
  }
}
```

### BackendFunction エンドポイント

```
POST <Function URL>
```

**リクエスト:**
```json
{
  "message": "string",
  "session_id": "string (optional)"
}
```

**レスポンス（ストリーム）:**
```
data: {"type": "text", "content": "..."}
data: {"type": "text", "content": "..."}
data: {"type": "end", "session_id": "..."}
```

### Agent ツール定義

#### get_product_info

```python
def get_product_info(product_id: str = None) -> dict:
    """製品情報を取得する。product_idを指定しない場合は全製品を返す。"""
    pass
```

#### convert_currency

```python
def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """通貨を換算する。固定レートを使用。"""
    pass
```

#### create_quote（AgentCore Gateway経由）

ToolAPI の POST /quote エンドポイントを AgentCore Gateway を通じて呼び出す。

## Data Models

### ProductCatalog

```python
# 製品カタログ（Python 変数としてエージェント内に定義）
PRODUCTS = [
    {"id": "PROD-001", "name": "ウィジェットA", "unit_price": 29.99, "currency": "USD"},
    {"id": "PROD-002", "name": "ガジェットB", "unit_price": 4500, "currency": "JPY"},
    {"id": "PROD-003", "name": "モジュールC", "unit_price": 89.50, "currency": "USD"},
]
```

### CurrencyConverter

```python
# 固定換算レート
EXCHANGE_RATES = {
    "USD_TO_JPY": 150.0,
    "JPY_TO_USD": 1 / 150.0,
}
```

### QuotePDF 構成

| フィールド | 説明 |
|---|---|
| タイトル | 「注文見積書」 |
| 発行日 | 見積書作成日 |
| 顧客名 | リクエストで指定された顧客名 |
| 製品名 | カタログから取得した製品名 |
| 単価 | 指定通貨での単価 |
| 数量 | リクエストで指定された数量 |
| 合計金額 | 単価 × 数量（税抜き） |
| 通貨 | 表示通貨（USD/JPY） |

## Error Handling

### ToolAPI

| エラーケース | ステータスコード | レスポンス |
|---|---|---|
| 不正な製品ID | 400 | `{"error": "製品が見つかりません"}` |
| 必須パラメータ不足 | 400 | `{"error": "必須パラメータが不足しています"}` |
| PDF生成失敗 | 500 | `{"error": "PDF生成に失敗しました"}` |
| S3アップロード失敗 | 500 | `{"error": "ファイル保存に失敗しました"}` |

### BackendFunction

| エラーケース | ステータスコード | レスポンス |
|---|---|---|
| リクエストボディ不正 | 400 | `{"error": "無効なリクエストです"}` |
| AgentCore 呼出し失敗 | 502 | `{"error": "エージェントの応答を取得できません"}` |
| タイムアウト | 504 | `{"error": "応答がタイムアウトしました"}` |

### WebApp

- ネットワークエラー時: ユーザーに再試行を促すメッセージ表示
- ストリーム中断時: 途中までの応答を表示し、エラーメッセージを追加

## SAM テンプレート構成

### tool/template.yaml

```yaml
# SAM template for Quote Tool API and AgentCore Gateway
Resources:
  # Lambda Function for quote generation
  CreateQuoteFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: python3.13
      Handler: handler.lambda_handler
      # Layers and policies for reportlab, boto3, S3 access

  # REST API with IAM auth
  QuoteApi:
    Type: AWS::Serverless::Api
    Properties:
      Auth:
        DefaultAuthorizer: AWS_IAM

  # S3 Bucket for PDF storage (tool-local)
  QuoteBucket:
    Type: AWS::S3::Bucket

  # AgentCore Gateway (CloudFormation custom resource or SDK-based)
  AgentCoreGateway:
    Type: AWS::CloudFormation::CustomResource
    # Configuration for AgentCore Gateway pointing to QuoteApi
```

### backend/template.yaml

```yaml
# SAM template for Backend Function
Resources:
  # Lambda Function with Function URL
  BackendFunction:
    Type: AWS::Serverless::Function
    Properties:
      Runtime: nodejs20.x
      Handler: index.handler
      FunctionUrlConfig:
        AuthType: NONE
        Cors:
          AllowOrigins: ["*"]
          AllowMethods: ["POST", "OPTIONS"]
          AllowHeaders: ["Content-Type"]
        InvokeMode: RESPONSE_STREAM
```

## Correctness Properties

*プロパティとは、システムの全ての有効な実行に対して成立すべき特性・振る舞いのことである。プロパティは人間が読める仕様と、機械的に検証可能な正しさ保証の橋渡しとなる。*

### Property 1: 製品情報検索の正確性

*任意の* 有効な製品IDに対して、`get_product_info` が返す情報（ID、名称、単価、通貨）は ProductCatalog に定義されたデータと完全に一致し、すべての必須フィールド（ID、名称、単価、通貨）が存在し、通貨は "USD" または "JPY" のいずれかである。

**Validates: Requirements 1.1, 1.4**

### Property 2: 通貨換算ラウンドトリップ

*任意の* 正の金額に対して、JPY→USD→JPY の変換を行った場合、丸め誤差の許容範囲内で元の金額に戻る。同様に、USD→JPY→USD の変換も元の金額に戻る。

**Validates: Requirements 2.1, 2.2**

### Property 3: 見積金額計算の正確性

*任意の* 有効な製品ID、正の整数の注文数量、および有効な見積り通貨に対して、見積書に記載される合計金額は「指定通貨での単価 × 数量」と一致し、税金や追加料金は含まれない。

**Validates: Requirements 3.1, 3.3**
