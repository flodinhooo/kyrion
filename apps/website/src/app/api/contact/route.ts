import "server-only";
import { handleContact } from "@/lib/contact/handler";
import { deliverContact } from "@/lib/contact/mail";
import { readContactOrigin } from "@/lib/contact/config";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: Request) {
  return handleContact(request, {
    getAllowedOrigin: () => readContactOrigin(process.env),
    deliver: deliverContact,
    logFailure: (event) => console.error(JSON.stringify(event)),
  });
}
