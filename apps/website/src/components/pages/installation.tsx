import Link from "next/link";
import { github, href, type Dictionary, type Locale } from "@/lib/site";
import { installers } from "@/lib/releases";
import { Container, PageHero } from "../site-ui";

export function DownloadPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const content = t.download;
  return (
    <>
      <PageHero {...content} />
      <Container className="space-y-12 py-14">
        <p className="max-w-3xl text-lg leading-8">{content.localOnly}</p>
        <section aria-labelledby="installer-releases" className="space-y-5">
          <h2 id="installer-releases" className="text-2xl font-medium">
            {content.versions}
          </h2>
          {installers.length === 0 ? (
            <p className="max-w-3xl rounded-xl border border-border p-6 leading-7">
              {content.unpublished}
            </p>
          ) : (
            <ul className="grid gap-5 md:grid-cols-2">
              {installers.map((item) => (
                <li
                  key={`${item.version}/${item.platform}`}
                  className="min-w-0 space-y-3 rounded-xl border border-border p-6"
                >
                  <h3 className="text-xl">
                    {item.version} · {item.platform}
                  </h3>
                  <p>
                    {new Date(item.publishedAt).toLocaleDateString(
                      locale === "de" ? "de-CH" : "en-GB",
                      { timeZone: "UTC" },
                    )}{" "}
                    · {(item.bytes / 1024 ** 2).toFixed(1)} MiB
                  </p>
                  <a
                    className="inline-flex min-h-11 items-center underline"
                    href={item.url}
                  >
                    {content.download}
                  </a>
                  <p className="break-all font-mono text-xs">
                    SHA-256: {item.sha256}
                  </p>
                  <a
                    className="inline-flex min-h-11 items-center underline"
                    href={item.notesUrl}
                  >
                    {content.releaseNotes}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="space-y-5">
          <h2 className="text-2xl font-medium">{content.requirementsTitle}</h2>
          <ul className="list-disc space-y-3 pl-6 leading-7">
            {content.requirements.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
        <section className="space-y-5">
          <h2 className="text-2xl font-medium">{content.helpTitle}</h2>
          <ol className="list-decimal space-y-3 pl-6 leading-7">
            {content.help.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ol>
          <div className="flex flex-wrap gap-x-8 gap-y-3">
            <a
              className="inline-flex min-h-11 items-center underline"
              href={`${github}/blob/HEAD/infrastructure/installer-v1/README.md`}
            >
              {content.instructions}
            </a>
            <a
              className="inline-flex min-h-11 items-center underline"
              href={`${github}/blob/HEAD/docs/installer-requirements.md`}
            >
              {content.status}
            </a>
            <Link
              className="inline-flex min-h-11 items-center underline"
              href={href(locale, "hardware")}
            >
              {content.hardware}
            </Link>
          </div>
        </section>
      </Container>
    </>
  );
}

export function HardwarePage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const content = t.hardware;
  return (
    <>
      <PageHero {...content} />
      <Container className="space-y-10 py-14">
        <p className="max-w-3xl leading-8">{content.note}</p>
        <div className="grid gap-6 md:grid-cols-2">
          {content.scenarios.map((item) => (
            <section
              key={item.title}
              className="space-y-4 rounded-xl border border-border p-6"
            >
              <h2 className="text-2xl font-medium">{item.title}</h2>
              <p className="leading-7 text-muted-foreground">
                {item.description}
              </p>
            </section>
          ))}
        </div>
        <section className="space-y-4">
          <h2 className="text-2xl font-medium">{content.protocolTitle}</h2>
          <dl className="space-y-5">
            {content.protocols.map((item) => (
              <div key={item.title}>
                <dt className="font-medium">{item.title}</dt>
                <dd className="mt-2 max-w-3xl leading-7 text-muted-foreground">
                  {item.description}
                </dd>
              </div>
            ))}
          </dl>
        </section>
        <p className="max-w-3xl leading-7">{content.future}</p>
        <Link
          className="inline-flex min-h-11 items-center underline"
          href={href(locale, "download")}
        >
          {content.back}
        </Link>
      </Container>
    </>
  );
}
