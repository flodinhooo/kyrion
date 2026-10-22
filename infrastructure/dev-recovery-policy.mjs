import {timingSafeEqual} from 'node:crypto';

export function authorisedKey(value, expected) {
  return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) && value.length === expected.length
    && timingSafeEqual(Buffer.from(value), Buffer.from(expected));
}

export function validAction(value) {
  return value !== null && typeof value === 'object'
    && Object.keys(value).length === 1 && ['start', 'restart'].includes(value.action);
}

export function canRestartManagedProcess(action, executable, child) {
  return action === 'restart' && executable !== 'wsl.exe'
    && !!child && child.exitCode === null && !child.killed;
}
