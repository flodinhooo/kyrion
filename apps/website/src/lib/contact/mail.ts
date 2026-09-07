import "server-only";
import nodemailer from "nodemailer";
import { buildContactEmail } from "./email";
import { readSmtpConfig } from "./config";
import type { ContactPayload } from "./validation";

export async function deliverContact(
  data: ContactPayload,
  requestId: string,
): Promise<void> {
  const config = readSmtpConfig(process.env);
  const transporter = nodemailer.createTransport(config.transport);
  try {
    const result = await transporter.sendMail({
      ...buildContactEmail(data, requestId),
      from: { address: config.from, name: "Kyrion website" },
      to: { address: config.to, name: "" },
      envelope: { from: config.from, to: [config.to] },
    });
    if (result.accepted.length !== 1 || result.rejected.length > 0)
      throw new Error("CONTACT_RECIPIENT_REJECTED");
  } finally {
    transporter.close();
  }
}
