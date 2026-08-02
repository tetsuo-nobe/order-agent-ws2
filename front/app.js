// ===================================
// 注文見積りアシスタント - メインスクリプト
// ===================================

// ----- 設定セクション -----
// バックエンドのURL（Lambda Function URL）をここに設定してください
const BACKEND_URL = " https://6kozybnrfsk2upbafub6ohgla40wqspa.lambda-url.ap-northeast-1.on.aws/";
// 例: const BACKEND_URL = "https://xxxxxxxxxx.lambda-url.ap-northeast-1.on.aws/";

// ----- marked.js の設定 -----
// 改行をそのまま <br> に変換する
marked.setOptions({ breaks: true });

// ----- 状態管理 -----
// セッションID（最初のレスポンスで受信後に保持）
let sessionId = null;
// 送信中フラグ（二重送信防止）
let isSending = false;

// ----- DOM 要素の取得 -----
const messageList = document.getElementById("messageList");
const inputForm = document.getElementById("inputForm");
const messageInput = document.getElementById("messageInput");
const sendButton = document.getElementById("sendButton");

// ----- イベントリスナー登録 -----

// フォーム送信イベント（送信ボタンクリック + Enterキー対応）
inputForm.addEventListener("submit", (e) => {
  e.preventDefault();
  handleSend();
});

// ----- メッセージ送信処理 -----

/**
 * メッセージ送信のメイン処理
 * ユーザー入力を取得し、バックエンドへストリーミングリクエストを送信する
 */
async function handleSend() {
  const text = messageInput.value.trim();
  if (!text || isSending) return;

  // バックエンドURLが未設定の場合はエラー表示
  if (!BACKEND_URL) {
    addErrorMessage("バックエンドURLが設定されていません。app.js の BACKEND_URL を設定してください。");
    return;
  }

  // UI状態を送信中に変更
  setInputDisabled(true);
  isSending = true;

  // ユーザーメッセージを画面に追加
  addMessage(text, "user");
  messageInput.value = "";

  // タイピングインジケーターを表示
  const typingIndicator = showTypingIndicator();

  try {
    // バックエンドへリクエスト送信
    const response = await fetch(BACKEND_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: text,
        session_id: sessionId,
      }),
    });

    // タイピングインジケーターを削除
    removeTypingIndicator(typingIndicator);

    // HTTPエラーチェック
    if (!response.ok) {
      throw new Error(`サーバーエラー (${response.status})`);
    }

    // ストリームレスポンスを処理
    await processStream(response);
  } catch (error) {
    // タイピングインジケーターが残っている場合は削除
    removeTypingIndicator(typingIndicator);

    // ネットワークエラーの処理
    console.error("送信エラー:", error);
    addErrorMessage("通信エラーが発生しました。ネットワーク接続を確認して再試行してください。");
  } finally {
    // UI状態を復元
    setInputDisabled(false);
    isSending = false;
    messageInput.focus();
  }
}

// ----- ストリーム処理 -----

/**
 * SSE形式のストリームレスポンスを解析し、リアルタイム表示する
 * @param {Response} response - Fetch APIのレスポンスオブジェクト
 */
