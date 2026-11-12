import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, unlink, rmdir} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const checker = fileURLToPath(new URL('./dev-recovery-acl.ps1', import.meta.url));
const check = (target, directory = false) => spawnSync('powershell.exe',
  ['-NoProfile', '-NonInteractive', '-File', checker, '-LiteralPath', target,
    ...(directory ? ['-Directory'] : [])], {windowsHide: true, timeout: 10000}).status;

test('native recovery ACL check accepts protected operator paths and rejects inherited or extra grants',
  {skip: process.platform !== 'win32'}, async () => {
    const directory = await mkdtemp(path.join(tmpdir(), 'kyrion-recovery-acl-'));
    const file = path.join(directory, 'operator-fixture.key');
    const operator = `${process.env.USERDOMAIN}\\${process.env.USERNAME}`;
    const acl = (target, ...args) => {
      const result = spawnSync('icacls.exe', [target, ...args], {windowsHide: true, timeout: 10000});
      assert.equal(result.status, 0, 'native ACL operation succeeds');
    };
    try {
      await writeFile(file, 'not-an-operator-key');
      assert.notEqual(check(directory, true), 0, 'inherited permissions are not accepted');
      acl(directory, '/inheritance:r', '/grant:r', `${operator}:(OI)(CI)F`);
      acl(file, '/inheritance:r', '/grant:r', `${operator}:F`);
      assert.equal(check(directory, true), 0);
      assert.equal(check(file), 0);
      assert.equal(check(directory, true), 0, 'already protected directory can be rechecked');
      assert.notEqual(check(file, true), 0, 'file cannot stand in for a directory');
      acl(file, '/grant', '*S-1-1-0:R');
      assert.notEqual(check(file), 0, 'an additional Everyone read grant is rejected');
    } finally {
      await unlink(file);
      await rmdir(directory);
    }
  });
