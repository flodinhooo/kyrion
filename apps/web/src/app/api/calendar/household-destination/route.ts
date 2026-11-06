import { deliveryProxy } from "@/features/calendar/delivery-server";
export async function GET() { return deliveryProxy("/household-destination", "GET"); }
export async function PUT(request: Request) { return deliveryProxy("/household-destination", "PUT", request); }
