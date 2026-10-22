import { useCallback, useEffect, useRef, useState } from 'react';
import * as api from './api';
import { Composer } from './components/Composer';
import { CompareView } from './components/CompareView';
import { Dialog } from './components/Dialog';
import { MessageView } from './components/MessageView';
import { Sidebar } from './components/Sidebar';
import { recall, remember } from './storage';
import { METHOD_INFO, type ComparisonResult, type ConversationSummary, type DocumentInfo, type Message, type Method, type Passage } from './types';

type Source = Passage & { text: string; documentId: string };
type Confirm = { title: string; body: string; action: string; run(): Promise<void> };

export default function App() {
  const [session, setSession] = useState<api.Session | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [documentId, setDocumentId] = useState(recall('document') ?? '');
  const [method, setMethod] = useState<Method>((recall('method') as Method) || 'rag');
  const [streaming, setStreaming] = useState(false);
  const [notice, setNotice] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  const [comparison, setComparison] = useState<ComparisonResult | 'loading' | null>(null);
  const [saved, setSaved] = useState<{ id: string; question: string }[] | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const current = useRef<string | null>(null);
  const thread = useRef<HTMLDivElement>(null);
  current.current = currentId;

  const fail = (error: unknown) => setNotice(error instanceof Error ? error.message : 'Something went wrong.');
  const activeDoc = documents.find((d) => d.id === documentId);
  const grounded = activeDoc?.status === 'ready';

  const refreshDocuments = useCallback(async () => {
    const docs = await api.listDocuments();
    setDocuments(docs);
    return docs;
  }, []);

  const open = useCallback(async (id: string) => {
    setCurrentId(id);
    setMenuOpen(false);
    setNotice('');
    const data = await api.loadConversation(id);
    if (current.current !== id) return;
    setTitle(data.title);
    setMessages(data.messages);
  }, []);

  useEffect(() => {
    (async () => {
      setSession(await api.startSession());
      const [list] = await Promise.all([api.listConversations(), refreshDocuments()]);
      setConversations(list);
      if (list.length) await open(list[0].id);
    })().catch(fail);
  }, [open, refreshDocuments]);

  // Poll only while something is importing.
  useEffect(() => {
    if (!documents.some((d) => d.status === 'queued' || d.status === 'indexing')) return;
    const timer = setInterval(() => refreshDocuments().catch(fail), 1500);
    return () => clearInterval(timer);
  }, [documents, refreshDocuments]);

  useEffect(() => {
    if (!source) return;
    const close = (e: KeyboardEvent) => { if (e.key === 'Escape') setSource(null); };
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [source]);

  useEffect(() => { remember('document', documentId); }, [documentId]);
  useEffect(() => { remember('method', method); }, [method]);
  useEffect(() => { thread.current?.scrollTo({ top: thread.current.scrollHeight }); }, [messages]);

  async function newChat() {
    try {
      const chat = await api.createConversation();
      setConversations((list) => [chat, ...list]);
      await open(chat.id);
    } catch (error) { fail(error); }
  }

  async function send(text: string): Promise<boolean> {
    let id = currentId;
    try {
      if (!id) {
        const chat = await api.createConversation(text.slice(0, 60));
        setConversations((list) => [chat, ...list]);
        setCurrentId(id = chat.id);
        current.current = id;
        setTitle(chat.title);
        setMessages([]);
      }
    } catch (error) { fail(error); return false; }
    const conversation = id;
    // Updates from this stream only touch the conversation that started it.
    const patch = (fn: (m: Message) => Message) => {
      if (current.current !== conversation) return;
      setMessages((list) => [...list.slice(0, -1), fn(list[list.length - 1])]);
    };
    setNotice('');
    setStreaming(true);
    setMessages((list) => [...list, { role: 'user', content: text }, { role: 'assistant', content: '', pending: true, steps: [] }]);
    try {
      const result = await api.sendMessage(conversation, grounded ? { message: text, document_id: documentId, method } : { message: text }, {
        onStep: (label) => patch((m) => ({ ...m, steps: [...(m.steps ?? []), label] })),
        onEvidence: (passages) => patch((m) => ({ ...m, evidence: passages })),
        onToken: (delta) => patch((m) => ({ ...m, content: m.content + delta })),
      });
      patch((m) => ({ ...m, content: result.reply, grounded: result.grounded, pending: false }));
      return true;
    } catch (error) {
      // The failed turn was not saved; drop the placeholder pair and restore the draft.
      if (current.current === conversation) setMessages((list) => list.slice(0, -2));
      fail(error);
      return false;
    } finally {
      setStreaming(false);
    }
  }

  async function runComparison(question: string) {
    if (!grounded) return;
    setComparison('loading');
    try { setComparison(await api.compare(documentId, question)); } catch (error) { setComparison(null); fail(error); }
  }

  async function openSource(docId: string, passage: Passage) {
    try { setSource({ ...(await api.loadSource(docId, passage.id)), documentId: docId }); } catch (error) { fail(error); }
  }

  async function startImport(promise: Promise<DocumentInfo>) {
    try {
      const doc = await promise;
      setDocumentId(doc.id);
      await refreshDocuments();
    } catch (error) { fail(error); }
  }

  // Simplest to most agentic, limited to what the server offers.
  const methods = (Object.keys(METHOD_INFO) as Method[]).filter((m) => !session || session.methods.includes(m));
  const placeholder = grounded ? 'Ask a question about this source…' : 'Message the assistant…';

  return (
    <div className="app">
      <Sidebar open={menuOpen} conversations={conversations} currentId={currentId} documents={documents} busy={streaming}
        onClose={() => setMenuOpen(false)} onSaved={() => api.listComparisons().then(setSaved).catch(fail)} onSelect={(id) => open(id).catch(fail)} onNew={newChat}
        onImport={(file) => startImport(api.importDocument(file))} onDemo={() => startImport(api.importDemo())}
        onRetry={(id) => api.retryDocument(id).then(refreshDocuments).catch(fail)}
        onRemove={(doc) => setConfirm({
          title: 'Remove source?', action: 'Remove source',
          body: `“${doc.title}” and its index will be deleted. Earlier replies keep their text but lose passage links.`,
          run: async () => { await api.removeDocument(doc.id); if (doc.id === documentId) setDocumentId(''); await refreshDocuments(); },
        })} />
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} aria-hidden />}

      <main className="main">
        <header className="toolbar">
          <button type="button" className="icon menu" aria-label="Open menu" onClick={() => setMenuOpen(true)}>☰</button>
          <h1 title={title}>{currentId ? title : 'New conversation'}</h1>
          <div className="toolbar-actions">
            {currentId && (<>
              <button type="button" className="link" onClick={() => setRenaming(true)} disabled={streaming}>Rename</button>
              <button type="button" className="link" disabled={streaming} onClick={() => setConfirm({
                title: 'Delete conversation?', action: 'Delete conversation', body: 'This permanently removes the conversation and its messages.',
                run: async () => {
                  await api.deleteConversation(currentId);
                  const list = conversations.filter((c) => c.id !== currentId);
                  setConversations(list); setCurrentId(null); setMessages([]); setTitle('');
                  if (list[0]) await open(list[0].id);
                },
              })}>Delete</button>
            </>)}
          </div>
        </header>

        <div className="controls" role="group" aria-label="Answer settings">
          <label className="select">
            <span>Source</span>
            <select value={documentId} onChange={(e) => setDocumentId(e.target.value)} disabled={streaming}>
              <option value="">None — general chat ({session?.provider ?? '…'})</option>
              {documents.map((d) => <option key={d.id} value={d.id} disabled={d.status !== 'ready'}>{d.title}{d.status !== 'ready' ? ` (${d.status})` : ''}</option>)}
            </select>
          </label>
          {grounded && (
            <div className="segmented" role="radiogroup" aria-label="Search method">
              {methods.map((m) => (
                <button key={m} type="button" role="radio" aria-checked={method === m} title={METHOD_INFO[m]?.hint}
                  onClick={() => setMethod(m)} disabled={streaming}>{METHOD_INFO[m]?.label ?? m}</button>
              ))}
            </div>
          )}
        </div>
        {grounded && <p className="method-hint small muted">{METHOD_INFO[method]?.hint}</p>}

        <div className="thread" ref={thread} aria-live="polite">
          {messages.length === 0 ? (
            <div className="empty">
              <h2>{grounded ? `Ask “${activeDoc!.title}” anything` : 'Ask a question about your documents'}</h2>
              <p className="muted">
                {grounded
                  ? 'Answers cite the passages they came from. Click a number to read the source.'
                  : 'Import a PDF from the library (or try the GPU demo notes), select it as the source, and every answer will be grounded in cited passages.'}
              </p>
            </div>
          ) : messages.map((m, i) => <MessageView key={i} message={m} onOpenSource={openSource} />)}
        </div>

        {notice && <p className="notice" role="status">{notice}<button type="button" className="icon" aria-label="Dismiss" onClick={() => setNotice('')}>×</button></p>}
        <Composer disabled={streaming} placeholder={placeholder} onSend={send} onCompare={grounded ? runComparison : undefined} />
      </main>

      <aside className={`drawer${source ? ' open' : ''}`} aria-label="Source passage" aria-hidden={!source}>
        {source && (
          <>
            <header className="dialog-header">
              <h2>Source</h2>
              <button type="button" className="icon" aria-label="Close source" onClick={() => setSource(null)}>×</button>
            </header>
            <p className="small muted">
              PDF page {source.page}{source.printed_page ? ` · printed page ${source.printed_page}` : ''} · {source.id}
            </p>
            {source.section && <h3>{source.section}</h3>}
            <pre className="passage">{source.text}</pre>
          </>
        )}
      </aside>

      <Dialog open={comparison !== null} wide title="Method comparison" onClose={() => setComparison(null)}>
        {comparison === 'loading'
          ? <p className="muted"><span className="spinner" aria-hidden /> Running all {methods.length} methods on the local model. This takes a minute or two…</p>
          : comparison && <CompareView result={comparison} onOpenSource={openSource} />}
      </Dialog>

      <Dialog open={saved !== null} title="Saved comparisons" onClose={() => setSaved(null)}>
        {saved?.length === 0 && <p className="muted">No comparisons yet. Choose a source, type a question and press “Compare methods”.</p>}
        <ul className="plain">
          {saved?.map((c) => (
            <li key={c.id}><button type="button" className="link" onClick={async () => {
              setSaved(null);
              try { setComparison(await api.loadComparison(c.id)); } catch (error) { fail(error); }
            }}>{c.question}</button></li>
          ))}
        </ul>
      </Dialog>

      <Dialog open={renaming} title="Rename conversation" onClose={() => setRenaming(false)}>
        <form className="stack" onSubmit={async (e) => {
          e.preventDefault();
          const value = new FormData(e.currentTarget).get('title')?.toString().trim();
          if (!value || !currentId) return;
          try {
            const chat = await api.renameConversation(currentId, value);
            setTitle(chat.title);
            setConversations((list) => list.map((c) => (c.id === chat.id ? { ...c, title: chat.title } : c)));
            setRenaming(false);
          } catch (error) { fail(error); }
        }}>
          <label htmlFor="conversation-title">Title</label>
          <input id="conversation-title" name="title" defaultValue={title} maxLength={80} required autoFocus />
          <div className="row end">
            <button type="button" className="ghost" onClick={() => setRenaming(false)}>Cancel</button>
            <button type="submit" className="primary">Save</button>
          </div>
        </form>
      </Dialog>

      <Dialog open={confirm !== null} title={confirm?.title ?? ''} onClose={() => setConfirm(null)}>
        <p>{confirm?.body}</p>
        <div className="row end">
          <button type="button" className="ghost" onClick={() => setConfirm(null)}>Cancel</button>
          <button type="button" className="danger" onClick={async () => {
            try { await confirm?.run(); setConfirm(null); } catch (error) { setConfirm(null); fail(error); }
          }}>{confirm?.action}</button>
        </div>
      </Dialog>
    </div>
  );
}
