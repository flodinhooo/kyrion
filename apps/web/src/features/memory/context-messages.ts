export const contextMessages = {
  de: {
    data: "Eigene kommende Kalendertermine lokal einbeziehen",
    excluded: "Nicht verwendet", blocked: "Gesperrt", local: "Lokal",
    sourceKinds: {
      current_conversation: "Aktuelles Gespräch",
      current_message: "Aktuelle Nachricht",
      personal_memory: "Persönliche Erinnerung",
      conversation_history: "Frühere Gespräche",
      user_preferences: "Benutzerpräferenzen",
      kyrion_data: "Kyrion-Daten",
      documents: "Dokumente"
    },
    title: "Persönliche Kontextquellen", history: "Relevante frühere Gespräche lokal einbeziehen",
    preferences: "Routing-Präferenzen lokal einbeziehen", categories: "Zulässige Memory-Kategorien",
    privacy: "Persönlicher Kontext bleibt lokal. Cloud erhält nur die aktuell bestätigte Nachricht. Gemeinsame Unternehmens- und Dokumentenquellen sind gesperrt.",
    active: "Aktiv", inactive: "Deaktiviert", expiry: "Ablaufzeit (UTC, optional)", source: "Herkunft",
    created: "Erstellt", updated: "Geändert", explicit: "Ausdrücklich vorgeschlagen", reject: "Vorschlag ablehnen",
    inspect: "Kontextquellen ansehen", conversation: "Konversations-ID", turn: "Nachrichten-ID", selected: "Ausgewählt",
  },
  en: {
    data: "Include my upcoming calendar events locally",
    excluded: "Excluded", blocked: "Blocked", local: "Local",
    sourceKinds: {
      current_conversation: "Current conversation",
      current_message: "Current message",
      personal_memory: "Personal memory",
      conversation_history: "Previous conversations",
      user_preferences: "User preferences",
      kyrion_data: "Kyrion data",
      documents: "Documents"
    },
    title: "Personal context sources", history: "Include relevant previous conversations locally",
    preferences: "Include routing preferences locally", categories: "Allowed memory categories",
    privacy: "Personal context stays local. Cloud receives only the current confirmed message. Shared business and document sources are blocked.",
    active: "Active", inactive: "Disabled", expiry: "Expiry (UTC, optional)", source: "Origin",
    created: "Created", updated: "Updated", explicit: "Explicitly proposed", reject: "Reject proposal",
    inspect: "Inspect context sources", conversation: "Conversation ID", turn: "Message ID", selected: "Selected",
  },
} as const;
