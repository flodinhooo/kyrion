"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icons } from "@/components/icons";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { isAiServiceStatus, type AiServiceStatus } from "@/features/status/contracts";
import { isModelCatalog, type ModelCatalog } from "@/features/models/contracts";
import {
  availableBrowserVoices,
  preferredBrowserVoice,
  type BrowserVoiceOption,
} from "@/features/voice/browser-speech";
import { Locale, messages } from "@/lib/messages";
import { csrfHeader } from "@/features/auth/csrf";
import { BrandAsset } from "@/components/brand-asset";
import { isConversationList, type ConversationSummary } from "@/features/conversations/contracts";

type WorkspaceContextValue = {
  username: string;
  locale: Locale;
  modelCatalog: ModelCatalog | null;
  selectedModelId: string | null;
  selectModel: (modelId: string) => void;
  selectedVoiceUri: string | null;
  selectVoice: (voiceUri: string) => void;
  speechRate: number;
  setSpeechRate: (rate: number) => void;
  speechVoices: BrowserVoiceOption[];
  textSize: TextSize;
  setTextSize: (size: TextSize) => void;
  t: (typeof messages)[Locale];
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
type AiStatus = AiServiceStatus | { status: "checking" };
export type TextSize = "standard" | "comfortable" | "large";

const navigation = [
  ["chat", Icons.chat, "/"],
  ["home", Icons.home, "/home"],
  ["devices", Icons.power, "/devices"],
  ["addDevice", Icons.plus, "/devices/add"],
  ["automations", Icons.spark, "/automations"],
  ["plugins", Icons.plugins, "/plugins"],
  ["activity", Icons.activity, "/activity"],
] as const;

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("useWorkspace must be used within AppShell");
  return context;
}

