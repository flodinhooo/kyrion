# Web experience

## Implemented navigation and layout

The authenticated root opens the room overview. Navigation is ordered Home,
Chat, Lounge, Devices, Automations, Integrations and Activity. Chat history and
the new-conversation action remain local to the chat routes. Device discovery
is an action on the device and home pages instead of a separate navigation
destination. Existing `/home`, `/devices/add` and `/plugins` URLs remain valid.

The Integrations label describes the current internal provider catalog, not a
public plugin marketplace. Catalog badges describe availability of the
integration; they do not claim a live connection. Connection management remains
inside each integration.

Shared workspace styles provide compact headings, consistent content widths,
aligned integration actions, visible keyboard focus and responsive settings
cards. Large decorative background glows are removed from the workspace.
German and English labels are maintained together.

Home displays room and device counts from successfully loaded Core data, plus
the number of devices reported online. These are observed states, not a live
connectivity guarantee. Loading and failure do not display fabricated zero
counts. An empty home provides an explicit create-room action. Existing room
assignment and device control continue through the same Core APIs.

## Room favorites and device status

Home offers up to eight owner-selected room shortcuts. Selection is a browser
presentation preference, stored under an owner-name-scoped localStorage key;
it does not grant permissions and is not synchronized between browsers.
Only identifiers are stored. Stored input is validated and bounded, deleted
rooms are omitted, and unavailable storage leaves an in-memory selection with
a visible explanation. Opening a favorite uses the existing room dialog.

The device-status section lists Core-reported offline, degraded and unknown
devices separately from online devices. A manual refresh reloads the existing
Core snapshot; it does not execute device commands or force provider discovery.
Failed refreshes display an error and suppress the device-status section until
another load succeeds. This is not a live health monitor.

## Device search and filters

The device overview filters its existing Core snapshot by device/display name,
hardware name or room name, plus device class and availability. Search words
are combined, ignoring case and accents, with German sharp-s matching `ss`.
Filtering changes presentation only; it never sends commands or changes room
assignments. The result count and reset action remain visible, and a dedicated
empty-result state explains how to recover.

Room-wide switches are hidden while filters are active so a room action cannot
affect devices hidden by the current view. Individual device controls and their
existing Core validation remain available. Empty rooms stay visible in the
unfiltered view for room management.

## Everyday device cards

Device cards keep the name, availability, observation time, current readings
and daily controls visible. A native, initially collapsed Manage disclosure
contains model/integration details, renaming, classification, room assignment,
removal and button bindings. Expanding or closing it performs no command and
preserves edits while the card remains mounted. Removal still opens the existing
confirmation dialog. Full light controls open through an explicit keyboard-
accessible button rather than a click handler on the entire article.

## Follow-up

Synchronized favorites, a platform-wide issue overview and live home-state
refresh remain follow-up work. Physical device and Spotify playback
verification remain separate from layout and build checks.
