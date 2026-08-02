from kyrion_ai.contracts import ChatEvent, ChatRequest


def test_chat_request_accepts_web_contract() -> None:
    request = ChatRequest.model_validate(
        {
            "conversationId": "conversation-1",
            "messages": [{"role": "user", "content": "Hallo"}],
            "locale": "de",
        }
    )

    assert request.conversation_id == "conversation-1"


def test_chat_event_serialises_web_contract_as_ndjson() -> None:
    event = ChatEvent(type="message.delta", message_id="message-1", delta="Hallo")

    assert event.to_ndjson() == (
        b'{"type":"message.delta","messageId":"message-1","delta":"Hallo"}\n'
    )
