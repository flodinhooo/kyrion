import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {children}
    </svg>
  );
}

export const Icons = {
  chat: (props: IconProps) => (
    <IconBase {...props}><path d="M5 17.5 3.5 21l4.2-1.8A9 9 0 1 0 5 17.5Z" /><path d="M8 10h8M8 14h5" /></IconBase>
  ),
  home: (props: IconProps) => (
    <IconBase {...props}><path d="m3 11 9-8 9 8" /><path d="M5 10v10h14V10M9 20v-6h6v6" /></IconBase>
  ),
  spark: (props: IconProps) => (
    <IconBase {...props}><path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Z" /><path d="m19 15 .7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7L19 15Z" /></IconBase>
  ),
  book: (props: IconProps) => (
    <IconBase {...props}><path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22V5.5ZM20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5A3.5 3.5 0 0 1 20 22V5.5Z" /></IconBase>
  ),
  activity: (props: IconProps) => (
    <IconBase {...props}><path d="M4 5h16M4 12h16M4 19h16" /><circle cx="7" cy="5" r="1" fill="currentColor" /><circle cx="11" cy="12" r="1" fill="currentColor" /><circle cx="16" cy="19" r="1" fill="currentColor" /></IconBase>
  ),
  plugins: (props: IconProps) => (
    <IconBase {...props}><path d="M8 3v4M16 3v4M5 7h14v4a7 7 0 0 1-14 0V7Z" /><path d="M9 17v4M15 17v4M7 21h10" /></IconBase>
  ),
  settings: (props: IconProps) => (
    <IconBase {...props}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1a1.7 1.7 0 0 0 1.9.3A1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></IconBase>
  ),
  plus: (props: IconProps) => <IconBase {...props}><path d="M12 5v14M5 12h14" /></IconBase>,
  sun: (props: IconProps) => <IconBase {...props}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.65 17.65l1.42 1.42M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.65 6.35l1.42-1.42" /></IconBase>,
  send: (props: IconProps) => <IconBase {...props}><path d="m22 2-7 20-4-9-9-4 20-7Z" /><path d="M22 2 11 13" /></IconBase>,
  stop: (props: IconProps) => <IconBase {...props}><rect x="7" y="7" width="10" height="10" rx="1" /></IconBase>,
  mic: (props: IconProps) => <IconBase {...props}><rect x="9" y="3" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" /></IconBase>,
  menu: (props: IconProps) => <IconBase {...props}><path d="M4 7h16M4 12h16M4 17h16" /></IconBase>,
  close: (props: IconProps) => <IconBase {...props}><path d="m6 6 12 12M18 6 6 18" /></IconBase>,
  clock: (props: IconProps) => <IconBase {...props}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></IconBase>,
  user: (props: IconProps) => <IconBase {...props}><circle cx="12" cy="8" r="4" /><path d="M4.5 21a7.5 7.5 0 0 1 15 0" /></IconBase>,
  shield: (props: IconProps) => <IconBase {...props}><path d="M12 3 5 6v5c0 4.6 2.8 8.1 7 10 4.2-1.9 7-5.4 7-10V6l-7-3Z" /><path d="m9 12 2 2 4-4" /></IconBase>,
  edit: (props: IconProps) => <IconBase {...props}><path d="M4 20h4l11-11-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></IconBase>,
  trash: (props: IconProps) => <IconBase {...props}><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5" /></IconBase>,
  check: (props: IconProps) => <IconBase {...props}><path d="m5 12 4 4L19 6" /></IconBase>,
};
