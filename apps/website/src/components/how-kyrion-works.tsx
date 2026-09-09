"use client";

import {
  AudioLines,
  BatteryCharging,
  Cloud,
  House,
  Lightbulb,
  Radio,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Dictionary } from "@/lib/site";
import { Logo } from "./logo";

export function HowKyrionWorks({ t }: { t: Dictionary["home"] }) {
  const sectionRef = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(false);
  const destinationIcons = [Lightbulb, Radio, AudioLines, BatteryCharging];

  useEffect(() => {
    const section = sectionRef.current;
    if (!section || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.18 },
    );
    observer.observe(section);
    return () => observer.disconnect();
  }, []);

  return (
    <section
      ref={sectionRef}
      className={`how-kyrion-works border-y border-border bg-muted/35 py-20 sm:py-28 ${visible ? "is-visible" : ""}`}
      aria-labelledby="how-kyrion-works-title"
    >
      <div className="mx-auto w-full max-w-7xl px-5 sm:px-8">
        <div className="max-w-2xl">
          <p className="mb-5 font-mono text-[11px] font-medium tracking-[0.16em] text-accent">
            {t.worksEyebrow}
          </p>
          <h2
            id="how-kyrion-works-title"
            className="whitespace-pre-line text-3xl leading-[1.12] font-medium tracking-[-0.045em] sm:text-5xl"
          >
            {t.worksTitle}
          </h2>
          <p className="mt-6 text-base leading-7 text-muted-foreground sm:text-lg">
            {t.worksDescription}
          </p>
        </div>

        <ol className="how-kyrion-flow mt-12 list-none p-0 lg:mt-16">
          <li className="how-kyrion-node how-kyrion-user">
            <div className="how-kyrion-node-card">
              <UserRound aria-hidden="true" className="how-kyrion-icon" />
              <p className="how-kyrion-node-title">{t.worksUser.title}</p>
              <p className="how-kyrion-node-copy">{t.worksUser.description}</p>
            </div>
          </li>
          <li className="how-kyrion-connector" aria-hidden="true" />
          <li className="how-kyrion-node how-kyrion-velora">
            <div className="how-kyrion-node-card">
              <AudioLines aria-hidden="true" className="how-kyrion-icon" />
              <p className="how-kyrion-node-title">{t.worksVelora.title}</p>
              <p className="how-kyrion-node-copy">
                {t.worksVelora.description}
              </p>
              <p className="how-kyrion-node-meta">{t.worksVelora.meta}</p>
            </div>
          </li>
          <li className="how-kyrion-connector" aria-hidden="true" />
          <li className="how-kyrion-node how-kyrion-core">
            <div className="how-kyrion-node-card">
              <div className="how-kyrion-core-mark">
                <Logo mark className="size-10" />
              </div>
              <p className="how-kyrion-node-title">{t.worksCore.title}</p>
              <p className="how-kyrion-node-copy">{t.worksCore.description}</p>
              <p className="how-kyrion-node-meta">{t.worksCore.meta}</p>
              <div className="how-kyrion-cloud-branch">
                <Cloud aria-hidden="true" className="size-4" />
                <span>
                  <strong>{t.worksCloud.title}</strong>
                  <small>{t.worksCloud.description}</small>
                </span>
              </div>
            </div>
          </li>
          <li className="how-kyrion-connector" aria-hidden="true" />
          <li className="how-kyrion-node how-kyrion-environment">
            <div className="how-kyrion-node-card">
              <House aria-hidden="true" className="how-kyrion-icon" />
              <p className="how-kyrion-node-title">
                {t.worksEnvironment.title}
              </p>
              <p className="how-kyrion-node-copy">
                {t.worksEnvironment.description}
              </p>
              <div className="how-kyrion-destinations">
                {t.worksEnvironment.items.map((item, index) => {
                  const Icon = destinationIcons[index];
                  return (
                    <span key={item}>
                      <Icon aria-hidden="true" />
                      {item}
                    </span>
                  );
                })}
              </div>
            </div>
          </li>
        </ol>
        <p className="mt-8 font-mono text-[10px] leading-5 text-muted-foreground">
          {t.worksNote}
        </p>
      </div>
    </section>
  );
}
