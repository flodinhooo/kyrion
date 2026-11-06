import { disclosureProxy } from "@/features/calendar/disclosure-server";
export async function GET() { return disclosureProxy("/sources"); }
