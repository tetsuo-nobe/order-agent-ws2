import { randomUUID } from "crypto";

/**
 * リクエストボディのバリデーション
 * @param {object} body - パース済みリクエストボディ
 * @returns {{ valid: boolean, error?: string }}
 */
export function validateRequest(body) {
  if (!body || typeof body.message !== "string" || body.message.trim() === "") {
    return { valid: false, error: "無効なリクエストです" };
  }
  return { valid: true };
}

/**
 * エラーレスポンスを書き込む
 * @param {object} responseStream - Lambda レスポンスストリーム
 * @param {number} statusCode - HTTP ステータスコード
 * @param {string} errorMessage - エラーメッセージ
 */
function writeErrorResponse(responseStream, statusCode, errorMessage) {
  const metadata = {
    statusCode,
    headers: {
      "Content-Type": "application/json",
    },
  };

  responseStream = awslambda.HttpResponseStream.from(responseStream, metadata);
  responseStream.write(JSON.stringify({ error: errorMessage }));
  responseStream.end();
}

/**
 * ストリーミングハンドラのコアロジック
 * CORS プリフライト（OPTIONS）は Function URL が自動処理するため、
 * Lambda には到達しない。コード側での CORS ヘッダー付与は不要。
 *
 * @param {object} event - Lambda Function URL イベント
 * @param {object} responseStream - レスポンスストリーム
 * @param {object} _context - Lambda コンテキスト
 * @param {object} client - AWS SDK クライアント（依存性注入）
 */
export async function handleRequest(event, responseStream, _context, client) {
  // リクエストボディのパース
  let body;
  try {
    body = typeof event.body === "string" ? JSON.parse(event.body) : event.body;
  } catch {
    writeErrorResponse(responseStream, 400, "無効なリクエストです");
    return;
  }

  // バリデーション
  const validation = validateRequest(body);
  if (!validation.valid) {
    writeErrorResponse(responseStream, 400, validation.error);
    return;
  }

  // セッション ID の取得または新規生成
  const sessionId = body.session_id || randomUUID();
  const agentId = process.env.AGENT_ID;

  // ストリームレスポンスの開始
  const metadata = {
    statusCode: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
    },
  };
  responseStream = awslambda.HttpResponseStream.from(responseStream, metadata);

  try {
    // AgentCore Runtime エージェントの呼出し
    const response = await client.send({
      agentId: agentId,
      sessionId: sessionId,
      inputText: body.message,
    });

    // AgentCore Runtime のレスポンスストリームを処理
    // レスポンス形式: EventStream with chunk events or stream property
    const stream = response.stream || response.completion || response.body;
    
    if (stream) {
      if (stream[Symbol.asyncIterator]) {
        // AsyncIterable ストリーム
        for await (const event of stream) {
          // chunk イベント: { chunk: { bytes: Uint8Array } }
          if (event.chunk?.bytes) {
            const text = new TextDecoder().decode(event.chunk.bytes);
            responseStream.write(`data: ${JSON.stringify({ type: "text", content: text })}\n\n`);
          }
          // contentBlockDelta イベント (Harness形式)
          else if (event.contentBlockDelta?.delta?.text) {
            const text = event.contentBlockDelta.delta.text;
            responseStream.write(`data: ${JSON.stringify({ type: "text", content: text })}\n\n`);
          }
          // messageStop イベント
          else if (event.messageStop) {
            // ストリーム完了
          }
        }
      } else if (typeof stream === "string") {
        // 非ストリームレスポンス（文字列）
        responseStream.write(`data: ${JSON.stringify({ type: "text", content: stream })}\n\n`);
      }
    }

    // 完了イベント送信
    responseStream.write(`data: ${JSON.stringify({ type: "end", session_id: sessionId })}\n\n`);
    responseStream.end();
  } catch (error) {
    console.error("Agent invocation error:", error);
    // タイムアウトエラーの判定
    if (error.name === "TimeoutError" || error.code === "ETIMEDOUT") {
      responseStream.write(`data: ${JSON.stringify({ type: "error", error: "応答がタイムアウトしました" })}\n\n`);
    } else {
      // デバッグ用: エラー詳細をレスポンスに含める
      const errorDetail = `${error.name || "Error"}: ${error.message || "unknown"}`;
      responseStream.write(`data: ${JSON.stringify({ type: "error", error: errorDetail })}\n\n`);
    }
    responseStream.end();
  }
}
