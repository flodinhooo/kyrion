import { proxyHa } from "@/features/integrations/home-assistant-proxy";
export function GET(request: Request) { return proxyHa(request, "selection"); }
export function POST(request: Request) { return proxyHa(request, "selection"); }
