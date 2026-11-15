# Additive Windows service-host capability compatibility

The native updater previously compared the host's entire capability document to
an old four-field object. New independently added diagnostics, backup and ingress
fields consequently caused compatible hosts to be refused. The updater now
strictly validates its required protocol integers and true fence/maintenance
flags, while accepting independent additional capabilities. Duplicate JSON keys,
wrong types, missing guarantees and unknown protocol versions remain refused.
This does not relax artifact/signature/hash checks or authorize a release.

The deterministic protocol test passed. Actual hash-checked Windows native
executables `0.0.0-dev.20261115.12` and `.14` both passed the corrected native
adapter check from separate private fixture paths. Report:
`build/native-additive-capability-report.json`. No services, scheduled tasks,
release downloads or payload activation occurred. Full native update/SCM
acceptance remains separate in the existing disposable-host workflow.

The full installer assignment and ongoing Windows ingress work remain open.
