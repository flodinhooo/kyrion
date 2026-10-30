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
      foreach($file in @('infrastructure/dev/Prepare-CoreLan.ps1','infrastructure/dev/Set-CoreLan.ps1',
        'infrastructure/dev/Install-CoreLanGuards.ps1','infrastructure/dev/Invoke-CoreLanGuardsAdmin.ps1',
        'infrastructure/dev/Activate-CoreLan.ps1')) {
        $errors=$null;
        [void][System.Management.Automation.Language.Parser]::ParseFile(
          (Join-Path $PWD $file),[ref]$null,[ref]$errors);
        if($errors){throw 'SCRIPT_PARSE_FAILED'}
      }; 'PARSED'`);
    assert.match(result, /PARSED/);
  });

test('non-Pi guard covers all IPv4 except loopback and exactly the two Pi addresses', () => {
  const addresses = JSON.parse(readFileSync(new URL('./dev/core-lan-guard-addresses.json', import.meta.url)));
  const ipv4 = (value) => value.split('.').reduce((sum, octet) => sum * 256 + Number(octet), 0);
  const ranges = addresses.filter((value) => !value.includes(':')).map((value) => {
    const [address, prefix] = value.split('/');
    const start = ipv4(address);
    const size = 2 ** (32 - Number(prefix));
    assert.equal(start % size, 0);
    return [start, start + size - 1];
  }).sort((left, right) => left[0] - right[0]);
  const gaps = [];
  let end = -1;
  for (const [start, last] of ranges) {
    assert.ok(start > end, 'no overlapping networks');
    if (start > end + 1) gaps.push([end + 1, start - 1]);
    end = last;
  }
  assert.equal(end, 2 ** 32 - 1);
  assert.deepEqual(gaps, [[ipv4('127.0.0.0'), ipv4('127.255.255.255')],
    [ipv4('192.168.1.115'), ipv4('192.168.1.116')]]);
  assert.deepEqual(addresses.filter((value) => value.includes(':')), ['::/1', '8000::/1']);
});

test('Windows dotted subnet masks and /32 hosts compare to the exact approved scope',
  {skip: process.platform !== 'win32'}, () => {
    const result = powershell(`. ./infrastructure/dev/Install-CoreLanGuards.ps1 | Out-Null;
      if ((ConvertTo-CoreFirewallAddress '192.168.1.64/27') -ne '192.168.1.64/255.255.255.224') {throw 'MASK'};
      if ((ConvertTo-CoreFirewallAddress '192.168.1.114/32') -ne '192.168.1.114') {throw 'HOST'};
      if ((ConvertTo-CoreFirewallAddress '::/1') -ne '::/1') {throw 'V6'};
      'NORMALIZED'`);
    assert.match(result, /NORMALIZED/);
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
