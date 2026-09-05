import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { messages } from "../lib/messages";

vi.mock("@/components/app-shell", () => ({ useWorkspace: () => ({ locale: "en", t: messages.en }) }));
import { SnapshotStatus } from "./snapshot-status";

describe("snapshot feedback", () => {
  it("announces initial loading without claiming a loaded timestamp", () => {
    const html = renderToStaticMarkup(<SnapshotStatus loaded={false} error={false} busy={false} updatedAt={null} onReload={() => {}} />);
    expect(html).toContain('role="status"');
    expect(html).toContain(messages.en.homeLoadingStatus);
    expect(html).not.toContain("<time");
    expect(html).not.toContain(messages.en.snapshotDescription);
  });

  it("keeps the last successful time and warns when old data survives a failure", () => {
    const html = renderToStaticMarkup(<SnapshotStatus loaded error busy={false} updatedAt={new Date("2026-09-05T10:00:00Z")} onReload={() => {}} />);
    expect(html).toContain('role="alert"');
    expect(html).toContain(messages.en.snapshotMayBeStale);
    expect(html).toContain('dateTime="2026-09-05T10:00:00.000Z"');
    expect(html).toContain(messages.en.snapshotRetry);
  });

  it("disables repeated manual reloads while busy", () => {
    const html = renderToStaticMarkup(<SnapshotStatus loaded error={false} busy updatedAt={null} onReload={() => {}} />);
    expect(html).toContain('disabled=""');
    expect(html).toContain(messages.en.homeRefreshingStatus);
  });
});
