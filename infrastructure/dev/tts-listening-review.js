/* Static local review only: no API calls, storage service or automatic submission. */
'use strict';
document.addEventListener('play', (event) => {
  if (!(event.target instanceof HTMLAudioElement)) return;
  for (const player of document.querySelectorAll('audio')) {
    if (player !== event.target) player.pause();
  }
}, true);
document.getElementById('export').addEventListener('click', () => {
  const ratings = {};
  for (const field of document.querySelectorAll('select, textarea')) {
    ratings[field.id] = field.value;
  }
  const blob = new Blob([JSON.stringify({
    comparison: 'a842b9e-existing-samples-first-warm-run',
    createdAt: new Date().toISOString(),
    ratings,
  }, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'kyrion-tts-listening-ratings.json';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
