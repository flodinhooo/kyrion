import {spawn} from 'node:child_process';
import {readFile, mkdir} from 'node:fs/promises';
import {openSync, closeSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

// Start the independent helper alongside Windows Web development, without
// giving the Web server itself host execution privileges.
if (process.platform !== 'win32') process.exit(0);
const root = fileURLToPath(new URL('../', import.meta.url));
const stateDir = path.join(root, '.run/dev-recovery');

async function ready() {
  try {
    const key = (await readFile(path.join(stateDir, 'operator.key'), 'utf8')).trim();
    const response = await fetch('http://127.0.0.1:17654/', {
      headers: {Authorization: `Bearer ${key}`},
      signal: AbortSignal.timeout(800)
    });
    return response.ok;
  } catch {
    return false;
  }
}

if (await ready()) process.exit(0);
await mkdir(stateDir, {recursive: true});
const log = openSync(path.join(stateDir, 'helper.log'), 'a');
let child;
try {
  child = spawn(process.execPath, [path.join(root, 'infrastructure/dev-recovery.mjs')], {
    cwd: root, detached: true, windowsHide: true, stdio: ['ignore', log, log],
  });
} finally {
  closeSync(log);
}
let failed = false;
child.once('error', () => {
  failed = true;
});
child.unref();
for (let attempt = 0; attempt < 10 && !failed; attempt++) {
  await new Promise((resolve) => setTimeout(resolve, 500));
  if (await ready()) process.exit(0);
}
throw new Error('Recovery helper unavailable. Check .run/dev-recovery/helper.log and local port 17654.');
