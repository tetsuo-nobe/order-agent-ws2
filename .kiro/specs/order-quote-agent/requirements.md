# Requirements Document

## Introduction

注文見積り書を作成する AI エージェントと、それを利用する Web アプリケーションのシステムである。ユーザーは Web アプリケーションのチャット UI を通じてエージェントと対話し、製品情報の問い合わせ、注文の見積り提示、注文見積り書（PDF）の発行を行える。エージェントは Amazon Bedrock AgentCore Runtime 上で動作し、Strands Agents SDK（Python 3.13）で実装される。LLM モデルとして jp.anthropic.claude-sonnet-4-6 を使用し、デプロイリージョンは ap-northeast-1（東京）とする。

## Glossary

- **Agent**: Strands Agents SDK で実装され、Amazon Bedrock AgentCore Runtime 上で動作する AI エージェント
- **WebApp**: JavaScript ベースの SPA として構成されるフロントエンド Web アプリケーション
- **ToolAPI**: 見積書作成のための Lambda 関数とプロキシ統合された Amazon API Gateway REST API
- **AgentCoreGateway**: ToolAPI を AgentCore のツールとして呼び出すための AgentCore Gateway
- **BackendFunction**: フロントエンドとエージェントの仲介を行う Node.js Lambda 関数（Function URL 使用）
- **ProductCatalog**: 製品情報を保持するダミー実装のデータストア（Python 変数）
- **CurrencyConverter**: 通貨換算を行うダミー実装の関数（固定レート）
- **QuotePDF**: 注文見積り書の PDF ファイル
- **S3Bucket**: QuotePDF を保存する Amazon S3 バケット
- **AgentCoreMemory**: AgentCore Memory の短期記憶によるセッション管理機能

## Requirements

### Requirement 1: 製品情報の取得

**User Story:** As a ユーザー, I want エージェントに製品情報を問い合わせたい, so that 製品の名称や単価を確認できる

#### Acceptance Criteria

1. WHEN ユーザーが製品IDを指定して問い合わせた場合, THE Agent SHALL ProductCatalog から該当製品の ID、名称、単価、通貨（USD または JPY）を取得して回答する
2. WHEN ユーザーがすべての製品情報を要求した場合, THE Agent SHALL ProductCatalog からすべての製品情報を取得して回答する
3. THE ProductCatalog SHALL 3 点の製品データを Python 変数として保持する
4. THE ProductCatalog SHALL 各製品について ID、名称、単価、通貨（USD または JPY）の情報を保持する

### Requirement 2: 通貨換算

**User Story:** As a ユーザー, I want 通貨を換算したい, so that 異なる通貨単位で金額を確認できる

#### Acceptance Criteria

1. WHEN JPY から USD への換算が要求された場合, THE CurrencyConverter SHALL 固定レートを使用して JPY を USD に換算する
2. WHEN USD から JPY への換算が要求された場合, THE CurrencyConverter SHALL 固定レートを使用して USD を JPY に換算する
3. THE CurrencyConverter SHALL 換算レートを Python 変数として固定的に保持する

### Requirement 3: 注文見積り書の発行

**User Story:** As a ユーザー, I want 注文見積り書を PDF で発行したい, so that 正式な見積りを顧客に提示できる

#### Acceptance Criteria

1. WHEN ユーザーが製品 ID、顧客名、注文数、見積り通貨を指定した場合, THE ToolAPI SHALL 該当製品の情報を取得し、指定通貨で見積書の PDF を作成する
2. THE QuotePDF SHALL 全角文字に対応したフォントを使用して生成される
3. THE QuotePDF SHALL 税抜き表示（単純な合計のみ）で金額を表示する
4. WHEN QuotePDF が生成された場合, THE ToolAPI SHALL QuotePDF を S3Bucket に保存する
5. WHEN QuotePDF が S3Bucket に保存された場合, THE ToolAPI SHALL 30 日間有効な署名付き URL を発行して返却する

### Requirement 4: AgentCore Gateway によるツール呼出し

**User Story:** As a Agent, I want AgentCore Gateway を通じて ToolAPI を呼び出したい, so that 見積書作成ツールを利用できる

