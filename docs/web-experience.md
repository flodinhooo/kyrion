# Web experience

## Implemented navigation and layout

The authenticated root opens the room overview. Navigation is ordered Home,
Chat, Lounge, Devices, Automations, Integrations and Activity. Chat history and
the new-conversation action remain local to the chat routes. Device discovery
is an action on the device and home pages instead of a separate navigation
destination. Existing `/home`, `/devices/add` and `/plugins` URLs remain valid.

The Integrations label describes the current internal provider catalog, not a
public plugin marketplace. Each card reads its existing authenticated Core
metadata independently: saved Nanoleaf connections, registered gateways, and
Spotify configuration/account connection. Saved connections and registrations
are labelled as setup, not as proof of live reachability. The gateway card
explicitly directs users to gateway management for radio-service status.

Cards expose loading, setup, configured/connected, missing server configuration
and failed-query states with setup or management links. One failed query does
not discard the other results. Reads time out after ten seconds and are aborted
when leaving the page. A reload action retries the metadata queries without
discovering devices, changing connections or starting playback. Connection
management remains inside each integration.

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

## Snapshot feedback

Home and Devices share a loading/error status panel with the time of the last
fully successful snapshot read. This timestamp describes loading from Core,
not the freshness of every device observation; per-device observation times
remain visible separately. Partial or failed reads do not advance it.

The retry action only reloads snapshot data. It does not repeat a failed write
or command. Device discovery/observation refresh remains a separate action on
Devices. Initial loading does not render empty room cards, and a successfully
loaded empty device catalog provides an add-device action. Failed reads retain
a visible warning when previously loaded data is still shown.

## Keyboard and small-screen navigation

A localized skip link moves keyboard focus to the main workspace. The page
header stays reachable while scrolling; long titles truncate without pushing
navigation controls off-screen. Sidebar and mobile navigation can scroll on
short screens, and the mobile close control has dedicated space above the brand.
Mobile header controls have at least 44-pixel touch targets. Device and
confirmation dialogs scroll within the dynamic viewport, with wrapping
confirmation actions. Focus indicators also cover portalled navigation and
dialogs, plus native disclosure summaries. Visual and assistive-technology
verification remains a separate manual check.

## Authentication and failure recovery

The `/signup` page supports first-owner setup and invitation-based registration
for additional accounts. The original owner creates a one-use, 24-hour code in
Profile > Security. Invited users have the same shared device, room and
integration controls, with separate credentials and personal data. Signup and
the invitation panel explain this access in German and English. RBAC remains
planned; invited accounts cannot issue further invitations.

The September review also localized sign-in/setup, added bounded authentication
requests and distinguished Core unavailability (503) from expired sessions
(401). An open workspace checks session validity on focus and once per minute;
expiry offers a sign-in link without replaying pending actions. Failed room
writes remain visible inside the dialog, and device-management requests restore
their controls after network failures. Preferences and missing browser speech
synthesis cannot prevent the main workspace from loading. Home and Devices
bound requests without automatically retrying commands with unknown outcomes.

See [the pre-image review](status/2026-09-05-web-pre-image-review.md) for
verification and the boundary between local review and the later Pi update.

## Follow-up

Synchronized favorites, a platform-wide issue overview and live home-state
refresh remain follow-up work. Physical device and Spotify playback
verification remain separate from layout and build checks.
