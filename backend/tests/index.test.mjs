import { describe, it, beforeEach } from "node:test";
import assert from "node:assert/strict";

// --- モック用のヘルパー ---

/**
 * MockResponseStream: Lambda Function URL のストリーミングレスポンスをシミュレート
 */
class MockResponseStream {
  constructor() {
    this.chunks = [];
    this.ended = false;
    this.metadata = null;
  }

  write(data) {
    this.chunks.push(data);
  }

  end() {
    this.ended = true;
  }

  getBody() {
    return this.chunks.join("");
  }
}

// awslambda グローバルオブジェクトのセットアップ（Lambda 環境シミュレーション）
global.awslambda = {
  streamifyResponse: (fn) => fn,
  HttpResponseStream: {
    from: (stream, metadata) => {
      stream.metadata = metadata;
      return stream;
    },
  },
};

// SDK に依存しないコアロジックをインポート
const { handleRequest } = await import("../src/handler-core.mjs");

describe("BackendFunction", () => {
  let responseStream;
  let mockClient;

  beforeEach(() => {
    responseStream = new MockResponseStream();
    mockClient = { send: async () => ({ completion: null }) };
  });

  describe("リクエストバリデーション", () => {
    it("message が存在しない場合は 400 エラーを返す", async () => {
      const event = {
        requestContext: { http: { method: "POST" } },
        body: JSON.stringify({}),
      };

      await handleRequest(event, responseStream, {}, mockClient);

      assert.equal(responseStream.metadata.statusCode, 400);
      const body = JSON.parse(responseStream.getBody());
      assert.equal(body.error, "無効なリクエストです");
    });

    it("message が空文字の場合は 400 エラーを返す", async () => {
      const event = {
        requestContext: { http: { method: "POST" } },
        body: JSON.stringify({ message: "" }),
      };

      await handleRequest(event, responseStream, {}, mockClient);

      assert.equal(responseStream.metadata.statusCode, 400);
      const body = JSON.parse(responseStream.getBody());
      assert.equal(body.error, "無効なリクエストです");
    });

    it("body が不正な JSON の場合は 400 エラーを返す", async () => {
      const event = {
        requestContext: { http: { method: "POST" } },
        body: "invalid json{{{",
      };

      await handleRequest(event, responseStream, {}, mockClient);

      assert.equal(responseStream.metadata.statusCode, 400);
      const body = JSON.parse(responseStream.getBody());
      assert.equal(body.error, "無効なリクエストです");
    });
  });

  describe("正常なエージェント呼出し", () => {
    it("ストリーミングレスポンスを SSE 形式で返す（contentBlockDelta 形式）", async () => {
      // AgentCore Runtime が返す contentBlockDelta 形式のモック
      const mockChunks = [
        { contentBlockDelta: { delta: { text: "こんにちは" }, contentBlockIndex: 0 } },
        { contentBlockDelta: { delta: { text: "、お手伝いします" }, contentBlockIndex: 0 } },
      ];

      mockClient = {
        send: async () => ({
          stream: (async function* () {
            for (const c of mockChunks) {
              yield c;
            }
          })(),
        }),
      };

      const event = {
        requestContext: { http: { method: "POST" } },
        body: JSON.stringify({ message: "製品を教えて", session_id: "test-session-123" }),
      };

      await handleRequest(event, responseStream, {}, mockClient);

      assert.equal(responseStream.metadata.statusCode, 200);
      assert.equal(responseStream.metadata.headers["Content-Type"], "text/event-stream");

      const body = responseStream.getBody();
      // テキストチャンクが SSE 形式で含まれることを確認
      assert.ok(body.includes('data: {"type":"text","content":"こんにちは"}'));
      assert.ok(body.includes('data: {"type":"text","content":"、お手伝いします"}'));
      // 終了イベントにセッション ID が含まれることを確認
      assert.ok(body.includes('data: {"type":"end","session_id":"test-session-123"}'));
      assert.equal(responseStream.ended, true);
    });
  });

  describe("ツール使用イベントの転送", () => {
    it("contentBlockStart のツール使用イベントを tool_use SSE として返す", async () => {
      // ツール呼出し開始 → テキスト応答のストリームをモック
      const mockChunks = [
        { contentBlockStart: { start: { toolUse: { name: "get_product_info", toolUseId: "tool-1" } } } },
        { contentBlockDelta: { delta: { text: "製品A" }, contentBlockIndex: 1 } },
      ];

      mockClient = {
        send: async () => ({
          stream: (async function* () {
            for (const c of mockChunks) {
              yield c;
            }
          })(),
        }),
      };

      const event = {
        requestContext: { http: { method: "POST" } },
        body: JSON.stringify({ message: "見積もりを作成して", session_id: "sess-tool-test" }),
      };

      await handleRequest(event, responseStream, {}, mockClient);

      assert.equal(responseStream.metadata.statusCode, 200);
      const body = responseStream.getBody();
      // tool_use イベントが SSE に含まれることを確認
      assert.ok(body.includes('data: {"type":"tool_use","name":"get_product_info"}'));
      // テキストも正常に返されることを確認
      assert.ok(body.includes('data: {"type":"text","content":"製品A"}'));
      assert.equal(responseStream.ended, true);
    });
  });

  describe("エージェント呼出し失敗", () => {
    it("エージェントエラー時はエラーイベントを返す", async () => {
      mockClient = {
        send: async () => {
          throw new Error("Agent invocation failed");
        },
      };

      const event = {
        requestContext: { http: { method: "POST" } },
        body: JSON.stringify({ message: "テストメッセージ" }),
      };

      await handleRequest(event, responseStream, {}, mockClient);

      assert.equal(responseStream.metadata.statusCode, 200);
      const body = responseStream.getBody();
      // handler-core.mjs はエラー詳細をそのまま返す
      assert.ok(body.includes("Agent invocation failed"));
      assert.ok(body.includes('"type":"error"'));
      assert.equal(responseStream.ended, true);
    });
  });
});
