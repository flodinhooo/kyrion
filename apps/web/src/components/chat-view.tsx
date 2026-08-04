"use client";

import {
  FormEvent,
  KeyboardEvent,
  UIEvent,
  useLayoutEffect,
  useEffect,
  useRef,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { useWorkspace } from "@/components/app-shell";
import { Icons } from "@/components/icons";
import { MarkdownMessage } from "@/components/markdown-message";
import { VoiceMode } from "@/components/voice-mode";
import { ApiChatTransport } from "@/features/chat/client/api-chat-transport";
import type { ChatErrorCode, ChatMessage, ChatRequest } from "@/features/chat/contracts";
import type { Conversation } from "@/features/conversations/contracts";
import { createConversationTitle } from "@/features/conversations/title";
import { csrfHeader } from "@/features/auth/csrf";
import type { PersonalMemory } from "@/features/memory/contracts";
import { isPersonalMemory } from "@/features/memory/contracts";
import { explicitMemoryStatement } from "@/features/memory/explicit-request";

const chatTransport = new ApiChatTransport();
const bottomThreshold = 80;
const errorMessageKeys = {
  MODEL_UNAVAILABLE: "modelUnavailable",
  INVALID_REQUEST: "invalidChatRequest",
  CONVERSATION_NOT_FOUND: "historyUnavailable",
  CONVERSATION_CONFLICT: "conversationSaveError",
  CORE_UNAVAILABLE: "conversationSaveError",
  REQUEST_ABORTED: "streamError",
  STREAM_FAILED: "streamError",
} as const;

function createMessage(role: ChatMessage["role"], content: string, id = crypto.randomUUID()): ChatMessage {
  return { id, role, content, createdAt: new Date().toISOString() };
}

function latestAssistant(messages: ChatMessage[]): ChatMessage | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "assistant") return messages[index] ?? null;
  }
  return null;
}

