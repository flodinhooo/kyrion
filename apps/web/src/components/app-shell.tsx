"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
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
  t: (typeof messages)[Locale];
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);
type AiStatus = AiServiceStatus | { status: "checking" };

const navigation = [
  ["chat", Icons.chat, "/"],
  ["home", Icons.home, "/home"],
  ["automations", Icons.spark, "/automations"],
  ["knowledge", Icons.book, "/knowledge"],
  ["activity", Icons.activity, "/activity"],
] as const;

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) throw new Error("useWorkspace must be used within AppShell");
  return context;
}

export function AppShell({ children, username }: { children: ReactNode; username: string }) {
  const pathname = usePathname();
  const [locale, setLocale] = useState<Locale>("de");
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [aiStatus, setAiStatus] = useState<AiStatus>({ status: "checking" });
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [speechVoices, setSpeechVoices] = useState<BrowserVoiceOption[]>([]);
  const [selectedVoiceUri, setSelectedVoiceUri] = useState<string | null>(null);
  const [speechRate, setSpeechRateState] = useState(0.95);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const t = messages[locale];

  useEffect(() => {
    let disposed = false;
    async function loadConversations() {
      try {
        const response = await fetch("/api/conversations", { cache: "no-store" });
        const value: unknown = await response.json();
        if (response.ok && isConversationList(value) && !disposed) setConversations(value.items);
      } catch { /* Core availability is represented by an empty history. */ }
    }
    void loadConversations();
    window.addEventListener("kyrion:conversations-updated", loadConversations);
    return () => { disposed = true; window.removeEventListener("kyrion:conversations-updated", loadConversations); };
  }, []);

  useEffect(() => {
    const savedTheme = localStorage.getItem("kyrion-theme");
    const savedLocale = localStorage.getItem("kyrion-locale");
    const preferredDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const nextTheme = savedTheme === "light" || savedTheme === "dark"
      ? savedTheme
      : preferredDark ? "dark" : "light";
    const nextLocale = savedLocale === "en" || savedLocale === "de"
      ? savedLocale
      : navigator.language.toLowerCase().startsWith("de") ? "de" : "en";

    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.lang = nextLocale;
    queueMicrotask(() => {
      setTheme(nextTheme);
      setLocale(nextLocale);
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

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST", headers: csrfHeader() });
    window.location.assign("/login");
  }

  function sidebarContent() {
    return (
      <>
        <div className="brand">
          <div className="brand-mark"><span>K</span></div>
          <div><strong>Kyrion</strong><small>{t.brandTagline}</small></div>
        </div>

        <Link className="new-chat-button" href="/">
          <Icons.plus />
          <span>{t.newConversation}</span>
        </Link>

        <nav aria-label={t.navigation}>
          <p className="section-label">{t.navigation}</p>
          {navigation.map(([key, Icon, href]) => (
            <Link className={`nav-item ${pathname === href ? "active" : ""}`} href={href} key={key}>
              <Icon />
              <span>{t[key]}</span>
            </Link>
          ))}
        </nav>

        <div className="recent-section">
          <p className="section-label">{t.recent}</p>
          {conversations.map((conversation) => (
            <Link className="history-item" href={`/conversations/${conversation.id}`} key={conversation.id}>
              <span>{conversation.title}</span>
              <small>{new Intl.DateTimeFormat(locale, { dateStyle: "short" }).format(new Date(conversation.updatedAt))}</small>
            </Link>
          ))}
        </div>

        <div className="sidebar-footer">
          <Link className={`nav-item ${pathname === "/settings" ? "active" : ""}`} href="/settings"><Icons.settings /><span>{t.settings}</span></Link>
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
      t,
    }}>
      <div className="app-shell">
        <div className="ambient ambient-one" />
        <div className="ambient ambient-two" />
        <aside className="sidebar">{sidebarContent()}</aside>

        <main className="workspace">
          <header className="topbar">
            <Sheet>
              <SheetTrigger asChild>
                <button className="icon-button mobile-menu" type="button" aria-label={t.menu}><Icons.menu /></button>
              </SheetTrigger>
              <SheetContent side="left" showCloseButton={false} className="mobile-sheet">
                <SheetTitle className="sr-only">{t.navigation}</SheetTitle>
                <SheetClose asChild>
                  <button className="icon-button mobile-sheet-close" type="button" aria-label={t.closeMenu}><Icons.close /></button>
                </SheetClose>
                {sidebarContent()}
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
