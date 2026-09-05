"use client";

import { useRef, useState, type ReactNode } from "react";
import { Tabs } from "radix-ui";
import { ChevronLeft, ChevronRight, Film, Headphones, Images, Music2, Server } from "lucide-react";
import { useWorkspace } from "@/components/app-shell";
import { SpotifyPlayer } from "@/features/spotify/spotify-player";
import { LoungeSourceVisible, YouTubeCard } from "@/features/youtube/youtube-card";
import "./lounge.css";

function SourceCarousel({ names, children, active = true }: { names: string[]; children: ReactNode[]; active?: boolean }) {
  const { t } = useWorkspace();
  const track = useRef<HTMLDivElement>(null);
  const [selected, setSelected] = useState(0);
  function select(index: number) {
    const element = track.current;
    if (!element) return;
    element.scrollTo({ left: index * (element.clientWidth + 24), behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  }
  return <div className="lounge-carousel" role="region" aria-label={t.loungeSources}>
    <div className="lounge-source-picker" aria-label={t.loungeSources}>{names.map((name, index) => <button key={name} aria-pressed={index === selected} onClick={() => select(index)}>{name}</button>)}</div>
    <div className="lounge-track-scroll" ref={track} onScroll={(event) => setSelected(Math.round(event.currentTarget.scrollLeft / (event.currentTarget.clientWidth + 24)))}>
      {children.map((child, index) => <div className="lounge-slide" key={names[index]} role="group" aria-label={names[index]} inert={index !== selected}><LoungeSourceVisible value={active && index === selected}>{child}</LoungeSourceVisible></div>)}
    </div>
    <div className="lounge-carousel-controls">
      <button aria-label={t.loungePreviousSource} disabled={selected === 0} onClick={() => select(selected - 1)}><ChevronLeft size={19} /></button>
      <div className="lounge-dots">{names.map((name, index) => <button key={name} aria-label={name} aria-pressed={index === selected} onClick={() => select(index)}><span /></button>)}</div>
      <button aria-label={t.loungeNextSource} disabled={selected === names.length - 1} onClick={() => select(selected + 1)}><ChevronRight size={19} /></button>
    </div>
  </div>;
}

function PlannedSource({ name, description, icon }: { name: string; description: string; icon: ReactNode }) {
  const { t } = useWorkspace();
  return <article className="lounge-planned"><div className="lounge-source-heading"><span className="lounge-source-name">{name}</span><span className="lounge-badge">{t.loungePlanned}</span></div>
    <div className="lounge-empty"><div className="lounge-planned-icon">{icon}</div><h2>{name}</h2><p>{description}</p><span className="lounge-coming">{t.loungeNotAvailable}</span></div>
  </article>;
}

export default function LoungePage() {
  const { t } = useWorkspace();
  const [tab, setTab] = useState("music");
  return <section className="lounge-stage">
    <header className="lounge-header"><div><p className="eyebrow">{t.loungeEyebrow}</p><h1>{t.lounge}</h1><p>{t.loungeDescription}</p></div><Headphones className="lounge-header-icon" size={56} strokeWidth={1} /></header>
    <Tabs.Root value={tab} onValueChange={setTab}>
      <Tabs.List className="lounge-tabs" aria-label={t.loungeCategories}>
        <Tabs.Trigger value="music"><Music2 size={19} />{t.loungeMusic}</Tabs.Trigger>
        <Tabs.Trigger value="videos"><Film size={19} />{t.loungeVideos}</Tabs.Trigger>
        <Tabs.Trigger value="photos"><Images size={19} />{t.loungePhotos}</Tabs.Trigger>
      </Tabs.List>
      <Tabs.Content value="music" forceMount className="lounge-tab-panel">
        <SourceCarousel active={tab === "music"} names={["Spotify", "YouTube Music", "Jellyfin", t.loungeNas]}>
          {[
            <SpotifyPlayer key="spotify" />,
            <YouTubeCard key="youtube" source="MUSIC" />,
            <PlannedSource key="jellyfin" name="Jellyfin" description={t.loungeJellyfinMusicPlan} icon={<Headphones size={60} />} />,
            <PlannedSource key="nas" name={t.loungeNas} description={t.loungeNasMusicPlan} icon={<Server size={60} />} />,
          ]}
        </SourceCarousel>
      </Tabs.Content>
      <Tabs.Content value="videos" forceMount className="lounge-tab-panel">
        <SourceCarousel active={tab === "videos"} names={["YouTube", "Jellyfin", t.loungeNas]}>
          {[
            <YouTubeCard key="youtube" source="VIDEO" />,
            <PlannedSource key="jellyfin" name="Jellyfin" description={t.loungeJellyfinVideoPlan} icon={<Film size={60} />} />,
            <PlannedSource key="nas" name={t.loungeNas} description={t.loungeNasVideoPlan} icon={<Server size={60} />} />,
          ]}
        </SourceCarousel>
      </Tabs.Content>
      <Tabs.Content value="photos" className="lounge-tab-panel">
        <SourceCarousel names={[t.loungeNas, "Jellyfin"]}>
          {[
            <PlannedSource key="nas" name={t.loungeNas} description={t.loungeNasPhotosPlan} icon={<Images size={60} />} />,
            <PlannedSource key="jellyfin" name="Jellyfin" description={t.loungeJellyfinPhotosPlan} icon={<Server size={60} />} />,
          ]}
        </SourceCarousel>
      </Tabs.Content>
    </Tabs.Root>
  </section>;
}