export function ChatView({ initialConversation }: { initialConversation?: Conversation }) {
  const router = useRouter();
  const { locale, selectedModelId, selectedVoiceUri, speechRate, t } = useWorkspace();
  const [conversationId] = useState(() => initialConversation?.id ?? crypto.randomUUID());
  const [input, setInput] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(initialConversation?.messages ?? []);
  const [conversationTitle, setConversationTitle] = useState(initialConversation?.title ?? null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<ChatErrorCode | null>(null);
  const [wasStopped, setWasStopped] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const [contextCompacted, setContextCompacted] = useState(false);
  const [memoryProposal, setMemoryProposal] = useState<PersonalMemory | null>(null);
  const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const chatStage = useRef<HTMLElement | null>(null);
  const shouldFollowConversation = useRef(true);
  const previousScrollTop = useRef(0);
  const hasPersisted = useRef(Boolean(initialConversation));

  useEffect(() => {
    function updateRenamedTitle(event: Event) {
      const detail = (event as CustomEvent<{ id: string; title: string }>).detail;
      if (detail?.id === conversationId) setConversationTitle(detail.title);
    }
    window.addEventListener("kyrion:conversation-renamed", updateRenamedTitle);
    return () => window.removeEventListener("kyrion:conversation-renamed", updateRenamedTitle);
  }, [conversationId]);

  useLayoutEffect(() => {
    const stage = chatStage.current;
    if (!stage || !shouldFollowConversation.current) return;

    stage.scrollTop = stage.scrollHeight;
  }, [chatMessages, streamError, wasStopped]);

  function handleChatScroll(event: UIEvent<HTMLElement>) {
    const stage = event.currentTarget;
    const distanceFromBottom = stage.scrollHeight - stage.scrollTop - stage.clientHeight;
    const isScrollingUp = stage.scrollTop < previousScrollTop.current;

    if (isScrollingUp) {
      shouldFollowConversation.current = false;
    } else if (distanceFromBottom <= bottomThreshold) {
      shouldFollowConversation.current = true;
    }
    previousScrollTop.current = stage.scrollTop;
  }

  async function submitMessage(rawContent: string): Promise<void> {
    const content = rawContent.trim();
    if (!content || isStreaming) return;

    const userMessage = createMessage("user", content);
    const title = conversationTitle ?? createConversationTitle(
      chatMessages[0]?.content ?? userMessage.content,
      locale,
    );
    const request: ChatRequest = {
      conversationId,
      title,
      modelId: selectedModelId ?? undefined,
      locale,
      message: {
        id: userMessage.id,
        content: userMessage.content,
        createdAt: userMessage.createdAt,
      },
    };
    const controller = new AbortController();
    activeRequest.current = controller;
    shouldFollowConversation.current = true;
    setChatMessages((current) => [...current, userMessage]);
    setInput("");
    setStreamError(null);
    setWasStopped(false);
    setSaveError(false);
    setContextCompacted(false);
    setIsStreaming(true);
    let assistantMessage: ChatMessage | null = null;
    let memoryWasProposed = false;

    try {
      for await (const chatEvent of chatTransport.stream(request, { signal: controller.signal })) {
        if (chatEvent.type === "context.compacted") setContextCompacted(true);
        if (chatEvent.type === "message.started") {
          if (!memoryWasProposed) {
            memoryWasProposed = true;
            void proposeExplicitMemory(content, userMessage);
          }
          assistantMessage = createMessage("assistant", "", chatEvent.messageId);
          setChatMessages((current) => [...current, createMessage("assistant", "", chatEvent.messageId)]);
        }
        if (chatEvent.type === "message.delta") {
          if (assistantMessage?.id === chatEvent.messageId) assistantMessage = { ...assistantMessage, content: assistantMessage.content + chatEvent.delta };
          setChatMessages((current) => current.map((message) =>
            message.id === chatEvent.messageId
              ? { ...message, content: message.content + chatEvent.delta }
              : message,
          ));
        }
        if (chatEvent.type === "error") {
          setChatMessages((current) => current.filter((message) =>
            message.role !== "assistant" || message.content,
          ));
          setStreamError(chatEvent.code);
        }
      }
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) setStreamError("STREAM_FAILED");
    } finally {
      activeRequest.current = null;
      setIsStreaming(false);
      if (assistantMessage?.content) {
        if (!conversationTitle) setConversationTitle(title);
        setSaveError(false);
        window.dispatchEvent(new Event("kyrion:conversations-updated"));
        if (!hasPersisted.current) {
          hasPersisted.current = true;
          router.replace(`/conversations/${conversationId}`);
        }
      }
    }
  }

  async function proposeExplicitMemory(content: string, sourceMessage: ChatMessage) {
    const statement = explicitMemoryStatement(content, locale);
    if (!statement) return;
    try {
      const response = await fetch("/api/memory", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({
          category: "other", content: statement, sensitivity: "sensitive",
          sourceConversationId: conversationId, sourceMessageId: sourceMessage.id,
        }),
      });
      const value: unknown = await response.json();
      if (response.ok && isPersonalMemory(value)) setMemoryProposal(value);
    } catch { /* Chat remains usable when optional memory is unavailable. */ }
  }

  async function resolveMemoryProposal(action: "confirm" | "forget") {
    if (!memoryProposal) return;
    const response = await fetch(
      action === "confirm" ? `/api/memory/${memoryProposal.id}/confirm` : `/api/memory/${memoryProposal.id}`,
      { method: action === "confirm" ? "POST" : "DELETE", headers: csrfHeader() },
    );
    if (response.ok) setMemoryProposal(null);
  }

  function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitMessage(input);
  }

  function stopResponse() {
    if (!activeRequest.current) return;

    setChatMessages((current) => current.filter((message) =>
      message.role !== "assistant" || message.content,
    ));
    setWasStopped(true);
    activeRequest.current.abort();
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key !== "Enter"
      || event.shiftKey
      || event.nativeEvent.isComposing
      || isStreaming
    ) return;

    event.preventDefault();
    event.currentTarget.form?.requestSubmit();
  }

  return (
    <section
      className={`chat-stage ${chatMessages.length ? "has-messages" : ""}`}
      onScroll={handleChatScroll}
      ref={chatStage}
    >
      {chatMessages.length === 0 ? (
        <div className="welcome">
          <button
            className="velora-orb"
            type="button"
            aria-label={t.voiceOpen}
            title={t.voiceOpen}
            onClick={() => setIsVoiceModeOpen(true)}
          >
            <div className="orb-core" /><div className="orb-ring" />
          </button>
          <p className="eyebrow">{t.welcomeEyebrow}</p>
          <h1>{t.welcomeTitle}</h1>
          <p className="welcome-copy">{t.welcomeBody}</p>
          <div className="suggestion-grid">
            <button type="button" onClick={() => setInput(t.suggestionHomeDetail)}><Icons.home /><span><strong>{t.suggestionHome}</strong><small>{t.suggestionHomeDetail}</small></span></button>
            <button type="button" onClick={() => setInput(t.suggestionPlanDetail)}><Icons.clock /><span><strong>{t.suggestionPlan}</strong><small>{t.suggestionPlanDetail}</small></span></button>
            <button type="button" onClick={() => setInput(t.suggestionExploreDetail)}><Icons.spark /><span><strong>{t.suggestionExplore}</strong><small>{t.suggestionExploreDetail}</small></span></button>
          </div>
        </div>
      ) : (
        <div className="message-list" aria-live="polite" aria-busy={isStreaming}>
          {chatMessages.map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="avatar">{message.role === "assistant" ? "V" : "K"}</div>
              <div className="message-body">
                <strong>{message.role === "assistant" ? t.velora : t.you}</strong>
                {message.role === "assistant" && message.content ? (
                  <MarkdownMessage>{message.content}</MarkdownMessage>
                ) : message.role === "assistant" ? (
                  <div className="generation-status" role="status">
                    <span className="visually-hidden">{t.generating}</span>
                    <span aria-hidden="true" />
                    <span aria-hidden="true" />
                    <span aria-hidden="true" />
                  </div>
                ) : (
                  <p className="message-plain-text">{message.content}</p>
                )}
              </div>
            </article>
          ))}
          {streamError && <p className="stream-error" role="alert">{t[errorMessageKeys[streamError]]}</p>}
          {wasStopped && <p className="stream-notice" role="status">{t.responseStopped}</p>}
          {contextCompacted && <p className="stream-notice" role="status">{t.contextCompacted}</p>}
          {memoryProposal && <div className="memory-proposal" role="status"><p>{t.chatMemoryProposed}: {memoryProposal.content}</p><div><button type="button" onClick={() => void resolveMemoryProposal("confirm")}>{t.memoryConfirm}</button><button type="button" onClick={() => void resolveMemoryProposal("forget")}>{t.memoryForget}</button></div></div>}
          {saveError && <p className="stream-error" role="alert">{t.conversationSaveError}</p>}
        </div>
      )}

      <div className="composer-wrap">
        <form className="composer" onSubmit={sendMessage}>
          <textarea aria-label={t.inputPlaceholder} placeholder={t.inputPlaceholder} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={handleInputKeyDown} rows={1} disabled={isStreaming} />
          {isStreaming ? (
            <button type="button" aria-label={t.stop} onClick={stopResponse}><Icons.stop /></button>
          ) : (
            <button type="submit" aria-label={t.send} disabled={!input.trim()}><Icons.send /></button>
          )}
        </form>
        <p>{t.inputHint}</p>
      </div>
      {isVoiceModeOpen && (
        <VoiceMode
          isStreaming={isStreaming}
          latestAssistantMessage={latestAssistant(chatMessages)}
          locale={locale}
          selectedVoiceUri={selectedVoiceUri}
          speechRate={speechRate}
          streamFailed={streamError !== null}
          t={t}
          onClose={() => setIsVoiceModeOpen(false)}
          onSubmit={submitMessage}
        />
      )}
    </section>
  );
}