#### Acceptance Criteria

1. THE AgentCoreGateway SHALL Lambda 関数とプロキシ統合された API Gateway REST API を呼び出す形式で構成される
2. THE AgentCoreGateway SHALL IAM 認証により呼び出される
3. THE AgentCoreGateway SHALL SAM テンプレートに CloudFormation の記法でコード化される

### Requirement 5: エージェントの実装とデプロイ

**User Story:** As a 開発者, I want エージェントを AgentCore Runtime にデプロイしたい, so that 本番環境で稼働させられる

#### Acceptance Criteria

1. THE Agent SHALL Strands Agents SDK を使用して Python 3.13 で実装される
2. THE Agent SHALL LLM モデルとして jp.anthropic.claude-sonnet-4-6 を使用する
3. THE Agent SHALL Amazon Bedrock AgentCore Runtime にデプロイされる
4. THE Agent SHALL AgentCoreMemory の短期記憶でセッションを管理する
5. THE Agent SHALL ap-northeast-1（東京）リージョンにデプロイされる

### Requirement 6: バックエンド仲介関数

**User Story:** As a WebApp, I want エージェントの回答をストリームで受信したい, so that リアルタイムに回答を表示できる

#### Acceptance Criteria

1. THE BackendFunction SHALL Node.js で実装される
2. THE BackendFunction SHALL Lambda Function URL を使用してフロントエンドからアクセスされる
3. THE BackendFunction SHALL エージェントの回答をストリーム形式でフロントエンドに返却する
4. THE BackendFunction SHALL BedrockAgentCoreClient を使用して AgentCore Runtime のエージェントを呼び出す
5. THE BackendFunction SHALL CORS に対応したレスポンスヘッダーを返却する

### Requirement 7: フロントエンド Web アプリケーション

**User Story:** As a ユーザー, I want Web ブラウザからエージェントとチャットしたい, so that 製品の問い合わせや見積り書の発行ができる

#### Acceptance Criteria

1. THE WebApp SHALL JavaScript ベースの SPA として構成される
2. THE WebApp SHALL React や Next.js などのフレームワークを使用せずに実装される
3. THE WebApp SHALL 見栄えのよいチャット UI デザインを提供する
4. THE WebApp SHALL BackendFunction からのストリームレスポンスをリアルタイムに表示する
5. THE WebApp SHALL AWS Amplify ホスティングでデプロイされる
6. THE WebApp SHALL CORS を意識した実装とする

### Requirement 8: インフラストラクチャ構成

**User Story:** As a 開発者, I want インフラを AWS SAM でデプロイしたい, so that 再現性のある構築ができる

#### Acceptance Criteria

1. THE ToolAPI SHALL AWS SAM テンプレートでデプロイされる
2. THE BackendFunction SHALL AWS SAM テンプレートでデプロイされる
3. THE S3Bucket SHALL AWS SAM テンプレートでデプロイされる
4. WHILE SAM テンプレートにコメントを記述する場合, THE 開発者 SHALL コメントをすべて半角英語で記述する
5. THE SAM テンプレート SHALL 各 Lambda 関数の依存関係を必要最小限に構成し sam build の実行時間を短縮する

### Requirement 9: フォルダ構成

**User Story:** As a 開発者, I want プロジェクトを機能ごとにフォルダ分けしたい, so that コードの管理がしやすくなる

#### Acceptance Criteria

1. THE プロジェクト SHALL tool フォルダに見積書作成の API Gateway、Lambda 関数、AgentCore Gateway、必要な IAM ポリシー・ロールの SAM テンプレートを配置する
2. THE プロジェクト SHALL agent フォルダに agentcore CLI で作成する AgentCore プロジェクト（AgentCore Runtime、AgentCore Memory）を配置する
3. THE プロジェクト SHALL backend フォルダに S3 バケット、Node.js Lambda 関数（Function URL）、必要な IAM ポリシー・ロールの SAM テンプレートを配置する
4. THE プロジェクト SHALL front フォルダにフロントエンドの SPA を配置する
