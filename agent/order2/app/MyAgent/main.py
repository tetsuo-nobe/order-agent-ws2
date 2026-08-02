from strands import Agent
from strands.agent.conversation_manager.null_conversation_manager import NullConversationManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from model.load import load_model
from memory.session import get_memory_session_manager
from tools import get_product_info, convert_currency, create_quote

app = BedrockAgentCoreApp()
log = app.logger

DEFAULT_SYSTEM_PROMPT = """
あなたは注文見積り書作成アシスタントです。丁寧で専門的な日本語で対応してください。

あなたの役割:
- 製品カタログの検索と製品情報の提供
- 通貨換算（USD ⇔ JPY）
- 注文見積り書（PDF）の作成支援

以下のツールを使用できます:
- get_product_info: 製品情報を取得します。製品IDを指定すると特定の製品情報を、省略するとすべての製品情報を返します。
- convert_currency: 通貨を換算します。金額、換算元通貨、換算先通貨を指定してください。
- create_quote: 注文見積り書（PDF）を作成します。製品ID、顧客名、数量、通貨を指定してください。

ユーザーの質問に対して適切なツールを使い分け、正確な情報を提供してください。
金額は適切な通貨単位と共に表示し、計算結果は明確に伝えてください。
"""


# エージェントが使用するツールのリスト
tools = [get_product_info, convert_currency, create_quote]

_INLINE_FUNCTION_NAMES = set()


def _make_conversation_manager():
    return NullConversationManager()


def agent_factory():
    cache = {}

    def get_or_create_agent(session_id, user_id):
        _actor_id = user_id
        key = f"{session_id}/{_actor_id}"
        if key not in cache:
            cache[key] = Agent(
                model=load_model(),
                session_manager=get_memory_session_manager(session_id, _actor_id),
                conversation_manager=_make_conversation_manager(),
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                tools=tools,
                hooks=[],
            )
        return cache[key]

    return get_or_create_agent


get_or_create_agent = agent_factory()


def _extract_prompt(payload: dict):
    """harness 形式の messages[]、tool_results[]、または prompt 文字列を受け付ける。"""
    if "messages" in payload:
        return payload["messages"]
    if "tool_results" in payload:
        return [{"role": "user", "content": [{"toolResult": {
            "toolUseId": tr["toolUseId"],
            "status": tr.get("status", "success"),
            "content": tr.get("content", []),
        }} for tr in payload["tool_results"]]}]
    return payload.get("prompt", "")


def _has_inline_function_call(messages) -> bool:
    """messages にインラインファンクションツールの assistant toolUse が含まれていれば True を返す。"""
    if not _INLINE_FUNCTION_NAMES or not isinstance(messages, list):
        return False
    for msg in messages:
        if msg.get("role") == "assistant":
            for block in msg.get("content", []):
                if isinstance(block, dict) and block.get("toolUse", {}).get("name") in _INLINE_FUNCTION_NAMES:
                    return True
    return False


def _is_inline_function_call(event: dict) -> bool:
    """contentBlockStart イベントがインラインファンクションツールのものかを判定する。"""
    if not _INLINE_FUNCTION_NAMES:
        return False
    cbs = event.get("contentBlockStart", {})
    start = cbs.get("start", {})
    tool_use = start.get("toolUse") if isinstance(start, dict) else None
    return tool_use is not None and tool_use.get("name") in _INLINE_FUNCTION_NAMES


@app.entrypoint
async def invoke(payload, context):
    log.info("エージェントを呼び出し中...")

    session_id = getattr(context, 'session_id', 'default-session')
    user_id = getattr(context, 'user_id', 'default-user')
    agent = get_or_create_agent(session_id, user_id)

    prompt = _extract_prompt(payload)

    async for event in agent.stream_async(
        prompt,
    ):
        if not isinstance(event, dict) or "event" not in event:
            continue
        cbs = event["event"].get("contentBlockStart")
        if cbs is not None and not cbs.get("start"):
            continue
        yield event


if __name__ == "__main__":
    app.run()
