const $ = (id) => document.getElementById(id);
let csrf = '', current = null, pending = false;
let documents = [];
const status = (message) => { $('status').textContent = message; };
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), 'X-CSRF-Token': csrf } });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
function busy() {
  const activeDoc = documents.find(d => d.id === $('document').value);
  $('send').disabled = pending || !current || (activeDoc && activeDoc.status !== 'ready');
  $('rename').disabled = pending || !current;
  $('delete').disabled = pending || !current;
  $('newChat').disabled = pending;
  $('renameSave').disabled = pending;
  $('deleteConfirm').disabled = pending;
  $('compare').disabled = pending || !activeDoc || activeDoc.status !== 'ready' || !$('message').value.trim();
  $('document').disabled = pending;
  $('method').disabled = pending;
}
function renderMessages(messages, metadata = {}) {
  let turn = 0;
  $('messages').replaceChildren();
  if (!messages.length) { const p = document.createElement('p'); p.textContent = 'This conversation is ready. Send your first message.'; $('messages').append(p); }
  for (const message of messages) {
    const bubble = document.createElement('article'); bubble.className = `bubble ${message.role}`;
    const label = document.createElement('strong'); label.textContent = message.role === 'user' ? 'You' : 'Assistant';
    const content = document.createElement('div'); content.textContent = message.content;
    bubble.append(label, content);
    if (message.role === 'assistant') { turn++; if (metadata[String(turn)]) renderEvidence(bubble, metadata[String(turn)]); }
    $('messages').append(bubble);
  }
}
async function load(cid) {
  const data = await api(`/api/conversations/${cid}`);
  if (current !== cid) return;
  $('title').textContent = data.title; renderMessages(data.messages, data.grounded_turns); busy();
}
async function refreshList() {
  const data = await api('/api/conversations'); $('conversations').replaceChildren();
  for (const chat of data.conversations) {
    const button = document.createElement('button'); button.textContent = chat.title;
    button.setAttribute('aria-current', String(chat.id === current));
    button.addEventListener('click', async () => { current = chat.id; busy(); status(''); try { await load(current); await refreshList(); } catch (error) { status(error.message); } });
    $('conversations').append(button);
  }
  return data.conversations;
}
$('newChat').addEventListener('click', async () => {
  try { const chat = await api('/api/conversations', { method: 'POST', body: JSON.stringify({ title: 'New conversation' }) }); current = chat.id; await load(current); await refreshList(); status(''); $('message').focus(); } catch (error) { status(error.message); }
});
$('rename').addEventListener('click', () => {
  $('conversationTitle').value = $('title').textContent;
  $('renameError').textContent = ''; $('renameDialog').showModal();
});
$('renameCancel').addEventListener('click', () => $('renameDialog').close());
$('renameForm').addEventListener('submit', async (event) => {
  event.preventDefault(); if (pending || !current) return;
  const title = $('conversationTitle').value.trim();
  if (!title) { $('renameError').textContent = 'Enter a conversation title.'; return; }
  const cid = current; pending = true; busy();
  try {
    await api(`/api/conversations/${cid}`, { method: 'PATCH', body: JSON.stringify({ title }) });
    await load(cid); await refreshList(); $('renameDialog').close(); status('Title saved.');
  } catch (error) { $('renameError').textContent = error.message; }
  finally { pending = false; busy(); }
});
$('delete').addEventListener('click', () => { $('deleteError').textContent = ''; $('deleteDialog').showModal(); });
$('deleteCancel').addEventListener('click', () => $('deleteDialog').close());
$('deleteConfirm').addEventListener('click', async () => {
  if (pending || !current) return; pending = true; busy();
  try {
    await api(`/api/conversations/${current}`, { method: 'DELETE' }); current = null;
    const list = await refreshList();
    if (list.length) { current = list[0].id; await load(current); await refreshList(); }
    else { $('title').textContent = 'Start a conversation'; $('messages').replaceChildren(); }
    $('deleteDialog').close(); status('Conversation deleted.');
  } catch (error) { $('deleteError').textContent = error.message; }
  finally { pending = false; busy(); }
});
$('composer').addEventListener('submit', async (event) => {
  event.preventDefault(); const message = $('message').value.trim(); if (pending || !current || !message) return;
  const cid = current; pending = true; busy(); status('Assistant is replying…');
  try { await api('/chat', { method: 'POST', body: JSON.stringify({ conversation_id: cid, message, document_id: $('document').value || undefined, method: $('method').value }) }); $('message').value = ''; if (current === cid) await load(cid); status('Reply saved.'); } catch (error) { status(error.message + ' Your message has been kept so you can retry.'); }
  finally { pending = false; busy(); $('message').focus(); }
});
$('message').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('composer').requestSubmit(); } });
(async () => {
  try { const session = await api('/api/session'); csrf = session.csrf; await refreshDocuments(); await refreshExperiments(); $('mode').textContent = session.provider === 'demo' ? 'Ordinary chat: offline demo · study: local Ollama' : 'OpenAI · replies use your configured key'; const list = await refreshList(); if (list.length) { current = list[0].id; await load(current); await refreshList(); } else $('newChat').click(); } catch (error) { status(error.message + ' Reload to reconnect.'); }
})();

