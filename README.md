# 注文見積りアシスタント

## 概要

- AI エージェントを使った注文見積書作成システム
- チャット UI を通じて製品情報の問い合わせ、通貨換算、PDF 見積書の生成が可能
- Amazon Bedrock AgentCore Runtime 上で動作する Strands Agents SDK エージェント

## アーキテクチャ

```
┌─────────────┐     ┌──────────────────────┐     ┌─────────────────────────┐     ┌──────────────────────┐
│   WebApp    │────▶│   BackendFunction    │────▶│  AgentCore Runtime     │────▶│  ToolAPI             │
│  (SPA/JS)  │◀────│  (Node.js Lambda)    │◀────│  (Strands Agent)       │◀────│  (Python Lambda)     │
│  localhost  │     │  Function URL        │     │  AgentCore Memory      │     │  API GW + S3         │
└─────────────┘     └──────────────────────┘     └─────────────────────────┘     └──────────────────────┘
```

## フォルダ構成

```
order-agent-ws2/
├── front/           # フロントエンド（Vanilla JS SPA）
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── amplify.yml
├── backend/         # バックエンド（Node.js Lambda + Function URL）
│   ├── template.yaml    # SAM テンプレート
│   ├── samconfig.toml
│   └── src/
│       ├── index.mjs        # Lambda ハンドラー（SigV4 署名付き AgentCore 呼出し）
│       ├── handler-core.mjs # コアロジック（バリデーション、ストリーム処理）
│       └── package.json
├── agent/           # エージェント（AgentCore Runtime）
│   └── order2/
│       ├── agentcore/
│       │   └── agentcore.json  # AgentCore プロジェクト設定
│       └── app/MyAgent/
│           ├── main.py       # エージェントエントリポイント
│           ├── tools.py      # ツール定義（製品検索、通貨換算、見積書作成）
│           ├── model/load.py # Bedrock モデル設定
│           ├── memory/session.py  # セッション管理
│           └── pyproject.toml
├── tool/            # ToolAPI（見積書 PDF 生成）
│   ├── template.yaml    # SAM テンプレート
│   └── src/
│       ├── handler.py       # PDF 生成 Lambda
│       ├── requirements.txt
│       └── fonts/           # 日本語フォント（NotoSansJP）
└── .kiro/specs/     # 仕様書
```

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | Vanilla JS, marked.js（マークダウン表示） |
| バックエンド | Node.js 20.x, Lambda Function URL (RESPONSE_STREAM) |
| エージェント | Python 3.14, Strands Agents SDK, AgentCore Runtime |
| モデル | jp.anthropic.claude-sonnet-4-6 (ap-northeast-1) |
| ツール API | Python 3.13, reportlab (PDF), API Gateway (IAM認証) |
| インフラ | AWS SAM, AgentCore CLI, CloudFormation |

## 前提条件

- AWS CLI v2（設定済み）
- AWS SAM CLI
- AgentCore CLI (`npm install -g @anthropic-ai/agentcore-cli` or equivalent)
- Python 3.13+
- Node.js 20+
- uv（Python パッケージマネージャー）

## 参考: AWS アカウントの指定

$env:AWS_ACCESS_KEY_ID = "あなたのアクセスキーID"
$env:AWS_SECRET_ACCESS_KEY = "あなたのシークレットアクセスキー"
$env:AWS_DEFAULT_REGION = "ap-northeast-1"

## デプロイ手順

### 1. ToolAPI のデプロイ

```bash
cd tool
sam build
sam deploy --guided
# スタック名: order2-tool
# リージョン: ap-northeast-1
```

デプロイ後、Outputs の `QuoteApiUrl` を控える。

### 2. エージェントのデプロイ

```bash
cd agent/order2/agentcore
```

`agentcore.json` の `QUOTE_API_URL` 環境変数に、手順1で取得した URL を設定：

```json
{"name": "QUOTE_API_URL", "value": "https://xxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/prod/quote"}
```

デプロイ：

```bash
agentcore deploy
```

デプロイ後、`agentcore status` で Runtime ARN を確認。

### 3. IAM ポリシーの設定

エージェントの実行ロールに API Gateway の呼出し権限を追加：

```powershell
$policy = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"execute-api:Invoke","Resource":"*"}]}'
[System.IO.File]::WriteAllText("$PWD\policy.json", $policy)
aws iam put-role-policy --role-name "<AgentCore実行ロール名>" --policy-name "InvokeQuoteApi" --policy-document file://policy.json
```

ロール名は `agentcore deploy` の出力から確認（例: `AgentCore-order2-default-ApplicationAgentMyAgentRun-XXXX`）。

### 4. バックエンドのデプロイ

```bash
cd backend
sam build
sam deploy --parameter-overrides AgentId=arn:aws:bedrock-agentcore:ap-northeast-1:XXXX:runtime/order2_MyAgent-XXXX
```

デプロイ後、Outputs の `BackendFunctionUrl` を控える。

### 5. フロントエンドの設定

`front/app.js` の `BACKEND_URL` に手順4で取得した Function URL を設定：

```javascript
const BACKEND_URL = "https://xxxxxxxx.lambda-url.ap-northeast-1.on.aws/";
```

### 6. フロントエンドの起動（ローカル）

```bash
cd front
python -m http.server 8080
```

ブラウザで `http://localhost:8080` にアクセス。

### 7. フロントエンドのデプロイ（Amplify）

AWS Amplify コンソールからホスティングを設定し、`front/` フォルダをデプロイ。

## 機能

### 製品情報の検索

- 「製品を教えて」→ 全製品一覧を表示
- 「PROD-001の詳細」→ 特定製品の情報を表示

### 通貨換算

- 「500ドルを日本円に換算して」→ 固定レート (1 USD = 150 JPY) で換算

### 見積書作成（PDF）

- 「ウィジェットA を 10個、顧客名テスト太郎、USD で見積りを作って」
- PDF が S3 に保存され、30日間有効な署名付き URL が返される

## 製品カタログ

| 製品ID | 製品名 | 単価 | 通貨 |
|---|---|---|---|
| PROD-001 | ウィジェットA | 29.99 | USD |
| PROD-002 | ガジェットB | 4,500 | JPY |
| PROD-003 | モジュールC | 89.50 | USD |

## 開発

### テストの実行

```bash
# ToolAPI テスト (19件)
cd tool
python -m pytest tests/ -v

# Agent Property テスト (4件)
cd agent/order2/app/MyAgent
.venv/Scripts/pytest.exe tests/ -v

# Backend テスト (5件)
cd backend/tests
node --test index.test.mjs
```

### ローカルでのエージェントテスト

```bash
cd agent/order2/agentcore
agentcore invoke --prompt "製品を教えて"
```

## 注意事項

- SAM テンプレートのコメントは英語で記述（Requirement 8.4）
- コードコメントは日本語
- 通貨換算は固定レート（1 USD = 150 JPY）のデモ実装
- PDF フォントは NotoSansJP を使用（全角文字対応）
- `file://` プロトコルでフロントエンドを開くと CORS エラーが発生するため、必ずローカルサーバー経由でアクセスすること
