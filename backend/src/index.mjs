import { SignatureV4 } from "@smithy/signature-v4";
import { Sha256 } from "@aws-crypto/sha256-js";
import { defaultProvider } from "@aws-sdk/credential-provider-node";
import { HttpRequest } from "@smithy/protocol-http";
import { handleRequest } from "./handler-core.mjs";
import https from "https";

const region = process.env.AWS_REGION_NAME || process.env.AWS_REGION || "ap-northeast-1";

// SigV4 署名用のオブジェクト
const signer = new SignatureV4({
  service: "bedrock-agentcore",
  region: region,
  credentials: defaultProvider(),
  sha256: Sha256,
});

/**
 * AgentCore Runtime からの SSE レスポンスをパースして contentBlockDelta イベントを yield する
 */
async function* invokeAgentRuntimeStream(agentRuntimeArn, sessionId, inputText) {
  const hostname = `bedrock-agentcore.${region}.amazonaws.com`;

  // botocore サービスモデルから確認: POST /runtimes/{agentRuntimeArn}/invocations
  const encodedArn = encodeURIComponent(agentRuntimeArn);
  const path = `/runtimes/${encodedArn}/invocations`;

  const payload = JSON.stringify({
    prompt: inputText,
  });

  // HTTP リクエストオブジェクトの作成
  const request = new HttpRequest({
    method: "POST",
    hostname: hostname,
    path: path,
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      "Host": hostname,
      "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sessionId,
    },
    body: payload,
  });

  // SigV4 で署名
  const signedRequest = await signer.sign(request);

  // HTTPS リクエストを実行し、レスポンスを SSE としてパースする
  const response = await new Promise((resolve, reject) => {
    const req = https.request(
      {
        hostname: signedRequest.hostname,
        path: signedRequest.path,
        method: signedRequest.method,
        headers: signedRequest.headers,
      },
      (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res);
        } else {
          let data = "";
          res.on("data", (chunk) => { data += chunk.toString(); });
          res.on("end", () => { reject(new Error(`AgentCore returned ${res.statusCode}: ${data}`)); });
        }
      }
    );
    req.on("error", reject);
    req.write(payload);
    req.end();
  });

  // Node.js Readable Stream を行ごとにパースして SSE イベントを yield
  let buffer = "";
  for await (const chunk of response) {
    buffer += chunk.toString("utf-8");

    // SSE は "\n\n" で区切られる
    const parts = buffer.split("\n\n");
    buffer = parts.pop(); // 最後の不完全な部分をバッファに残す

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;

      const jsonStr = line.slice(6); // "data: " を除去
      try {
        const event = JSON.parse(jsonStr);
        // contentBlockStart イベント（ツール呼出し開始）
        if (event.event?.contentBlockStart?.start?.toolUse) {
          yield { contentBlockStart: { start: { toolUse: event.event.contentBlockStart.start.toolUse } } };
        }
        // contentBlockDelta イベントからテキストを抽出
        else if (event.event?.contentBlockDelta?.delta?.text) {
          yield { contentBlockDelta: event.event.contentBlockDelta };
        }
        // messageStop イベント
        else if (event.event?.messageStop) {
          yield { messageStop: event.event.messageStop };
        }
      } catch {
        // パース失敗は無視
      }
    }
  }

  // バッファに残ったデータを処理
  if (buffer.trim()) {
    const line = buffer.trim();
    if (line.startsWith("data: ")) {
      try {
        const event = JSON.parse(line.slice(6));
        // contentBlockStart イベント（ツール呼出し開始）
        if (event.event?.contentBlockStart?.start?.toolUse) {
          yield { contentBlockStart: { start: { toolUse: event.event.contentBlockStart.start.toolUse } } };
        } else if (event.event?.contentBlockDelta?.delta?.text) {
          yield { contentBlockDelta: event.event.contentBlockDelta };
        } else if (event.event?.messageStop) {
          yield { messageStop: event.event.messageStop };
        }
      } catch {
        // パース失敗は無視
      }
    }
  }
}

// クライアントアダプター（handler-core.mjs の client インターフェースに合わせる）
const agentClient = {
  async send(params) {
    const stream = invokeAgentRuntimeStream(
      params.agentId,
      params.sessionId,
      params.inputText
    );
    return { stream };
  },
};

/**
 * Lambda Function URL のストリーミングハンドラ
 */
export const handler = awslambda.streamifyResponse(
  async (event, responseStream, context) => {
    await handleRequest(event, responseStream, context, agentClient);
  }
);
