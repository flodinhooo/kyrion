import type { Locale } from "@/lib/site";

// Inline artwork keeps flags consistent on platforms without flag emoji support.
export function LanguageFlag({ locale }: { locale: Locale }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 60 40"
      className="h-4 w-6 shrink-0 overflow-hidden rounded-sm"
    >
      {locale === "de" ? (
        <>
          <path fill="#181818" d="M0 0h60v14H0z" />
          <path fill="#d00" d="M0 14h60v13H0z" />
          <path fill="#ffce00" d="M0 27h60v13H0z" />
        </>
      ) : (
        <>
          <path fill="#012169" d="M0 0h60v40H0z" />
          <path stroke="#fff" strokeWidth="8" d="m0 0 60 40M60 0 0 40" />
          <path stroke="#c8102e" strokeWidth="3" d="m0 0 60 40M60 0 0 40" />
          <path stroke="#fff" strokeWidth="13" d="M30 0v40M0 20h60" />
          <path stroke="#c8102e" strokeWidth="7" d="M30 0v40M0 20h60" />
        </>
      )}
    </svg>
  );
}
