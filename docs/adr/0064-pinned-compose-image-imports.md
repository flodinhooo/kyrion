# ADR 0064: Preserve shared image names during Compose installation and recovery

Status: Accepted

Docker load restores archive tags. Authenticate and validate each archive first,
then remove only archive-level naming metadata before loading: Docker RepoTags,
legacy repository mappings and the OCI/containerd reference-name annotations.
Preserve layers/configuration, digests, architecture and licensing annotations.
Verify the resulting image ID and platform. Share this implementation between
fresh installation and the existing update adapter. Configure owned services by
immutable image IDs so unrelated installations' tags are never overwritten.

Docker 29's containerd store can expose an enclosing OCI index digest where a
classic store exposes the image-configuration digest. Accept either only through
a bounded, digest-verified descriptor path to the same authenticated native
configuration. Reject other executable platforms/configurations and nested naming
metadata that would require rewriting content-addressed blobs. Preserve optional
non-executable build attestations. Do not assume a configuration digest alone is
the engine's reported ID. Verify that the actual container source ID also resolves.

For an update from an existing tagged Compose configuration, derive canonical
source pins from the actual owned containers' inspected image IDs. Retain the
original configuration as evidence, but recovery must execute those source IDs,
not whatever a shared tag resolves to later. Journal the known original hash as
a bounded source alias before any configuration change. While startup is fenced,
select canonical pinned source configuration before backup; interrupted original
or pinned writes must reconcile only those approved hashes. Preserve all other
service/configuration fields and refuse unknown layouts. Do not silently adopt
edited user configuration or promise arbitrary legacy repair.

Track the selected source/target image pins with configuration reconciliation.
Repair recreates only the exact journaled pinned template, with the same digest
guard as other known configuration; it must never fall back to mutable tags.

Test real archive rewriting separately from actual Docker import and Compose
transactions. Container execution does not establish systemd or cold-boot
acceptance; any injected prerequisite probe must be explicit in evidence.

References: [Docker load](https://docs.docker.com/reference/cli/docker/image/load/)
and [containerd reference-name handling](https://github.com/containerd/containerd/blob/9e70782d9a0e92900f402b2c7a4e2aa30754503c/core/transfer/image/imagestore.go).
