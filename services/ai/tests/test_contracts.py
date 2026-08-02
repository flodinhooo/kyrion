import pytest
from pydantic import ValidationError

from kyrion_ai.contracts import ChatEvent, ChatRequest


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


def test_chat_event_serialises_web_contract_as_ndjson() -> None:
    event = ChatEvent(type="message.delta", message_id="message-1", delta="Hallo")

    assert event.to_ndjson() == (
        b'{"type":"message.delta","messageId":"message-1","delta":"Hallo"}\n'
    )
