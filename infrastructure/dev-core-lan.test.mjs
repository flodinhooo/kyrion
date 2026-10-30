import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync, spawnSync} from 'node:child_process';
import {readFileSync, existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';

const root = fileURLToPath(new URL('../', import.meta.url));
const powershell = (command) => execFileSync('powershell.exe',
  ['-NoProfile', '-NonInteractive', '-Command', command], {cwd: root, encoding: 'utf8', timeout: 15000});

test('LAN preparation and activation guard parse without executing a network change',
  {skip: process.platform !== 'win32'}, () => {
    const result = powershell(`$ErrorActionPreference='Stop';
      foreach($file in @('infrastructure/dev/Prepare-CoreLan.ps1','infrastructure/dev/Set-CoreLan.ps1')) {
        $errors=$null;
        [void][System.Management.Automation.Language.Parser]::ParseFile(
          (Join-Path $PWD $file),[ref]$null,[ref]$errors);
        if($errors){throw 'SCRIPT_PARSE_FAILED'}
      }; 'PARSED'`);
    assert.match(result, /PARSED/);
  });

test('unreviewed LAN activation fails closed before configuration or process access',
  {skip: process.platform !== 'win32'}, () => {
    const config = new URL('../infrastructure/.env', import.meta.url);
    const hash = () => existsSync(config)
      ? createHash('sha256').update(readFileSync(config)).digest('hex') : null;
    const before = hash();
    // PID zero can never identify Core, even if a future edit removes the guard.
    const result = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command',
        "& infrastructure/dev/Set-CoreLan.ps1 -CoreProcessId 0 -Apply"],
      {cwd: root, encoding: 'utf8', timeout: 15000});
    assert.equal(result.error, undefined);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /CORE_LAN_APPLY_BLOCKED_USE_SPRINT04_REVIEW/);
    assert.equal(hash(), before);
  });
