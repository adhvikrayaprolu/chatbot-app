const $ = (id) => document.getElementById(id);
let csrf = '', current = null, pending = false;
const status = (message) => { $('status').textContent = message; };
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf } });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
function busy() {
  $('send').disabled = pending || !current;
  $('rename').disabled = pending || !current;
  $('delete').disabled = pending || !current;
  $('newChat').disabled = pending;
  $('renameSave').disabled = pending;
  $('deleteConfirm').disabled = pending;
}
function renderMessages(messages) {
  $('messages').replaceChildren();
  if (!messages.length) { const p = document.createElement('p'); p.textContent = 'This conversation is ready. Send your first message.'; $('messages').append(p); }
  for (const message of messages) {
    const bubble = document.createElement('article'); bubble.className = `bubble ${message.role}`;
    const label = document.createElement('strong'); label.textContent = message.role === 'user' ? 'You' : 'Assistant';
    const content = document.createElement('div'); content.textContent = message.content;
    bubble.append(label, content); $('messages').append(bubble);
  }
}
async function load(cid) {
  const data = await api(`/api/conversations/${cid}`);
  if (current !== cid) return;
  $('title').textContent = data.title; renderMessages(data.messages); busy();
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
  try { await api('/chat', { method: 'POST', body: JSON.stringify({ conversation_id: cid, message }) }); $('message').value = ''; if (current === cid) await load(cid); status('Reply saved.'); } catch (error) { status(error.message + ' Your message has been kept so you can retry.'); }
  finally { pending = false; busy(); $('message').focus(); }
});
$('message').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); $('composer').requestSubmit(); } });
(async () => {
  try { const session = await api('/api/session'); csrf = session.csrf; $('mode').textContent = session.provider === 'demo' ? 'Offline demo · no AI API calls' : 'OpenAI · replies use your configured key'; const list = await refreshList(); if (list.length) { current = list[0].id; await load(current); await refreshList(); } else $('newChat').click(); } catch (error) { status(error.message + ' Reload to reconnect.'); }
})();
