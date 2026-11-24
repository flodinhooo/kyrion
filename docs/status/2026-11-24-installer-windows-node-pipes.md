# Windows scoped event transport

The existing gateway event reader now uses native Windows PeekNamedPipe for its
owned anonymous stdout pipe. It has one reader, reads only advertised available
bytes and checks stop/permission state while idle. Existing bounded byte/line
limits and UTF-8 refusal are shared with the Linux selector path. Permission is
checked again before each buffered line is yielded, so revocation after one line
does not release another buffered event.

[Microsoft's pipe semantics](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe)
inform the sole-reader constraint: no other thread issues synchronous reads on
the same owned stdout handle. The existing runtime may terminate the exact child;
it never introduces a competing pipe reader or an unbounded reader thread.

Actual Windows pipes and controlled MQTT bytes pass idle revocation, UTF-8 and
size bounds, EOF and buffered-event revocation tests. No broker, device action or
physical hardware is used. Full agent suites: Windows 106 passed / 16 skipped;
isolated Linux 98 passed / 24 skipped. Logs:
`build/gateway-windows-scoped-pipes-tests.txt` and
`build/isolated-linux/gateway-embedded-full-tests.txt`. Ruff/formatting pass.

This completes the Windows pipe transport component. Windows task runtime and
prepared-node SCM deployment remain disabled until their actual dependencies,
service identity and lifecycle are implemented and verified. The private native
`.20261124.1` artifacts predate this transport addition; their sealed source maps
remain evidence for commit 476a0a7, not for later source changes. Full task
placement and exclusive handoff remain open. Preserve concurrent website work
and the unrelated local-Web tsconfig changes.
