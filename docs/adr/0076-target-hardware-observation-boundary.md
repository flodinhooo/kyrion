# ADR 0076: Read-only hardware observations use bounded OS-owned tools

Status: Accepted for implementation, 2026-11-14.

Installer inventory must not execute arbitrary PATH entries as administrator.
Use a fixed per-OS tool allowlist, protected/resolved Linux executable paths and
the actual Windows system directory. Child processes receive a minimal trusted
environment, no stdin, bounded runtime and bounded captured data. Unknown/custom
tool locations remain unknown rather than being executed implicitly.

Observe Windows adapters through the system DXGI API and Linux adapters through
kernel sysfs. Keep those observations separate from NVIDIA's typed CLI view;
never add overlapping memory totals or count shared system memory as dedicated
VRAM. NVIDIA CSV units/unknown values are parsed strictly. Existing Ollama
version detection uses a verified loopback listener/API, not an executable from
the user's PATH. Merely finding an executable does not attest a running runtime.

All observations describe the actual host running this installer. Driver/adaptor
presence and memory values are not proof of working inference acceleration or a
performance estimate. Keep usableAcceleration unknown until runtime evidence;
reserve resource budgets as before. Neither probing nor recommendation enables
inference/cloud, changes drivers or takes exclusive ownership of hardware.

Primary API sources reviewed 2026-11-14:
[NVIDIA selective CSV queries](https://docs.nvidia.com/deploy/nvidia-smi/index.html),
[CreateDXGIFactory1](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-createdxgifactory1),
[EnumAdapters1](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/nf-dxgi-idxgifactory1-enumadapters1),
[adapter memory](https://learn.microsoft.com/en-us/windows/win32/api/dxgi/ns-dxgi-dxgi_adapter_desc1).
