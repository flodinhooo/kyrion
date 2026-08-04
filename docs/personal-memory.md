# Personal Memory Direction

## Goal

Velora should be able to understand an owner progressively across
conversations. This is not model fine-tuning. Kyrion should maintain an
owner-scoped, inspectable memory layer and provide only relevant memories to
the language model for a particular response.

Examples include communication preferences, important people, long-running
projects, values and beliefs that the owner intentionally shares. A later
response may use those memories when relevant, but should not force them into
unrelated topics.

## Required trust model

Conversation text is evidence, not automatically permanent truth. A memory
proposal should include:

- a stable owner identifier;
- a typed category such as preference, person, project or value;
- the concise remembered statement;
- source conversation and message identifiers;
- creation and last-confirmed timestamps;
- confidence and an explicit or inferred origin;
- sensitivity and retention classifications;
- supersession or deletion state.

Kyrion Core owns persistence, access control and deletion. The AI service may
propose memory candidates and retrieve authorised context, but it must not gain
unrestricted database authority.

Sensitive subjects such as religion, health, relationships and political
beliefs require particular care. The first slice should require explicit user
confirmation before retaining sensitive inferred memories. Users must be able
to inspect, correct, forget and disable personal memory independently of chat
history.

## Suggested incremental slice

1. Add a profile-level memory opt-in and clear explanation.
2. Allow an owner to explicitly say “remember this” and create a proposal.
3. Show proposed memories for confirmation before persistence.
4. Add a profile page for viewing, editing and forgetting memories.
5. Retrieve only a small, relevant set for each chat turn and show when memory
   influenced the response.
6. Evaluate extraction quality before considering automatic low-risk memories.

This feature should precede broad external integrations only if the immediate
product priority remains a deeply personal local assistant. It does not replace
conversation context compaction; the two mechanisms solve different problems.

## Implemented first slice

Flyway V6 and the authenticated Core memory API now implement the first five
steps through explicit retention control: memory is disabled by default,
German and English explicit remember requests create owner-scoped proposals,
every proposal requires confirmation, sensitive proposals are visibly marked,
and the profile supports inspection, correction and forgetting. Memory actions
produce data-minimised activity events without recording remembered content.

Core now retrieves at most three deterministically relevant confirmed memories,
uses stricter matching for sensitive records, counts them against the context
budget and makes every selected item visible in the chat. Flyway V7 adds linked
conflicts and an explicit replace/keep-both/forget decision. Superseded records
remain inspectable but no longer influence responses. Automatic inference and
retention expiry remain deliberately unimplemented.
