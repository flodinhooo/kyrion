import { spaceProxy } from "@/features/spaces/proxy";
export const GET = (request: Request) => spaceProxy(request, "/v1/space/invitations");
export const POST = (request: Request) => spaceProxy(request, "/v1/space/invitations");
