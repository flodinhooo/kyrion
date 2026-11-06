import { disclosureProxy } from "@/features/calendar/disclosure-server";
export async function GET() { return disclosureProxy(""); }
export async function PUT(request: Request) { return disclosureProxy("", request, true); }
