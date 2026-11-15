# Prepared-agent storage on Windows

The full installer assignment remains open. ADR 0090 extends the existing
prepared enrollment/AgentConfig implementation with typed Windows APIs; it does
not introduce another account, Space, node identity or deployment journal.

## Implemented and developer-tested

- Native owner-bound protected DACL creation and actual descriptor inspection;
  only the current identity, System and Administrators may access managed files.
  Trusted writable-ancestor checks additionally recognize resolved TrustedInstaller.
- Local fixed NTFS restriction; rejection of device/UNC/alternate-stream and
  ambiguous names, reparse components, hard links and broad credential ACLs.
- Flushed private publication with a native no-overwrite move; exclusive native
  lock handles with actual cross-process contention and release on child death.
- Existing prepared pending/configuration records use these primitives on Windows.
  Lost acknowledgements preserve the original credential/version; a committed
  configuration can finish cleanup without another enrollment request.
- The local data folder comes from the Windows known-folder API, with matched
  COM initialization/resource cleanup. Private temporary input directories use
  exclusive creation and bounded nonrecursive cleanup. Existing directory rights
  are never weakened or silently repaired.
- Prepared Linux publication now uses actual `renameat2(RENAME_NOREPLACE)` and
  parent fsync. A real SIGKILL after rename leaves one readable private file,
  without the former temporary-hard-link window. FIFO input is refused without
  waiting for a writer. Unsupported primitive/filesystem support refuses safely;
  there is no overwrite fallback. Legacy non-prepared saves are unchanged.

Windows targeted SDK/enrollment tests: eighteen passed, one symbolic-link test
skipped because the test user lacks that privilege. Core enrollment success
responses in these enrollment tests are explicit protocol doubles; file and
lock operations are actual Windows APIs. Full agent suites: 75 Windows passed /
23 skipped; 79 Linux passed /19 Windows-specific skips. Ruff passes. Private
Windows test roots were created beneath the validated local data folder and
removed only after exact scope/reparse checks. The ordinary development Temp
ancestor has additional writable principals and was correctly refused; its ACL
was preserved rather than modified to make tests pass.

## Still in progress

The curated installer source allowlist includes the new module. This checkpoint
does not yet enable the Windows foreground installer path, Windows health/runtime
or a prepared-node SCM profile. Actual Core/TLS Windows enrollment, exact target
Space binding, unknown hardware values, one-directory host distribution and the
complete Windows service journey remain source/integration work. The previous
private native artifact `.15` predates this checkpoint. It is not presented as
containing this new module, and no new artifact was published.

Local reports: `build/gateway-windows-storage-tests.txt` and
`build/isolated-linux/gateway-embedded-full-tests.txt`. No actual household device,
productive installation, release, cloud model or external account was used.
