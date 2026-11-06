import { disclosureProxy } from "@/features/calendar/disclosure-server";
export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  const search = new URL(request.url).searchParams;
  const query = new URLSearchParams();
  for (const key of ["start", "end"]) { const value = search.get(key); if (value) query.set(key, value); }
  return disclosureProxy(`/sources/${encodeURIComponent(id)}/events?${query}`);
}
