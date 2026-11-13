/** One explicit write attempt. A timeout never proves that a device did not act. */
export async function runDeviceCommand(
  send: (signal: AbortSignal) => Promise<Response>,
  accept: (value: unknown) => boolean,
  pending: (value: boolean) => void,
  failed: (value: boolean) => void,
) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15_000);
  pending(true);
  failed(false);
  try {
    const response = await send(controller.signal);
    const value: unknown = await response.json();
    if (!response.ok || !accept(value)) failed(true);
  } catch {
    failed(true);
  } finally {
    clearTimeout(timeout);
    pending(false);
  }
}
