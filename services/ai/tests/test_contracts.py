import pytest
from pydantic import ValidationError

from kyrion_ai.contracts import (
    BenchmarkPromptMetric,
    ChatEvent,
    ChatRequest,
    ModelBenchmarkResult,
    ModelCatalog,
    ModelInfo,
)


def test_chat_request_accepts_web_contract() -> None:
    request = ChatRequest.model_validate(
        {
            "conversationId": "conversation-1",
            "modelId": "gemma3:4b",
            "messages": [{"role": "user", "content": "Hallo"}],
            "locale": "de",
        }
    )

    assert request.conversation_id == "conversation-1"
    assert request.model_id == "gemma3:4b"


@pytest.mark.parametrize("conversation_id", ["", "x" * 129])
def test_chat_request_rejects_invalid_conversation_id(conversation_id: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "conversationId": conversation_id,
                "messages": [{"role": "user", "content": "Hallo"}],
                "locale": "de",
            }
        )


@pytest.mark.parametrize("model_id", ["", "x" * 129])
def test_chat_request_rejects_invalid_model_id(model_id: str) -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(
            {
                "modelId": model_id,
                "messages": [{"role": "user", "content": "Hallo"}],
                "locale": "de",
            }
        )


def test_chat_event_serialises_web_contract_as_ndjson() -> None:
    event = ChatEvent(type="message.delta", message_id="message-1", delta="Hallo")

    assert event.to_ndjson() == (
        b'{"type":"message.delta","messageId":"message-1","delta":"Hallo"}\n'
    )


def test_model_catalog_serialises_web_contract() -> None:
    catalog = ModelCatalog(
        default_model_id="gemma3:4b",
        models=[
            ModelInfo(
                id="gemma3:4b",
                label="gemma3:4b",
                size_bytes=3_300_000_000,
                parameter_size="4.3B",
                quantization="Q4_K_M",
                capabilities=["completion", "vision"],
                context_length=131_072,
            )
        ],
    )

    assert catalog.model_dump(by_alias=True) == {
        "defaultModelId": "gemma3:4b",
        "models": [
            {
                "id": "gemma3:4b",
                "label": "gemma3:4b",
                "sizeBytes": 3_300_000_000,
                "parameterSize": "4.3B",
                "quantization": "Q4_K_M",
                "capabilities": ["completion", "vision"],
                "contextLength": 131_072,
            }
        ],
    }


def test_model_benchmark_serialises_web_contract() -> None:
    result = ModelBenchmarkResult(
        model_id="gemma3:4b",
        warmup_load_ms=1200,
        average_duration_ms=600,
        average_tokens_per_second=50,
        checks_passed=1,
        prompt_count=1,
        prompts=[
            BenchmarkPromptMetric(
                prompt_id="instruction",
                duration_ms=600,
                generated_tokens=30,
                tokens_per_second=50,
                passed=True,
            )
        ],
    )

    payload = result.model_dump(by_alias=True)

    assert payload["modelId"] == "gemma3:4b"
    assert payload["averageTokensPerSecond"] == 50
    assert payload["prompts"][0]["promptId"] == "instruction"
