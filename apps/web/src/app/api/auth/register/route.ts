import { authenticate } from "../session-cookie";

export async function POST(request: Request) {
  return authenticate(request, "/v1/auth/register", 201);
}
