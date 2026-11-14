# Actual adapter observations and protected inventory tools

The full installer assignment remains open. ADR 0076 closes an inventory trust
gap: probes no longer execute arbitrary PATH tools with administrator rights or
inherit loader hooks/provider credentials. Fixed OS-owned tool paths and minimal
child environments are used, with no stdin, timeout and bounded captured output.
Linux tools/resolved ancestors must be root-owned and not group/world writable.
The actual Windows system directory supplies driver tools; unsupported custom
locations remain unknown. Runtime checks also refuse DOCKER_CONFIG overrides.

CPU descriptions use read-only registry/kernel observations. Windows adapters
use DXGI, including dedicated/shared memory and explicit software-adapter flags;
all COM references are released. Linux DRM/kernel IDs and available VRAM are
read without opening a controller, microphone or device for exclusive access.
Non-PCI/virtual adapters and missing values remain unknown. NVIDIA CSV reports
UUID/name/driver and MiB-based total/free memory, with strict duplicate, bounds,
unit and unknown-value handling. Separate overlapping views are never summed.
Shared system memory is not treated as additional dedicated VRAM.

Ollama inventory reads only the version from a verified loopback listener/API;
it never executes a discovered user PATH program or reads personal model names.
Executable presence and running version are separate observations. Recommendations
show the GPU observations while retaining conservative CPU planning until actual
runtime evidence. Driver/memory presence does not prove acceleration or speed.

## Developer evidence

- Complete suites pass: 435 Windows tests (three skips), 437 isolated Linux tests
  (seventeen skips, including Windows-only DXGI). Ruff/format pass.
- Synthetic CSV/kernel profiles test exact units, unknown/malformed values,
  duplicate IDs, impossible free-memory values and virtual adapters. Real child
  probes test output/time bounds, cleaned credential/loader environment and
  refusal of caller PATH tools. Runtime inventory tests verify version-only GET.
- Actual Windows read-only DXGI enumeration passed and reported one NVIDIA
  hardware adapter plus a separately marked software adapter. Dedicated and
  shared memory are kept separate; free VRAM remains unknown. The fixed Windows
  NVIDIA CLI location was unavailable, so no CLI/driver values were invented.
  Evidence: `build/actual-hardware-observation-20261114.json`.
- Actual isolated Debian/WSL read-only inventory passed. Its non-PCI DRM view
  remains unknown; the protected WSL NVIDIA tool reported 8 GiB VRAM and a current
  free-memory snapshot. This is a guest observation, not bare-Linux GPU generation
  acceptance. Evidence:
  `build/isolated-linux/actual-hardware-observation-20261114.json`.

Neither report contains hardware IDs/model names, credentials or raw environment.
No configuration, drivers, runtime/model downloads or physical devices changed.
Usable acceleration stays unknown and no benchmark was run. R46 remains open for
actual inference/offload validation and target GPU/ARM64 acceptance. Managed
Ollama/AI installation and the remaining scope retain their matrix states.

Native `.20261114.12` packages passed version/inventory/channel/public-CA smoke
and exact raw-source/artifact hash matching. Windows EXE: 12,748,355 bytes,
SHA-256 `2e4ef3ac5e7b2ebe55a7a3e425eb5d6f99a4336413fd5e42d35831103c56303a`.
Linux AMD64 archive: 14,554,828 bytes,
SHA-256 `dea54f44d976e23cca6b1639efb1d51a142e63a7a47350b62716f9c371fcd050`.
Files and adjacent JSON metadata are in `build/native-installer/`, unsigned and
unpublished, explicitly `platformInstallationAccepted: false`.
