/* Server renders only the selected transport. Never combine trace categories. */
const filter = document.querySelector('#trace-filter');
filter?.querySelector('select').addEventListener('change', () => filter.requestSubmit());
const events = document.querySelector('#events');
let refreshing = false;
async function refreshTrace() {
  if (refreshing || document.hidden || events?.dataset.live !== 'true') return;
  refreshing = true;
  try {
    const response = await fetch(location.href, {cache: 'no-store'});
    if (!response.ok || response.redirected) return;
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    if (doc.querySelector('#channel')?.value !== filter.querySelector('select').value) return;
    const next = doc.querySelector('#events');
    if (!next || next.innerHTML === events.innerHTML) return;
    const opened = new Set();
    events.querySelectorAll('[data-event]').forEach(row => row.querySelectorAll('details').forEach((d,i) => {
      if (d.open) opened.add(row.dataset.event + ':' + i);
    }));
    events.replaceChildren(...next.childNodes);
    events.querySelectorAll('[data-event]').forEach(row => row.querySelectorAll('details').forEach((d,i) => {
      d.open = opened.has(row.dataset.event + ':' + i);
    }));
  } catch (_) { /* Keep the last verified view during a temporary disconnect. */ }
  finally { refreshing = false; }
}
setInterval(refreshTrace, 5000);
