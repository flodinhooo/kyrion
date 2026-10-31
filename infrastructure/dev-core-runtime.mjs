import path from 'node:path';

// Operator configuration only; never selected by a browser request.
export function coreLaunch({root, artifact, manifest, javaHome, systemRoot}) {
  if (manifest && !path.isAbsolute(manifest)) throw new Error('INVALID_CORE_LAN_MANIFEST_PATH');
  return {
    file: manifest ? path.join(systemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe')
      : javaHome ? path.join(javaHome, 'bin/java.exe') : 'java.exe',
    args: manifest ? ['-NoProfile', '-NonInteractive', '-File', path.join(root, 'infrastructure/dev/Start-CoreLan.ps1'),
      '-Manifest', manifest, '-Wait'] : ['-jar', artifact],
    cwd: path.join(root, 'services/core'),
  };
}