export function AppShell({ children, username }: { children: ReactNode; username: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [locale, setLocale] = useState<Locale>("de");
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [aiStatus, setAiStatus] = useState<AiStatus>({ status: "checking" });
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [speechVoices, setSpeechVoices] = useState<BrowserVoiceOption[]>([]);
  const [selectedVoiceUri, setSelectedVoiceUri] = useState<string | null>(null);
  const [speechRate, setSpeechRateState] = useState(0.95);
  const [textSize, setTextSizeState] = useState<TextSize>("comfortable");
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [historyStatus, setHistoryStatus] = useState<"loading" | "ready" | "error">("loading");
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const t = messages[locale];
  const activeConversationId = pathname.match(/^\/conversations\/([^/]+)$/)?.[1] ?? null;

  useEffect(() => {
    const routeTitles: Array<[RegExp, string]> = [
      [/^\/$/, t.chat],
      [/^\/conversations\//, t.chat],
      [/^\/home/, t.home],
      [/^\/devices$/, t.devices],
      [/^\/devices\/add/, t.addDevice],
      [/^\/automations/, t.automations],
      [/^\/knowledge/, t.knowledge],
      [/^\/plugins\/nanoleaf/, t.nanoleafTitle],
      [/^\/plugins\/spotify/, "Spotify"],
      [/^\/plugins/, t.plugins],
      [/^\/activity/, t.activity],
      [/^\/profile/, t.profile],
      [/^\/settings\/gateways/, t.gatewayTitle],
      [/^\/settings\/models/, t.modelsTitle],
      [/^\/settings\/voice/, t.voiceSettingsTitle],
      [/^\/settings/, t.settings],
    ];
    const pageTitle = routeTitles.find(([pattern]) => pattern.test(pathname))?.[1] ?? "Kyrion";
    document.title = `${pageTitle} · Kyrion`;
  }, [pathname, t]);

  useEffect(() => {
    let disposed = false;
    async function loadConversations() {
      try {
        const response = await fetch("/api/conversations", { cache: "no-store" });
        const value: unknown = await response.json();
        if (!response.ok || !isConversationList(value)) throw new Error("Invalid conversation history");
        if (!disposed) { setConversations(value.items); setHistoryStatus("ready"); }
      } catch { if (!disposed) setHistoryStatus("error"); }
    }
    void loadConversations();
    window.addEventListener("kyrion:conversations-updated", loadConversations);
    return () => { disposed = true; window.removeEventListener("kyrion:conversations-updated", loadConversations); };
  }, []);

  useEffect(() => {
    const savedTheme = localStorage.getItem("kyrion-theme");
    const savedLocale = localStorage.getItem("kyrion-locale");
    const savedTextSize = localStorage.getItem("kyrion-text-size");
    const preferredDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const nextTheme = savedTheme === "light" || savedTheme === "dark"
      ? savedTheme
      : preferredDark ? "dark" : "light";
    const nextLocale = savedLocale === "en" || savedLocale === "de"
      ? savedLocale
      : navigator.language.toLowerCase().startsWith("de") ? "de" : "en";

    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.lang = nextLocale;
    const nextTextSize: TextSize = savedTextSize === "standard" || savedTextSize === "large" || savedTextSize === "comfortable"
      ? savedTextSize
      : "comfortable";
    document.documentElement.dataset.textSize = nextTextSize;
    queueMicrotask(() => {
      setTheme(nextTheme);
      setLocale(nextLocale);
      setTextSizeState(nextTextSize);
    });
  }, []);

  useEffect(() => {
    const loadVoices = () => {
      const voices = availableBrowserVoices();
      if (voices.length > 0) setSpeechVoices(voices);
    };
    const savedRate = Number.parseFloat(localStorage.getItem("kyrion-speech-rate") ?? "");
    if (Number.isFinite(savedRate) && savedRate >= 0.7 && savedRate <= 1.3) {
      queueMicrotask(() => setSpeechRateState(savedRate));
    }
    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
  }, []);

  useEffect(() => {
    if (speechVoices.length === 0) return;
    const compatibleVoices = speechVoices.filter((voice) =>
      voice.lang.toLowerCase().startsWith(locale),
    );
    const savedVoice = localStorage.getItem(`kyrion-voice-${locale}`);
    const nextVoice = compatibleVoices.find((voice) => voice.voiceURI === savedVoice)
      ?? preferredBrowserVoice(compatibleVoices, locale);
    queueMicrotask(() => setSelectedVoiceUri(nextVoice?.voiceURI ?? null));
  }, [locale, speechVoices]);

  useEffect(() => {
    let isDisposed = false;

    async function loadModels() {
      try {
        const response = await fetch("/api/models", { cache: "no-store" });
        const catalog: unknown = await response.json();
        if (!response.ok || !isModelCatalog(catalog)) throw new Error("Invalid model catalog");

        const savedModel = localStorage.getItem("kyrion-model");
        const nextModel = savedModel && catalog.models.some((model) => model.id === savedModel)
          ? savedModel
          : catalog.defaultModelId;
        if (!isDisposed) {
          setModelCatalog(catalog);
          setSelectedModelId(nextModel);
        }
      } catch {
        if (!isDisposed) {
          setModelCatalog(null);
          setSelectedModelId(null);
        }
      }
    }

    void loadModels();
    return () => { isDisposed = true; };
  }, []);

  useEffect(() => {
    let isDisposed = false;

    async function refreshAiStatus() {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        const status: unknown = await response.json();
        if (!response.ok || !isAiServiceStatus(status)) {
          throw new Error("AI service status response is invalid");
        }
        if (!isDisposed) setAiStatus(status);
      } catch {
        if (!isDisposed) setAiStatus({ status: "unavailable" });
      }
    }

    void refreshAiStatus();
    const refreshInterval = window.setInterval(refreshAiStatus, 30_000);

    return () => {
      isDisposed = true;
      window.clearInterval(refreshInterval);
    };
  }, []);

  const aiStatusText = aiStatus.status === "ready"
    ? `${t.aiServiceReady} · ${selectedModelId ?? aiStatus.model}`
    : aiStatus.status === "checking" ? t.aiServiceChecking : t.aiServiceUnavailable;

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    localStorage.setItem("kyrion-theme", nextTheme);
  }

  function toggleLocale() {
    const nextLocale = locale === "de" ? "en" : "de";
    setLocale(nextLocale);
    document.documentElement.lang = nextLocale;
    localStorage.setItem("kyrion-locale", nextLocale);
  }

  function selectModel(modelId: string) {
    if (!modelCatalog?.models.some((model) => model.id === modelId)) return;
    setSelectedModelId(modelId);
    localStorage.setItem("kyrion-model", modelId);
  }

  function selectVoice(voiceUri: string) {
    if (!speechVoices.some((voice) =>
      voice.voiceURI === voiceUri && voice.lang.toLowerCase().startsWith(locale)
    )) return;
    setSelectedVoiceUri(voiceUri);
    localStorage.setItem(`kyrion-voice-${locale}`, voiceUri);
  }

  function setSpeechRate(rate: number) {
    if (!Number.isFinite(rate) || rate < 0.7 || rate > 1.3) return;
    setSpeechRateState(rate);
    localStorage.setItem("kyrion-speech-rate", String(rate));
  }

  function setTextSize(size: TextSize) {
    setTextSizeState(size);
    document.documentElement.dataset.textSize = size;
    localStorage.setItem("kyrion-text-size", size);
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST", headers: csrfHeader() });
    window.location.assign("/login");
  }

  function beginRename(conversation: ConversationSummary) {
    setDeleteConfirmationId(null);
    setEditingConversationId(conversation.id);
    setEditingTitle(conversation.title);
  }

  async function renameConversation(event: React.FormEvent<HTMLFormElement>, id: string) {
    event.preventDefault();
    const title = editingTitle.trim();
    if (!title) return;
    const response = await fetch(`/api/conversations/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ title }),
    });
    if (!response.ok) { setHistoryStatus("error"); return; }
    setConversations((current) => current.map((item) => item.id === id ? { ...item, title } : item));
    setEditingConversationId(null);
    window.dispatchEvent(new CustomEvent("kyrion:conversation-renamed", { detail: { id, title } }));
  }

  async function deleteConversation(id: string) {
    const response = await fetch(`/api/conversations/${id}`, { method: "DELETE", headers: csrfHeader() });
    if (!response.ok) { setHistoryStatus("error"); return; }
    setConversations((current) => current.filter((item) => item.id !== id));
    setDeleteConfirmationId(null);
    if (activeConversationId === id) router.replace("/");
  }

  function sidebarContent(onNavigate?: () => void) {
    return (
      <>
        <div className="brand">
          <BrandAsset variant="wordmark" priority />
        </div>

        <Link className="new-chat-button" href="/" onClick={onNavigate}>
          <Icons.plus />
          <span>{t.newConversation}</span>
        </Link>

        <nav aria-label={t.navigation}>
          <p className="section-label">{t.navigation}</p>
          {navigation.map(([key, Icon, href]) => (
            <Link className={`nav-item ${pathname === href || (href !== "/" && pathname.startsWith(`${href}/`)) ? "active" : ""}`} href={href} key={key} onClick={onNavigate}>
              <Icon />
              <span>{t[key]}</span>
            </Link>
          ))}
        </nav>

        <div className="recent-section">
          <p className="section-label">{t.recent}</p>
          {historyStatus === "loading" && <p className="history-state">{t.historyLoading}</p>}
          {historyStatus === "error" && <p className="history-state error">{t.historyUnavailable}</p>}
          {historyStatus === "ready" && conversations.length === 0 && <p className="history-state">{t.historyEmpty}</p>}
          {conversations.map((conversation) => editingConversationId === conversation.id ? (
            <form className="history-edit" onSubmit={(event) => void renameConversation(event, conversation.id)} key={conversation.id}>
              <input value={editingTitle} onChange={(event) => setEditingTitle(event.target.value)} maxLength={160} aria-label={t.renameConversation} autoFocus />
              <button type="submit" aria-label={t.saveConversationTitle}><Icons.check /></button>
              <button type="button" aria-label={t.cancel} onClick={() => setEditingConversationId(null)}><Icons.close /></button>
            </form>
          ) : (
            <div className={`history-row ${activeConversationId === conversation.id ? "active" : ""}`} key={conversation.id}>
              <Link className="history-item" href={`/conversations/${conversation.id}`} onClick={onNavigate}>
                <span>{conversation.title}</span>
                <small>{new Intl.DateTimeFormat(locale, { dateStyle: "short" }).format(new Date(conversation.updatedAt))}</small>
              </Link>
              {deleteConfirmationId === conversation.id ? (
                <div className="history-confirm" role="group" aria-label={t.confirmDeleteConversation}>
                  <button type="button" className="danger" onClick={() => void deleteConversation(conversation.id)}>{t.delete}</button>
                  <button type="button" onClick={() => setDeleteConfirmationId(null)}>{t.cancel}</button>
                </div>
              ) : (
                <div className="history-actions">
                  <button type="button" aria-label={t.renameConversation} onClick={() => beginRename(conversation)}><Icons.edit /></button>
                  <button type="button" aria-label={t.deleteConversation} onClick={() => { setEditingConversationId(null); setDeleteConfirmationId(conversation.id); }}><Icons.trash /></button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <Link className={`nav-item ${pathname === "/settings" ? "active" : ""}`} href="/settings" onClick={onNavigate}><Icons.settings /><span>{t.settings}</span></Link>
          <div className="connection" title={aiStatusText}>
            <span className={`status-dot status-${aiStatus.status}`} />
            <span>{aiStatusText}</span>
          </div>
          <button className="logout-button" type="button" onClick={logout} title={username}>{t.logout}</button>
        </div>
      </>
    );
  }

  return (
    <WorkspaceContext.Provider value={{
      username,
      locale,
      modelCatalog,
      selectedModelId,
      selectedVoiceUri,
      selectModel,
      selectVoice,
      setSpeechRate,
      speechRate,
      speechVoices,
      textSize,
      setTextSize,
      t,
    }}>
      <div className="app-shell">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <aside className="sidebar">{sidebarContent()}</aside>

        <main className="workspace">
          <header className="topbar">
            <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
              <SheetTrigger asChild>
                <button className="icon-button mobile-menu" type="button" aria-label={t.menu}><Icons.menu /></button>
              </SheetTrigger>
              <SheetContent side="left" showCloseButton={false} className="mobile-sheet">
                <SheetTitle className="sr-only">{t.navigation}</SheetTitle>
                <SheetClose asChild>
                  <button className="icon-button mobile-sheet-close" type="button" aria-label={t.closeMenu}><Icons.close /></button>
                </SheetClose>
                {sidebarContent(() => setMobileMenuOpen(false))}
              </SheetContent>
            </Sheet>
            <div className="topbar-title" title={aiStatusText}>
              <span className={`status-dot status-${aiStatus.status}`} />
              <span>Velora</span>
              <small>{t.localPreview}</small>
            </div>
            <div className="topbar-actions">
              <Link className={`profile-button ${pathname === "/profile" ? "active" : ""}`} href="/profile" aria-label={t.profile} title={username}>
                <span>{username.slice(0, 1).toUpperCase()}</span>
                <Icons.user />
              </Link>
              <button className="language-button" type="button" aria-label={t.language} onClick={toggleLocale}>{locale.toUpperCase()}</button>
              <button className="icon-button" type="button" aria-label={t.theme} onClick={toggleTheme}><Icons.sun /></button>
            </div>
          </header>
          {children}
        </main>
      </div>
    </WorkspaceContext.Provider>
  );
}
