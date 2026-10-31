import { spaceProxy } from "@/features/spaces/proxy";
export const GET = (request: Request) => spaceProxy(request, "/v1/space");
export const PUT = (request: Request) => spaceProxy(request, "/v1/space");
