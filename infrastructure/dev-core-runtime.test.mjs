import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {coreLaunch} from './dev-core-runtime.mjs';

const root = path.resolve('synthetic-runtime');
const settings = {root, artifact: path.join(root, 'frozen.jar'), systemRoot: path.resolve('Windows')};

test('loopback recovery retains its immutable JAR and selected Java executable', () => {
  const launch = coreLaunch({...settings, javaHome: path.join(root, 'jdk')});
  assert.equal(launch.file, path.join(root, 'jdk/bin/java.exe'));
  assert.deepEqual(launch.args, ['-jar', settings.artifact]);
});

test('opted-in LAN recovery always enters the guarded pinned launcher and stays managed', () => {
  const manifest = path.join(root, "pin with spaces and $(literal).json");
  const launch = coreLaunch({...settings, manifest});
  assert.equal(launch.file, path.join(settings.systemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe'));
  assert.deepEqual(launch.args, ['-NoProfile', '-NonInteractive', '-File',
    path.join(root, 'infrastructure/dev/Start-CoreLan.ps1'), '-Manifest', manifest, '-Wait']);
  assert.ok(!launch.args.includes(settings.artifact));
});

test('a relative LAN manifest never silently falls back to an unguarded JVM', () => {
  assert.throws(() => coreLaunch({...settings, manifest: 'relative.json'}), /INVALID_CORE_LAN_MANIFEST_PATH/);
});
