// Repeated starts join an active job or tolerate the helper's short cooldown.
export async function requestRecovery(call, request, {
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
} = {}) {
  for (let attempt = 0; attempt < 5; attempt++) {
    const job = await call();
    if (job.state === 'running') {
      if (request.action === 'start' && !request.service) return job;
      throw new Error('RECOVERY_BUSY');
    }
    try {
      return await call('POST', request);
    } catch (error) {
      if (error.status !== 409 || attempt === 4) throw error;
      await sleep(1250);
    }
  }
}
