import { deliveryProxy } from "@/features/calendar/delivery-server";
type Context = { params: Promise<{ id: string }> };
export async function GET(_request: Request, context: Context) {
  const { id } = await context.params;
  return deliveryProxy(`/household-events/${encodeURIComponent(id)}/deliveries`, "GET");
}
export async function POST(request: Request, context: Context) {
  const { id } = await context.params;
  return deliveryProxy(`/household-events/${encodeURIComponent(id)}/deliveries`, "POST", request);
}
