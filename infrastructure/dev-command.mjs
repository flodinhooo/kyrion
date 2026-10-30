import {spawn} from 'node:child_process';

// A wedged Docker/WSL client must not wedge the development status command.
export function commandSucceeded(file, args, {
  cwd, timeoutMs = 5000, spawnProcess = spawn,
  setTimer = setTimeout, clearTimer = clearTimeout,
} = {}) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawnProcess(file, args, {cwd, windowsHide: true, stdio: 'ignore'});
    } catch {
      resolve(false);
      return;
    }
    const timer = setTimer(() => {
      // Terminate only this CLI client, never a container or a process tree.
      child.kill();
      child.unref();
      resolve(false);
    }, timeoutMs);
    child.once('error', () => {
      clearTimer(timer);
      resolve(false);
    });
    child.once('exit', (code) => {
      clearTimer(timer);
      resolve(code === 0);
    });
  });
}
