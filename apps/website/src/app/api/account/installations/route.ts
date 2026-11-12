import "server-only";
import {cookies} from "next/headers";
import {accountConfig} from "@/lib/account/config";
import {AccountStore, database} from "@/lib/account/store";
import {InstallationStore} from "@/lib/account/installations";

export const runtime = "nodejs";

export async function GET() {
  const headers = {"Cache-Control": "no-store"};
  try {
    const config = accountConfig();
    if (!config) return Response.json({code: "ACCOUNT_DISABLED"}, {status: 503, headers});
    const pool = database(config.databaseUrl);
    const session = await new AccountStore(pool, config).session((await cookies()).get("kyrion_website_session")?.value ?? "");
    if (!session) return Response.json({code: "UNAUTHENTICATED"}, {status: 401, headers});
    return Response.json({installations: await new InstallationStore(pool).list(session.id)}, {headers});
  } catch {
    return Response.json({code: "ACCOUNT_UNAVAILABLE"}, {status: 503, headers});
  }
}
