import type {
  ContactPayload,
  ContactReason,
  Experience,
  Ecosystem,
} from "./validation";

const reasonNames: Record<ContactReason, string> = {
  general: "General inquiry",
  testing: "Private Alpha / Beta interest",
  technical: "Technical question",
  feedback: "Feedback",
  partnership: "Partnership / business",
  other: "Other",
};
const experienceNames: Record<Experience, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
};
const ecosystemNames: Record<Ecosystem, string> = {
  homeAssistant: "Home Assistant",
  philipsHue: "Philips Hue",
  nanoleaf: "Nanoleaf",
  aqara: "Aqara",
  matterThread: "Matter / Thread",
  zigbee: "Zigbee",
  other: "Other",
  none: "None",
};

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function buildContactEmail(data: ContactPayload, requestId: string) {
  const rows: [string, string][] = [
    ["Contact reason", reasonNames[data.reason]],
    ["Name", data.name],
    ["Email", data.email],
    ["Company / organization", data.company || "Not supplied"],
    ["Subject", data.subject],
    ["Message", data.message],
  ];
  if (data.reason === "testing") {
    if (data.country) rows.push(["Country", data.country]);
    if (data.experience)
      rows.push(["Smart-home experience", experienceNames[data.experience]]);
    if (data.ecosystems.length)
      rows.push([
        "Smart-home ecosystem",
        data.ecosystems.map((item) => ecosystemNames[item]).join(", "),
      ]);
  }
  rows.push(
    [
      "Privacy acknowledgement",
      "Agreed: information may be used to respond to this inquiry.",
    ],
    ["Reference", requestId],
  );
  return {
    // Visitor input is never used as a raw header string or mail routing field.
    subject: `[Kyrion contact] ${reasonNames[data.reason]}: ${data.subject}`,
    replyTo: { address: data.email, name: data.name },
    text: `Kyrion website inquiry\n\n${rows.map(([label, value]) => `${label}:\n${value}`).join("\n\n")}`,
    html: `<!doctype html><html lang="en"><head><meta charset="utf-8"></head><body style="font-family:Arial,sans-serif;color:#101e2d"><h1>Kyrion website inquiry</h1>${rows.map(([label, value]) => `<h2 style="font-size:14px;margin:24px 0 8px">${escapeHtml(label)}</h2><p style="white-space:pre-wrap;margin:0">${escapeHtml(value)}</p>`).join("")}</body></html>`,
    disableFileAccess: true,
    disableUrlAccess: true,
  };
}
