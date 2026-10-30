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
import {orchestrationMessages} from "@/features/models/orchestration-messages";
import {modelMessages} from "@/features/models/messages";
import {knowledgeMessages, knowledgeError} from "@/features/knowledge/messages";
import {isKnowledgeSource, type KnowledgeSource} from "@/features/knowledge/contracts";

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
  const {locale, modelCatalog, selectedModelId, selectedVoiceUri, speechRate, t} = useWorkspace();
  const mt = modelMessages[locale];
  const ot = orchestrationMessages[locale];
  const kt = knowledgeMessages[locale];
  const [knowledgeEnabled, setKnowledgeEnabled] = useState(false);
  const [knowledgeSources, setKnowledgeSources] = useState<Record<string, KnowledgeSource[]>>({});
  const [task, setTask] = useState<"chat" | "analysis" | "code">("chat");
  const [actualModel, setActualModel] = useState<string | null>(null);
  const [fallbackModel, setFallbackModel] = useState<string | null>(null);
  const selectedModel = modelCatalog?.models.find(model => model.id === (selectedModelId ?? modelCatalog.defaultModelId));
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
  const [memoryProposalUnavailable, setMemoryProposalUnavailable] = useState(false);
  const [usedMemories, setUsedMemories] = useState<Array<{ id: string; category: string; content: string; sensitivity: "standard" | "sensitive" }>>([]);
  const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const chatStage = useRef<HTMLElement | null>(null);
  const shouldFollowConversation = useRef(true);
  const previousScrollTop = useRef(0);
  const hasPersisted = useRef(Boolean(initialConversation));
  useEffect(() => {
    if (!initialConversation) return;
    let active = true;
    void fetch(`/api/knowledge/answers/${initialConversation.id}`, {cache: "no-store"}).then(async response => {
      if (!response.ok) return;
      const value: unknown = await response.json();
      if (!Array.isArray(value) || !active) return;
      const grouped: Record<string, KnowledgeSource[]> = {};
      for (const item of value) {
        if (!item || typeof item !== "object" || !("messageId" in item) || typeof item.messageId !== "string"
          || !("source" in item) || !isKnowledgeSource(item.source)) continue;
        (grouped[item.messageId] ??= []).push(item.source);
      }
      setKnowledgeSources(grouped);
    }).catch(() => {
    });
    return () => {
      active = false;
    };
  }, [initialConversation]);

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
    const cloud = !isVoiceModeOpen && selectedModel?.local === false;
    if (cloud && !window.confirm(mt.cloudConfirm.replace("{provider}", selectedModel.provider ?? ""))) return;

    const userMessage = createMessage("user", content);
    const title = conversationTitle ?? createConversationTitle(
      chatMessages[0]?.content ?? userMessage.content,
      locale,
    );
    const request: ChatRequest = {
      conversationId,
      title,
      modelId: isVoiceModeOpen ? "auto" : selectedModelId ?? undefined,
      task: isVoiceModeOpen ? "voice" : task,
      cloudConsent: cloud,
      knowledgeEnabled,
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
    setActualModel(null);
    setFallbackModel(null);
    setWasStopped(false);
    setSaveError(false);
    setContextCompacted(false);
    setMemoryProposalUnavailable(false);
    setUsedMemories([]);
    setIsStreaming(true);
    let assistantMessage: ChatMessage | null = null;
    let memoryWasProposed = false;

    try {
      for await (const chatEvent of chatTransport.stream(request, { signal: controller.signal })) {
        if (!memoryWasProposed) {
          memoryWasProposed = true;
          void proposeExplicitMemory(content, userMessage);
        }
        if (chatEvent.type === "model.selected") setActualModel(`${chatEvent.provider} / ${chatEvent.modelId}`);
        if (chatEvent.type === "routing.fallback") setFallbackModel(chatEvent.profileId);
        if (chatEvent.type === "context.compacted") setContextCompacted(true);
        if (chatEvent.type === "memory.used") setUsedMemories(chatEvent.items);
        if (chatEvent.type === "knowledge.sources") setKnowledgeSources(current => ({
          ...current,
          [chatEvent.messageId]: chatEvent.items
        }));
        if (chatEvent.type === "message.started") {
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
      else setMemoryProposalUnavailable(true);
    } catch { setMemoryProposalUnavailable(true); }
  }

  async function resolveMemoryProposal(action: "confirm" | "replace" | "forget") {
    if (!memoryProposal) return;
    const response = await fetch(
      action === "forget" ? `/api/memory/${memoryProposal.id}` : `/api/memory/${memoryProposal.id}/confirm?resolution=${action === "replace" ? "replace" : "keep"}`,
      { method: action === "forget" ? "DELETE" : "POST", headers: csrfHeader() },
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
                {knowledgeSources[message.id]?.length > 0 && <details>
                  <summary>{kt.sources}</summary>
                  <ul>
                    {knowledgeSources[message.id].map(source => <li key={source.reference}>
                      <a
                        href={`/api/knowledge/documents/${source.documentId}/content`}>{source.filename}{source.page ? ` · ${source.page}` : ""}</a>
                      <small> [{source.reference}]</small>
                    </li>)}
                  </ul>
                </details>}
              </div>
            </article>
          ))}
          {streamError && <p className="stream-error" role="alert">{streamError in kt.errors
            ? knowledgeError(locale, streamError)
            : streamError in mt.errors
            ? mt.errors[streamError as keyof typeof mt.errors]
            : t[errorMessageKeys[streamError as keyof typeof errorMessageKeys]]}</p>}
          {wasStopped && <p className="stream-notice" role="status">{t.responseStopped}</p>}
          {contextCompacted && <p className="stream-notice" role="status">{t.contextCompacted}</p>}
          {memoryProposal && <div className="memory-proposal" role="status"><p>{t.chatMemoryProposed}: {memoryProposal.content}</p>{memoryProposal.conflictsWithMemoryId && <p>{t.memoryConflict}</p>}<div>{memoryProposal.conflictsWithMemoryId ? <><button type="button" onClick={() => void resolveMemoryProposal("replace")}>{t.memoryReplace}</button><button type="button" onClick={() => void resolveMemoryProposal("confirm")}>{t.memoryKeepBoth}</button></> : <button type="button" onClick={() => void resolveMemoryProposal("confirm")}>{t.memoryConfirm}</button>}<button type="button" onClick={() => void resolveMemoryProposal("forget")}>{t.memoryForget}</button></div></div>}
          {memoryProposalUnavailable && <p className="stream-notice" role="status">{t.chatMemoryUnavailable}</p>}
          {usedMemories.length > 0 && <details className="memory-used"><summary>{t.memoryUsed.replace("{count}", String(usedMemories.length))}</summary><ul>{usedMemories.map((memory) => <li key={memory.id}><span>{memory.sensitivity === "sensitive" ? t.memorySensitive : t.memoryStandard}</span>{memory.content}</li>)}</ul></details>}
          {saveError && <p className="stream-error" role="alert">{t.conversationSaveError}</p>}
        </div>
      )}

      <div className="composer-wrap">
        <label><input type="checkbox" checked={knowledgeEnabled}
                      disabled={isStreaming || selectedModel?.local === false}
                      onChange={event => setKnowledgeEnabled(event.target.checked)}/>{kt.toggle}</label>
        <label>{ot.task}<select value={task}
                                onChange={e => setTask(e.target.value === "analysis" ? "analysis" : e.target.value === "code" ? "code" : "chat")}
                                disabled={isStreaming}>{(["chat", "analysis", "code"] as const).map(id => <option
          key={id} value={id}>{ot.taskNames[id]}</option>)}</select></label>
        {selectedModelId === "auto" && <p>{ot.automatic}</p>}
        {actualModel && <p>{ot.actual}: {actualModel}</p>}
        {fallbackModel && <p role="status">{ot.fallbackOccurred}: {fallbackModel}</p>}
        {selectedModel &&
          <p>{mt.selected}: {selectedModel.provider ?? "ollama"} / {selectedModel.label} · {selectedModel.local === false ? mt.cloud : mt.local}</p>}
        {selectedModel?.local === false && <p role="status">{mt.cloudNotice}</p>}
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
