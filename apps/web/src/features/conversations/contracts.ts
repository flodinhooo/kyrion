import type { ChatMessage } from "@/features/chat/contracts";

export type ConversationSummary = { id: string; title: string; createdAt: string; updatedAt: string };
export type Conversation = ConversationSummary & { messages: ChatMessage[] };
export type ConversationList = { items: ConversationSummary[] };

export function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<Conversation>;
  return typeof item.id === "string" && typeof item.title === "string"
    && typeof item.createdAt === "string" && typeof item.updatedAt === "string"
    && Array.isArray(item.messages) && item.messages.every((message) =>
      typeof message?.id === "string" && (message.role === "user" || message.role === "assistant")
      && typeof message.content === "string" && typeof message.createdAt === "string");
}

export function isConversationList(value: unknown): value is ConversationList {
  return !!value && typeof value === "object" && Array.isArray((value as ConversationList).items)
    && (value as ConversationList).items.every((item) => typeof item.id === "string" && typeof item.title === "string");
}
