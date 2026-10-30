[CmdletBinding()]
param([string]$PiHost, [string]$CoreHost = 'kyrion-core.home')
$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (!$PiHost) { $PiHost = (Get-Content (Join-Path $sourceRoot '.run/dev-recovery/settings.json') -Raw | ConvertFrom-Json).piHost }
if ($PiHost -notmatch '^[a-zA-Z0-9.-]+$' -or $CoreHost -notmatch '^[a-zA-Z0-9.-]+$') { throw 'INVALID_TRUSTED_HOST' }
$probe = @'
import json,pathlib,socket,subprocess,urllib.request,urllib.error,urllib.parse
host=CORE_HOST_PLACEHOLDER
result={'corePort':8080,'dnsResolved':False,'tcpReachable':False,'coreReady':False,'unauthenticatedDevicesDenied':False}
try:
 dns=subprocess.run(['getent','ahostsv4',host],capture_output=True,text=True,timeout=5)
 result['dnsResolved']=dns.returncode==0 and bool(dns.stdout.strip())
 if result['dnsResolved']:
  ip=dns.stdout.split()[0]
  with socket.create_connection((ip,8080),timeout=3): result['tcpReachable']=True
  with urllib.request.urlopen('http://'+host+':8080/actuator/health',timeout=3) as response:
   result['coreReady']=response.status==200 and json.load(response).get('status')=='UP'
  try:
   urllib.request.urlopen('http://'+host+':8080/v1/devices',timeout=3)
  except urllib.error.HTTPError as error: result['unauthenticatedDevicesDenied']=error.code==401
except Exception as error: result['networkError']=type(error).__name__
config=pathlib.Path.home()/'.config/kyrion/voice-satellite.json'
try:
 data=json.loads(config.read_text())
 url=urllib.parse.urlsplit(data.get('core_url',''))
 result['voiceCoreHost']=url.hostname
 result['voiceUsesSameCore']=url.hostname==host and (url.port or 80)==8080
 result['voiceConfigured']=all(data.get(key) for key in ['core_url','satellite_id','credential_file'])
 result['wakeModelPresent']=pathlib.Path(data['model_path']).is_file()
 result['voiceCredentialFilePresent']=pathlib.Path(data['credential_file']).is_file()
except Exception as error: result['voiceConfigError']=type(error).__name__
units=['kyrion-voice-satellite.service','kyrion-spotify-receiver.service','kyrion-media-player.service']
result['userServices']={}
for unit in units:
 state=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True,timeout=3)
 result['userServices'][unit]=state.stdout.strip() in ['active']
gateway=subprocess.run(['systemctl','is-active','kyrion-gateway-agent.service'],capture_output=True,text=True,timeout=3)
result['gatewayServiceActive']=gateway.stdout.strip()=='active'
result['physicalAudioVerified']=False
print(json.dumps(result))
'@
$probe = $probe.Replace('CORE_HOST_PLACEHOLDER', ('"' + $CoreHost + '"'))
$result = $probe | & ssh.exe -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=yes -o HostKeyAlias=kyrion-node.local -i (Join-Path $env:USERPROFILE '.ssh/kyrion_node_ed25519') "flodinho@$PiHost" python3 -
if ($LASTEXITCODE -ne 0) { throw 'PI_PROBE_FAILED' }
$result
$status = $result | ConvertFrom-Json
if (!$status.coreReady -or !$status.unauthenticatedDevicesDenied -or !$status.voiceConfigured) { exit 1 }