async function processStream(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  // エージェントメッセージ用のバブルを事前に作成
  const agentBubble = createMessageElement("", "agent");
  messageList.appendChild(agentBubble);
  scrollToBottom();

  let buffer = ""; // SSEパース用バッファ
  let fullContent = ""; // 完全なメッセージ内容

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // チャンクをデコードしてバッファに追加
      buffer += decoder.decode(value, { stream: true });

      // SSE形式を行ごとにパース（"data: {...}\n\n"）
      const lines = buffer.split("\n");
      buffer = ""; // バッファをリセット

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // 最後の不完全な行はバッファに戻す
        if (i === lines.length - 1 && !line.endsWith("")) {
          buffer = line;
          continue;
        }

        // "data: " プレフィックスを持つ行を処理
        if (line.startsWith("data: ")) {
          const jsonStr = line.slice(6); // "data: " を除去
          try {
            const event = JSON.parse(jsonStr);
            // イベントタイプに応じた処理
            switch (event.type) {
              case "text":
                // テキストチャンクを追加表示
                fullContent += event.content;
                agentBubble.textContent = fullContent;
                scrollToBottom();
                break;

              case "end":
                // ストリーム完了、セッションIDを保存
                if (event.session_id) {
                  sessionId = event.session_id;
                }
                // マークダウンを HTML に変換して表示を更新
                if (fullContent) {
                  agentBubble.classList.add("markdown-body");
                  agentBubble.innerHTML = marked.parse(fullContent);
                  scrollToBottom();
                }
                break;

              case "error":
                // サーバーからのエラーイベント
                addErrorMessage(event.content || "エージェントでエラーが発生しました。");
                break;

              default:
                // 未知のイベントタイプは無視
                break;
            }
          } catch (parseError) {
            // JSONパースに失敗した場合は無視（不完全なデータの可能性）
            console.warn("SSEパースエラー:", parseError);
          }
        }
      }
    }

    // ストリーム完了後の処理
    if (!fullContent) {
      agentBubble.remove();
    } else if (!agentBubble.classList.contains("markdown-body")) {
      // end イベントを受信できなかった場合でもマークダウン変換を適用
      agentBubble.classList.add("markdown-body");
      agentBubble.innerHTML = marked.parse(fullContent);
      scrollToBottom();
    }
  } catch (streamError) {
    // ストリーム中断エラー
    console.error("ストリーム中断:", streamError);
    if (fullContent) {
      // 途中までの応答がある場合はそのまま表示
      addErrorMessage("応答の受信が中断されました。上記は途中までの回答です。");
    } else {
      agentBubble.remove();
      addErrorMessage("応答の受信に失敗しました。再試行してください。");
    }
  }
}

// ----- DOM操作ヘルパー関数 -----

/**
 * メッセージ要素を作成する
 * @param {string} text - メッセージテキスト
 * @param {string} type - メッセージタイプ（"user" | "agent" | "error"）
 * @returns {HTMLElement} 作成されたDOM要素
 */
function createMessageElement(text, type) {
  const div = document.createElement("div");
  div.classList.add("message", type);
  div.textContent = text;
  return div;
}

/**
 * メッセージをチャット画面に追加する
 * @param {string} text - メッセージテキスト
 * @param {string} type - メッセージタイプ（"user" | "agent"）
 */
function addMessage(text, type) {
  const element = createMessageElement(text, type);
  messageList.appendChild(element);
  scrollToBottom();
}

/**
 * エラーメッセージを表示する
 * @param {string} text - エラーメッセージテキスト
 */
function addErrorMessage(text) {
  const element = createMessageElement(text, "error");
  messageList.appendChild(element);
  scrollToBottom();
}

/**
 * タイピングインジケーターを表示する
 * @returns {HTMLElement} インジケーター要素（後で削除するために返す）
 */
function showTypingIndicator() {
  const indicator = document.createElement("div");
  indicator.classList.add("typing-indicator");
  indicator.setAttribute("aria-label", "エージェントが入力中");

  // 3つのドットを追加
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("span");
    dot.classList.add("dot");
    indicator.appendChild(dot);
  }

  messageList.appendChild(indicator);
  scrollToBottom();
  return indicator;
}

/**
 * タイピングインジケーターを削除する
 * @param {HTMLElement} indicator - 削除対象のインジケーター要素
 */
function removeTypingIndicator(indicator) {
  if (indicator && indicator.parentNode) {
    indicator.remove();
  }
}

/**
 * メッセージ一覧を最下部にスクロールする
 */
function scrollToBottom() {
  messageList.scrollTop = messageList.scrollHeight;
}

/**
 * 入力フォームの有効/無効を切り替える
 * @param {boolean} disabled - true で無効化、false で有効化
 */
function setInputDisabled(disabled) {
  messageInput.disabled = disabled;
  sendButton.disabled = disabled;
}
