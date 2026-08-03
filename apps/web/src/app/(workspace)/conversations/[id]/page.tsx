import { notFound, redirect } from "next/navigation";
import { ChatView } from "@/components/chat-view";
import { CORE_SERVICE_URL, sessionToken } from "@/lib/server-auth";
import { isConversation } from "@/features/conversations/contracts";

export default async function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await sessionToken();
  if (!token) redirect("/login");
  const response = await fetch(`${CORE_SERVICE_URL}/v1/conversations/${id}`, {
    headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
  }).catch(() => null);
  if (!response?.ok) notFound();
  const value: unknown = await response.json();
  if (!isConversation(value)) notFound();
  return <ChatView initialConversation={value} />;
}
