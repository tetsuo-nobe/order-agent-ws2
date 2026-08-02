# Implementation Plan: 注文見積り書作成エージェント

## Overview

4層アーキテクチャ（ToolAPI → Agent → Backend → Frontend）を段階的に実装する。各層は AWS SAM テンプレートとアプリケーションコードで構成され、Kiro が生成するのはコードとテンプレートのみ（デプロイは手動）。

## Tasks

- [x] 1. ToolAPI の実装（tool フォルダ）
  - [x] 1.1 SAM テンプレート作成（tool/template.yaml）
    - API Gateway REST API（IAM認証）、CreateQuoteFunction（Python 3.13）、S3バケット、AgentCore Gateway リソースを定義
    - Lambda のポリシーに S3 PutObject と GetObject を付与
    - reportlab の依存関係を requirements.txt で管理
    - _Requirements: 4.1, 4.2, 4.3, 8.1, 8.4, 8.5, 9.1_

  - [x] 1.2 Lambda 関数コード作成（tool/src/handler.py）
    - lambda_handler エントリポイントを実装
    - リクエストパラメータ（product_id, customer_name, quantity, currency）のバリデーション
    - 製品カタログから情報取得、通貨換算、合計金額計算（税抜き）
    - reportlab で PDF 生成（全角文字対応フォント使用）
    - S3 に PDF 保存、30日間有効な署名付き URL 発行
    - エラーハンドリング（400/500レスポンス）
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 1.3 依存関係ファイル作成（tool/src/requirements.txt）
    - reportlab と boto3 を記載
    - _Requirements: 8.5_

  - [ ]* 1.4 ToolAPI ユニットテスト作成（tool/tests/test_handler.py）
    - バリデーションテスト、PDF生成テスト、S3操作テスト
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 2. チェックポイント - ToolAPI の確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Agent の実装（agent フォルダ）
  - [ ] 3.1 エージェントメインコード作成（agent/agent.py）
    - Strands Agents SDK を使用したエージェント定義
    - モデル: jp.anthropic.claude-sonnet-4-6
    - リージョン: ap-northeast-1
    - AgentCore Memory（短期記憶）の設定
    - システムプロンプト定義（日本語対応、見積書作成支援の役割説明）
    - _Requirements: 5.1, 5.2, 5.4, 5.5_

  - [ ] 3.2 ツール関数実装（agent/tools.py）
    - get_product_info: 製品情報取得（全件/ID指定）
    - convert_currency: 通貨換算（固定レート）
    - ProductCatalog と ExchangeRates のデータ定義
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3_

  - [ ]* 3.3 Property テスト: 製品情報検索の正確性
    - **Property 1: 製品情報検索の正確性**
    - 任意の有効な製品IDに対して get_product_info が正しいデータを返すことを検証
    - **Validates: Requirements 1.1, 1.4**

  - [ ]* 3.4 Property テスト: 通貨換算ラウンドトリップ
    - **Property 2: 通貨換算ラウンドトリップ**
    - 任意の正の金額に対して JPY→USD→JPY / USD→JPY→USD が許容誤差内で元に戻ることを検証
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 3.5 Property テスト: 見積金額計算の正確性
    - **Property 3: 見積金額計算の正確性**
    - 任意の有効な製品ID・数量・通貨に対して合計金額が「単価×数量」と一致することを検証
    - **Validates: Requirements 3.1, 3.3**

  - [ ] 3.6 依存関係ファイル作成（agent/requirements.txt）
    - strands-agents, strands-agents-tools, boto3 を記載
    - _Requirements: 5.1, 8.5_

- [ ] 4. チェックポイント - Agent の確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Backend の実装（backend フォルダ）
  - [ ] 5.1 SAM テンプレート作成（backend/template.yaml）
    - BackendFunction（Node.js 20.x）を定義
    - Function URL 設定（AuthType: NONE, InvokeMode: RESPONSE_STREAM）
    - CORS 設定（AllowOrigins: *, AllowMethods: POST/OPTIONS, AllowHeaders: Content-Type）
    - S3バケット（見積書PDF保存用）
    - 必要な IAM ポリシー（bedrock-agent-core:InvokeAgent 等）
    - _Requirements: 6.1, 6.2, 6.5, 8.2, 8.3, 8.4, 8.5, 9.3_

  - [ ] 5.2 Lambda 関数コード作成（backend/src/index.mjs）
    - BedrockAgentCoreClient を使用してエージェント呼出し
    - ストリームレスポンス形式での応答返却
    - セッション ID の管理（リクエストから受取り/新規生成）
    - エラーハンドリング（400/502/504）
    - CORS ヘッダー付与
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ] 5.3 依存関係ファイル作成（backend/src/package.json）
    - @aws-sdk/client-bedrock-agent-core を記載
    - _Requirements: 6.4, 8.5_

  - [ ]* 5.4 Backend ユニットテスト作成（backend/tests/index.test.mjs）
    - リクエストバリデーション、ストリームレスポンス形式、エラーハンドリングのテスト
    - _Requirements: 6.1, 6.3, 6.5_

- [ ] 6. チェックポイント - Backend の確認
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Frontend の実装（front フォルダ）
  - [ ] 7.1 HTML ファイル作成（front/index.html）
    - チャット UI の基本構造（メッセージ一覧、入力欄、送信ボタン）
    - レスポンシブ対応のメタタグ
    - CSS と JS の読み込み
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 7.2 CSS ファイル作成（front/style.css）
    - 見栄えのよいチャット UI デザイン
    - メッセージバブル（ユーザー/エージェント区別）
    - 入力エリアのスタイリング
    - レスポンシブ対応
    - _Requirements: 7.3_

  - [ ] 7.3 JavaScript ファイル作成（front/app.js）
    - Fetch API でストリーミング読取り（ReadableStream）
    - メッセージ送受信のロジック
    - ストリーム中のリアルタイム表示
    - セッション管理（session_id の保持）
    - エラーハンドリング（ネットワークエラー、ストリーム中断）
    - CORS を意識したリクエスト設定
    - _Requirements: 7.1, 7.4, 7.6_

  - [ ] 7.4 デプロイ設定ファイル作成
    - Amplify ホスティング用の設定（必要に応じて amplify.yml 等）
    - _Requirements: 7.5_

- [ ] 8. 最終チェックポイント - 全体確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- タスク `*` 付きはオプションであり、MVP では省略可能
- 各タスクは要件へのトレーサビリティを持つ
- デプロイ作業（sam build/deploy, agentcore CLI）はユーザーが手動で実施
- AgentCore Gateway の具体的な CloudFormation リソースタイプは SAM テンプレート作成時に調査・決定
- reportlab で全角文字対応するには日本語フォント（例: NotoSansJP）の組み込みが必要
- BackendFunction の `@aws-sdk/client-bedrock-agent-core` パッケージ名は実装時に最新 SDK ドキュメントを確認

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.4", "3.1", "3.6"] },
    { "id": 3, "tasks": ["3.2"] },
    { "id": 4, "tasks": ["3.3", "3.4", "3.5"] },
    { "id": 5, "tasks": ["5.1", "5.3"] },
    { "id": 6, "tasks": ["5.2"] },
    { "id": 7, "tasks": ["5.4", "7.1"] },
    { "id": 8, "tasks": ["7.2", "7.3"] },
    { "id": 9, "tasks": ["7.4"] }
  ]
}
```
