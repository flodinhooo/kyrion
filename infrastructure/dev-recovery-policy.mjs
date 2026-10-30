import {timingSafeEqual} from 'node:crypto';

export function authorisedKey(value, expected) {
  return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value) && value.length === expected.length
    && timingSafeEqual(Buffer.from(value), Buffer.from(expected));
}

export function validAction(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)
    || !['start', 'restart'].includes(value.action)) return false;
  const fields = Object.keys(value);
  return fields.length === 1 || (fields.length === 2 && fields.includes('service')
    && value.action === 'restart' && ['core', 'ai', 'ollama'].includes(value.service));
}

export function selectedServices(services, target) {
  return target === undefined ? services : services.filter((service) => service.id === target);
}

export function canRestartManagedProcess(action, executable, child) {
  return action === 'restart' && executable !== 'wsl.exe'
    && !!child && child.exitCode === null && !child.killed;
}
