[CmdletBinding()]
param(
    [ValidateSet('capture','fixture','manual','session')][string]$Mode='capture',
    [ValidateSet(3,5,15)][int]$CaptureSeconds=3,
    [string]$Fixture,
    [switch]$Play,
    [string]$PiHost
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (!$PiHost) { $PiHost=(Get-Content (Join-Path $root '.run/dev-recovery/settings.json') -Raw | ConvertFrom-Json).piHost }
if ($PiHost -notmatch '^[a-zA-Z0-9.-]+$') { throw 'INVALID_TRUSTED_HOST' }
if ($Mode -eq 'fixture' -and !$Fixture) { throw 'FIXTURE_REQUIRED' }
$files=@{}
foreach ($name in @('core_client.py','http_transport.py')) {
    $files[$name]=[IO.File]::ReadAllText((Join-Path $root "services/voice-satellite/src/kyrion_voice_satellite/$name"))
}
$scriptName=if ($Mode -eq 'session') { 'Probe-VoiceSession.py' } else { 'Probe-VeloraHardware.py' }
$arguments=@()
if ($Mode -eq 'capture') { $arguments+=@('--capture-seconds',"$CaptureSeconds") }
if ($Mode -in @('fixture','manual')) { $arguments+='--dialogue' }
if ($Play) { $arguments+='--play' }
$fixtureBase64=$null
if ($Mode -eq 'fixture') {
    $bytes=[IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Fixture).Path)
    if ($bytes.Length -gt 2000000) { throw 'FIXTURE_TOO_LARGE' }
    $fixtureBase64=[Convert]::ToBase64String($bytes)
}
$payload=@{files=$files; probe=[IO.File]::ReadAllText((Join-Path $PSScriptRoot $scriptName)); arguments=$arguments;
    fixture=$fixtureBase64; stopSatellite=($Mode -in @('capture','manual'))} | ConvertTo-Json -Depth 5 -Compress
$encoded=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($payload))
$bootstrap=@'
import base64,json,pathlib,runpy,signal,subprocess,sys,tempfile
payload=json.loads(base64.b64decode('PAYLOAD'))
unit='kyrion-voice-satellite.service'
active=subprocess.run(['systemctl','--user','is-active','--quiet',unit]).returncode==0
stopped=False
def interrupted(*_): raise RuntimeError('OPERATOR_PROBE_INTERRUPTED')
signal.signal(signal.SIGTERM,interrupted)
try:
 if payload['stopSatellite'] and active:
  subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=10); stopped=True
 with tempfile.TemporaryDirectory(prefix='kyrion-operator-probe-') as directory:
  path=pathlib.Path(directory)
  import kyrion_voice_satellite
  kyrion_voice_satellite.__path__.insert(0,str(path))
  for name,content in payload['files'].items(): (path/name).write_text(content)
  script=path/'probe.py'; script.write_text(payload['probe'])
  sys.argv=[str(script)]+payload['arguments']
  if payload['fixture']:
   fixture=path/'synthetic.wav'; fixture.write_bytes(base64.b64decode(payload['fixture']))
   sys.argv+=['--fixture',str(fixture)]
  print(json.dumps({'sdkScope':'operator_process_only','installedPackageChanged':False}),flush=True)
  runpy.run_path(str(script),run_name='__main__')
finally:
 if stopped: subprocess.run(['systemctl','--user','start',unit],check=True,timeout=10)
'@
$bootstrap=$bootstrap.Replace('PAYLOAD',$encoded)
$bootstrap | & ssh.exe -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes -o HostKeyAlias=kyrion-node.local -i (Join-Path $env:USERPROFILE '.ssh/kyrion_node_ed25519') "flodinho@$PiHost" 'timeout 120s /home/flodinho/.local/share/kyrion/voice-satellite/venv/bin/python -'
if ($LASTEXITCODE -ne 0) { throw 'VELORA_OPERATOR_PROBE_FAILED' }
