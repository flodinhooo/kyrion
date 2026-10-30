import {execFile} from 'node:child_process';
import {readFile, readdir, mkdir, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

// Raw Docker inspect includes environment credentials. Persist only this projection.
export function containerDiagnostic(value) {
  const state = value?.State;
  return {
    name: typeof value?.Name === 'string' ? value.Name.replace(/^\//, '') : 'unknown',
    status: ['running', 'exited', 'created', 'restarting', 'paused', 'dead', 'removing']
      .includes(state?.Status) ? state.Status : 'unknown',
    oomKilled: typeof state?.OOMKilled === 'boolean' ? state.OOMKilled : null,
    exitCode: Number.isInteger(state?.ExitCode) ? state.ExitCode : null,
    restartCount: Number.isInteger(value?.RestartCount) ? value.RestartCount : null,
    startedAt: timestamp(state?.StartedAt), finishedAt: timestamp(state?.FinishedAt),
    health: ['healthy', 'unhealthy', 'starting'].includes(state?.Health?.Status)
      ? state.Health.Status : 'unknown',
  };
}

function timestamp(value) {
  return typeof value === 'string' && /^\d{4}-\d\d-\d\dT[\d:.]+(?:Z|[+-]\d\d:\d\d)$/.test(value)
    ? value : null;
}

// Classifications are evidence, not causal conclusions. Do not retain log payloads.
export function classifyDockerLog(source) {
  const rules = {
    wslConnectionReset: /Wsl\/Service\/0x80072746/i,
    wslBootstrapFailure: /wsl-bootstrap.*failed: exit|bootstrapping main distribution.*exit status/i,
    engineStopping: /setting engine linux\/wsl state .* -> stopping/i,
    engineRunning: /engine linux\/wsl is running after/i,
  };
  const results = [];
  for (const line of source.split(/\r?\n/)) {
    const at = line.match(/^\[([^\]]+)\]/)?.[1];
    if (!timestamp(at)) continue;
    for (const [code, pattern] of Object.entries(rules)) {
      if (pattern.test(line)) results.push({at, code});
    }
  }
  return results;
}

export function classifyKernelLog(source) {
  return {
    oomEvents: (source.match(/invoked oom-killer|Out of memory: Killed process|oom-kill:/gi) ?? []).length,
    panics: (source.match(/Kernel panic - not syncing/gi) ?? []).length,
    initTimeouts: (source.match(/WaitForBootProcess.*failed to start/gi) ?? []).length,
    dxgWarnings: (source.match(/dxgkio_query_adapter_info.*Ioctl failed/gi) ?? []).length,
    interopFatalSignals: (source.match(/potentially unexpected fatal signal 5/gi) ?? []).length,
  };
}

function capture(file, args, timeoutMs = 10000) {
  return new Promise((resolve) => {
    const child = execFile(file, args, {cwd: root, windowsHide: true, maxBuffer: 4 * 1024 * 1024},
      (error, stdout) => {
        clearTimeout(timer);
        resolve(error ? null : stdout);
      });
    const timer = setTimeout(() => {
      // Only abandon/terminate this read-only client, never a process tree or VM.
      child.stdout?.destroy();
      child.stderr?.destroy();
      child.kill();
      child.unref();
      resolve(null);
    }, timeoutMs);
    child.once('error', () => {
      clearTimeout(timer);
      resolve(null);
    });
  });
}

const wslProbe = `import json,pathlib,subprocess
m={}
for line in pathlib.Path('/proc/meminfo').read_text().splitlines():
 k,v=line.split(':',1)
 if k in ('MemTotal','MemAvailable','SwapTotal','SwapFree'): m[k]=int(v.strip().split()[0])
gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.total,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
print(json.dumps({'bootId':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'uptimeSeconds':float(pathlib.Path('/proc/uptime').read_text().split()[0]),'memoryKiB':m,'gpuMetrics':gpu.stdout.strip() if gpu.returncode==0 else None}))`;

export async function collectDiagnostics() {
  const result = {
    at: new Date().toISOString(), containers: [], dockerEvents: [], wsl: null,
    kernel: null, windows: null, unavailable: []
  };
  const jobs = await Promise.allSettled([
    capture('docker.exe', ['inspect', '--format',
      '[{"Name":{{json .Name}},"State":{{json .State}},"RestartCount":{{json .RestartCount}}}]', 'kyrion-postgres']),
    capture('wsl.exe', ['-d', 'Kyrion-Voice-Training', '--', '/usr/bin/python3', '-c', wslProbe]),
    capture('wsl.exe', ['-d', 'Kyrion-Voice-Training', '--', 'dmesg']),
    capture('powershell.exe', ['-NoProfile', '-Command',
      "$o=Get-CimInstance Win32_OperatingSystem; [pscustomobject]@{totalMemoryKiB=$o.TotalVisibleMemorySize;freeMemoryKiB=$o.FreePhysicalMemory;lastBoot=$o.LastBootUpTime.ToUniversalTime().ToString('o')} | ConvertTo-Json -Compress"]),
  ]);
  const values = jobs.map((job) => job.status === 'fulfilled' ? job.value : null);
  for (const [index, key] of ['docker', 'wsl', 'kernel', 'windows'].entries()) {
    if (!values[index]) {
      result.unavailable.push(key);
      continue;
    }
    try {
      if (key === 'docker') result.containers = JSON.parse(values[index]).map(containerDiagnostic);
      else if (key === 'kernel') result.kernel = classifyKernelLog(values[index]);
      else result[key] = JSON.parse(values[index]);
    } catch {
      result.unavailable.push(key);
    }
  }
  const logs = path.join(process.env.LOCALAPPDATA ?? '', 'Docker/log/host');
  try {
    const files = (await readdir(logs)).filter((name) => name.startsWith('com.docker.backend.exe.log'));
    for (const name of files) result.dockerEvents.push(...classifyDockerLog(await readFile(path.join(logs, name), 'utf8')));
    result.dockerEvents = result.dockerEvents.sort((a, b) => a.at.localeCompare(b.at)).slice(-100);
  } catch {
    result.unavailable.push('dockerLogs');
  }
  return result;
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  const result = await collectDiagnostics();
  const destination = path.join(root, '.run/dev-recovery/diagnostics');
  await mkdir(destination, {recursive: true});
  const file = path.join(destination, `${result.at.replaceAll(':', '-')}.json`);
  await writeFile(file, JSON.stringify(result, null, 2) + '\n', {mode: 0o600});
  console.log(JSON.stringify(result, null, 2));
  console.log(`Diagnostic snapshot: ${file}`);
  if (result.unavailable.length) process.exitCode = 1;
}