function documentState() {
  const doc = documents.find(d => d.id === $('document').value);
  let metadata = doc?.metadata || {};
  if (typeof metadata === 'string') { try { metadata = JSON.parse(metadata); } catch { metadata = {}; } }
  $('documentStatus').textContent = doc ? `${doc.title} · ${doc.status}${metadata.embedded ? ` · ${metadata.embedded}/${metadata.chunks} passages` : ''}${doc.error ? ` · ${doc.error}` : ''}` : 'Ordinary conversation · no document evidence';
  $('retryDocument').disabled = !doc || doc.status === 'ready' || pending;
  $('deleteDocument').disabled = !doc || ['queued', 'indexing'].includes(doc.status) || pending;
  $('send').disabled = pending || !current || (doc && doc.status !== 'ready');
  busy();
  if (doc && doc.status !== 'ready') $('compare').disabled = true;
}
async function refreshDocuments(selectId) {
  const data = await api('/api/documents'); documents = data.documents;
  const selected = selectId || $('document').value;
  $('document').replaceChildren(new Option('Ordinary conversation', ''));
  for (const doc of documents) $('document').append(new Option(`${doc.title} · ${doc.status}`, doc.id));
  $('document').value = selected; documentState();
}
$('document').addEventListener('change', documentState);
$('message').addEventListener('input', busy);
$('importForm').addEventListener('submit', async (event) => {
  event.preventDefault(); if (pending) return;
  const file = $('pdfFile').files[0]; if (!file) return;
  if (file.size > 64 * 1024 * 1024) { status('PDF must be smaller than 64 MiB.'); return; }
  const body = new FormData(); body.append('file', file);
  try { const doc = await api('/api/documents', {method: 'POST', body}); await refreshDocuments(doc.id); $('importForm').reset(); status('Import queued. You can keep using ordinary chat while it indexes.'); }
  catch (error) { status(error.message); }
});
$('demoDocument').addEventListener('click', async () => {
  try { const doc = await api('/api/documents/demo', {method: 'POST', body: '{}'}); await refreshDocuments(doc.id); }
  catch (error) { status(error.message); }
});
$('retryDocument').addEventListener('click', async () => {
  try { await api(`/api/documents/${$('document').value}/retry`, {method: 'POST', body: '{}'}); await refreshDocuments(); }
  catch (error) { status(error.message); }
});
$('deleteDocument').addEventListener('click', () => $('removeDocumentDialog').showModal());
$('cancelRemoveDocument').addEventListener('click', () => $('removeDocumentDialog').close());
$('confirmRemoveDocument').addEventListener('click', async () => {
  try { await api(`/api/documents/${$('document').value}`, {method: 'DELETE'}); $('removeDocumentDialog').close(); await refreshDocuments(); await refreshExperiments(); }
  catch (error) { status(error.message); }
});
function renderEvidence(parent, result) {
  const stats = document.createElement('small');
  stats.textContent = `${result.method} · ${result.seconds.toFixed(2)}s · ${result.input_tokens + result.output_tokens} tokens · ${result.model_calls} model calls`;
  parent.append(stats);
  const sources = document.createElement('div'); sources.className = 'sources';
  if (result.source_removed) { const note = document.createElement('p'); note.textContent = 'Source removed; passage text is no longer available.'; parent.append(note); }
  for (const citation of result.source_removed ? [] : result.citations) {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = `${citation.id} · PDF page ${citation.page}`;
    button.addEventListener('click', async () => {
      try { const source = await api(`/api/documents/${result.document_id}/sources/${citation.id}`); $('sourceLocation').textContent = `PDF page ${source.page}${source.printed_page ? ` · printed page ${source.printed_page}` : ''} · ${source.section}`; $('sourceText').textContent = source.text; $('sourceDialog').showModal(); }
      catch (error) { status(error.message); }
    }); sources.append(button);
  }
  parent.append(sources);
  const details = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = 'Evidence acquisition steps'; details.append(summary);
  for (const step of result.steps) { const p = document.createElement('p'); p.textContent = step; details.append(p); }
  parent.append(details);
}
$('closeSource').addEventListener('click', () => $('sourceDialog').close());
$('closeComparison').addEventListener('click', () => $('comparisonDialog').close());
$('compare').addEventListener('click', async () => {
  if (pending || !$('document').value || !$('message').value.trim()) return;
  const question = $('message').value.trim(); const documentId = $('document').value;
  pending = true; busy(); status('Comparing three methods locally… This can take several minutes.');
  try {
    const result = await api('/api/comparisons', {method: 'POST', body: JSON.stringify({document_id: documentId, question})});
    showComparison(result); await refreshExperiments(); status('Comparison saved separately; your chat has not changed.');
  } catch (error) { status(error.message + ' Your question is kept for retry.'); }
  finally { pending = false; busy(); documentState(); }
});
setInterval(async () => {
  if (!csrf || pending || !documents.some(d => ['queued', 'indexing'].includes(d.status))) return;
  try { await refreshDocuments(); } catch (error) { status(error.message); }
}, 2000);

function showComparison(result) {
  $('comparisonQuestion').textContent = result.question; $('comparisonResults').replaceChildren();
  for (const [method, answer] of Object.entries(result.results)) {
    const card = document.createElement('section'); card.className = 'comparisonCard'; const title = document.createElement('h3'); title.textContent = method;
    const text = document.createElement('p'); text.textContent = answer.status === 'complete' ? answer.reply : answer.error;
    card.append(title, text); if (answer.status === 'complete') renderEvidence(card, answer); $('comparisonResults').append(card);
  }
  $('comparisonDialog').showModal();
}
async function refreshExperiments() {
  const data = await api('/api/comparisons'); $('savedComparison').replaceChildren(new Option('Choose a comparison', ''));
  for (const experiment of data.comparisons) $('savedComparison').append(new Option(experiment.question, experiment.id));
}
$('savedComparison').addEventListener('change', async () => {
  if (!$('savedComparison').value || pending) return;
  try { showComparison(await api(`/api/comparisons/${$('savedComparison').value}`)); } catch (error) { status(error.message); }
});
