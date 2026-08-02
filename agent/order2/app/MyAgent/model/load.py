from strands.models.bedrock import BedrockModel


def load_model() -> BedrockModel:
    """Bedrock モデルクライアントを取得する（IAM認証使用）。"""
    return BedrockModel(
        model_id="jp.anthropic.claude-sonnet-4-6",
        region_name="ap-northeast-1",
    )
