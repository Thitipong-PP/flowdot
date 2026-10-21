'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest, getServiceHealth, type ServiceHealth, type SessionAccount } from '../lib/api';
import { Activity, Banknote, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, ClipboardCheck, FileText, Gauge, Headphones, ImagePlus, LayoutDashboard, LockKeyhole, LogIn, MoreHorizontal, Paperclip, Plus, Send, Settings2, ShieldCheck, Sparkles, UserRound, Users, Wallet, X } from 'lucide-react';

type Message = { role: 'ai' | 'user'; text?: string; kind?: 'loans' | 'dashboard'; image?: string; };
const initialMessages: Message[] = [
  { role: 'ai', text: 'Hello! 👋 Welcome to Flow, your SME Financial Copilot.\n\nGet started by clicking “Log in / Register” in the menu below, or click any quick simulation scenario below.' },
];

type FinancingProduct = { id: string; code: string; name: string; lender: string; description: string; maximumAmount: number; startingAnnualRate: number };
type DashboardData = { source: string; totals: { income: { total: number; count: number }; expense: { total: number; count: number } }; transactions: { _id: string; type: string; description: string; category: string; amount: number; occurredAt: string }[] };

type ThoughtLog = {
  time: string;
  tag: string;
  text: string;
  type?: 'guard' | 'cashflow' | 'rag' | 'vision';
};

const RADAR_NODES = [
  { id: 'ingress', name: '01 Ingress & Fast-Path', desc: 'Fast-Path routing (<2ms bypass)' },
  { id: 'vision', name: '02 Vision OCR', desc: 'Receipt & Statement extraction' },
  { id: 'cashflow', name: '03 Cashflow Worker', desc: 'Burn rate & liquidity runway' },
  { id: 'guard', name: '04 Invariant Guard', desc: 'Zero-hallucination math check' },
  { id: 'rag', name: '05 5-Stage Agentic RAG', desc: 'Hybrid FAISS + BM25 retrieval' },
  { id: 'compiler', name: '06 Response Compiler', desc: 'Executive synthesis for SME' },
];

const initialLogs: ThoughtLog[] = [
  { time: '00:00:01', tag: 'SYSTEM', text: 'Multi-Agent Subsystem initialized. 6 Worker Nodes ready.' },
  { time: '00:00:02', tag: 'STORE', text: 'Hybrid Vector Index: FAISS IndexFlatIP + BM25Okapi loaded.' },
];

const agents = [
  { id: 'orchestrator', name: 'Orchestrator', detail: 'Understands intent and routes to specialized agents', icon: Sparkles, tone: 'violet' },
  { id: 'vision', name: 'Vision & OCR', detail: 'Extracts invoices, receipts, and bank statements', icon: FileText, tone: 'blue' },
  { id: 'cashflow', name: 'Cash-flow', detail: 'Simulates cash flow and calculates runway', icon: Activity, tone: 'green' },
  { id: 'loans', name: 'Loan Matcher', detail: 'Matches eligible SME credit facilities', icon: Banknote, tone: 'orange' },
  { id: 'guard', name: 'Sanity Guard', detail: 'Enforces invariant math and policy constraints', icon: ShieldCheck, tone: 'teal' },
  { id: 'memory', name: 'Business Memory', detail: 'Retrieves business context and profile data', icon: ClipboardCheck, tone: 'pink' },
];

export default function CopilotDemo() {
  const [view, setView] = useState<'user' | 'admin'>('user');
  const [session, setSession] = useState<SessionAccount | null>(null);
  const [recommendationResults, setRecommendationResults] = useState<FinancingProduct[]>([]);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [serviceHealth, setServiceHealth] = useState<ApiHealth | null>(null);
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [activeAgent, setActiveAgent] = useState('orchestrator');
  const [modal, setModal] = useState<'login' | 'register' | 'account' | 'dashboard' | 'support' | 'user' | null>(null);
  const [toast, setToast] = useState('');
  const [selectedUser, setSelectedUser] = useState('SME-0284');
  const [activeRadarNode, setActiveRadarNode] = useState<string | null>(null);
  const [thoughtLogs, setThoughtLogs] = useState<ThoughtLog[]>(initialLogs);
  const [diagnostics, setDiagnostics] = useState<{
    projectedCash: number | null;
    runwayDays: number | null;
    riskLevel: 'SAFE' | 'WARN' | 'CRITICAL' | null;
  }>({
    projectedCash: 450000,
    runwayDays: 42,
    riskLevel: 'SAFE',
  });

  const messageListRef = useRef<HTMLDivElement>(null);
  const terminalBodyRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachedImage, setAttachedImage] = useState<{ name: string; base64: string } | null>(null);

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
      notify('Please select a PNG, JPEG, or WebP image.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      notify('Image size must be 10MB or less.');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setAttachedImage({ name: file.name, base64: reader.result as string });
      notify(`Attached "${file.name}". Click Send or press Enter to analyze with Typhoon OCR.`);
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  }

  useEffect(() => {
    apiRequest<SessionAccount>('/auth/session').then(setSession).catch(() => setSession(null));
    getServiceHealth().then(setServiceHealth).catch(() => setServiceHealth(null));
  }, []);

  useEffect(() => {
    const messageList = messageListRef.current;
    if (messageList) messageList.scrollTop = messageList.scrollHeight;
  }, [messages]);

  useEffect(() => {
    const el = terminalBodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [thoughtLogs]);

  function getTimestamp() {
    const d = new Date();
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`;
  }

  function addLog(tag: string, text: string, type?: 'guard' | 'cashflow' | 'rag' | 'vision') {
    setThoughtLogs((prev) => [...prev.slice(-40), { time: getTimestamp(), tag, text, type }]);
  }

  const notify = useCallback((text: string) => { setToast(text); window.setTimeout(() => setToast(''), 2400); }, []);

  function reply(text: string, kind?: Message['kind']) {
    setMessages((items) => [...items, { role: 'user', text }, { role: 'ai', text: kind ? undefined : 'Understood. Reviewing your financial data…', kind }]);
    if (kind === 'loans') setActiveAgent('loans');
    else if (kind === 'dashboard') setActiveAgent('cashflow');
    else setActiveAgent('orchestrator');
  }

  async function sendMessage(value = input) {
    const text = value.trim();
    const currentAttachment = attachedImage;
    if ((!text && !currentAttachment) || isSending) return;
    if (!session) { notify('Please log in to use the assistant.'); setModal('login'); return; }
    
    setMessages((items) => [
      ...items,
      {
        role: 'user',
        text: text || (currentAttachment ? `Attached document: ${currentAttachment.name}` : ''),
        image: currentAttachment?.base64,
      }
    ]);
    setInput('');
    setAttachedImage(null);
    setActiveAgent('orchestrator');
    setIsSending(true);

    const stepTimers: NodeJS.Timeout[] = [];
    if (currentAttachment) {
      setActiveRadarNode('vision');
      addLog('VISION', `Typhoon OCR: Scanning and extracting document from "${currentAttachment.name}"...`, 'vision');
      stepTimers.push(setTimeout(() => {
        setActiveRadarNode('cashflow');
        addLog('CASHFLOW', 'Calculating daily burn rate & projected liquidity runway...', 'cashflow');
      }, 550));
      stepTimers.push(setTimeout(() => {
        setActiveRadarNode('guard');
        addLog('GUARD', 'Running invariant sanity bounds & anti-hallucination guard...', 'guard');
      }, 950));
    } else {
      addLog('ROUTER', `Received SME query: "${text.slice(0, 32)}${text.length > 32 ? '...' : ''}"`);
      setActiveRadarNode('ingress');
      stepTimers.push(setTimeout(() => {
        setActiveRadarNode('cashflow');
        addLog('CASHFLOW', 'Calculating daily burn rate & projected liquidity runway...', 'cashflow');
      }, 280));
      stepTimers.push(setTimeout(() => {
        setActiveRadarNode('guard');
        addLog('GUARD', 'Running invariant sanity bounds & anti-hallucination guard...', 'guard');
      }, 650));
    }

    if (/loan|credit|borrow|interest|financing|limit|กู้|สินเชื่อ|เครดิต|ดอกเบี้ย|วงเงิน/i.test(text)) {
      stepTimers.push(setTimeout(() => {
        setActiveRadarNode('rag');
        addLog('RAG', 'Agentic RAG: Vector search across SME loan catalog (SME D Bank, GSB, EXIM)...', 'rag');
      }, 1050));
    } else {
      stepTimers.push(setTimeout(() => {
        setActiveRadarNode('compiler');
        addLog('COMPILER', 'Synthesizing executive financial guidance for business owner...');
      }, 1050));
    }

    try {
      const result = await apiRequest<{
        message: string;
        cashflow?: { projected_cash?: number; current_cash?: number; runway_days?: number; risk_level?: 'SAFE' | 'WARN' | 'CRITICAL' };
        loans?: FinancingProduct[];
        flowType?: string;
      }>('/assistant/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: text || 'Please inspect this uploaded financial document.',
          image: currentAttachment?.base64,
        }),
      });

      stepTimers.forEach(clearTimeout);
      setActiveRadarNode('compiler');
      addLog('SYSTEM', 'Pipeline execution completed successfully.');

      setMessages((items) => [...items, { role: 'ai', text: result.message }]);

      if (result.cashflow) {
        setDiagnostics({
          projectedCash: result.cashflow.projected_cash ?? result.cashflow.current_cash ?? null,
          runwayDays: result.cashflow.runway_days ?? null,
          riskLevel: result.cashflow.risk_level ?? ((result.cashflow.runway_days ?? 99) < 30 ? 'CRITICAL' : 'SAFE'),
        });
      }

      if (Array.isArray(result.loans) && result.loans.length > 0) {
        setRecommendationResults(result.loans);
      }
    } catch (error) {
      stepTimers.forEach(clearTimeout);
      addLog('SYSTEM', `Pipeline encountered error: ${error instanceof Error ? error.message : 'Assistant request failed'}`);
      setMessages((items) => [...items, { role: 'ai', text: error instanceof Error ? error.message : 'Assistant request failed.' }]);
    } finally {
      setIsSending(false);
      setTimeout(() => setActiveRadarNode(null), 1800);
    }
  }

  async function findFinancing() {
    if (!session?.profile) {
      notify('Please log in and complete your business profile first.');
      setModal('login');
      return;
    }
    setActiveAgent('loans');
    await sendMessage('Recommend loan and financing options suitable for my business profile.');
  }

  async function loadDashboard() {
    if (!session?.profile) { notify('Please log in first to see your financial data.'); setModal('login'); return; }
    try {
      const data = await apiRequest<DashboardData>('/customers/me/dashboard');
      setDashboardData(data);
      reply('Show my stored transactions and cash flow.', 'dashboard');
      setActiveAgent('cashflow');
    } catch (error) { notify(error instanceof Error ? error.message : 'Could not load your dashboard.'); }
  }

  async function createSupportTicket(subject: string, message: string) {
    await apiRequest('/support/tickets', { method: 'POST', body: JSON.stringify({ subject, message }) });
    setModal(null);
    notify('Support request sent.');
    setMessages((items) => [...items, { role: 'user', text: subject }, { role: 'ai', text: 'Your request was sent to the support team.' }]);
  }

  async function recordTransaction(transaction: {type:'income'|'expense';description:string;category:string;amount:number}) {
    await apiRequest('/transactions', { method: 'POST', body: JSON.stringify(transaction) });
    const data = await apiRequest<DashboardData>('/customers/me/dashboard');
    setDashboardData(data);
    notify('Transaction saved to MongoDB.');
  }

  function openAdminView() {
    if (session?.role === 'admin') setView('admin');
    else { notify('Admin sign-in is required.'); setModal('login'); }
  }

  function authenticated(account: SessionAccount) {
    setSession(account);
    if (account.role === 'admin') setView('admin');
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#"><span className="brand-mark"><Activity size={19} strokeWidth={2.5}/></span><span>flow<span className="brand-dot">.</span></span></a>
        <div className="header-center"><span className="live-dot"/> Flow workspace <span className="header-slash">/</span> Backend connected</div>
        <div className="header-right"><button className="account-menu-trigger" aria-label={session ? 'Open account menu' : 'Sign in'} onClick={() => setModal(session ? 'account' : 'login')}><span className="avatar avatar-small">{session?.profile ? `${session.profile.firstName.slice(0,1)}${session.profile.lastName.slice(0,1)}` : <UserRound size={13}/>}</span><ChevronDown size={14} className="muted"/></button><button className="header-name" onClick={() => setModal(session ? 'account' : 'login')}>{session?.profile ? `${session.profile.firstName} ${session.profile.lastName}` : session?.email ?? 'Sign in'}</button></div>
      </header>

      <div className="page-wrap">
        <div className="page-heading">
          <div>
            <div className="eyebrow"><span className="eyebrow-line"/> FINANCIAL WORKSPACE</div>
            <h1>Your business, in <em>good hands.</em></h1>
            <p>Connect your business profile, financing options, and recorded transactions.</p>
          </div>
          <div className="heading-note">
            <span className="note-icon"><Sparkles size={16}/></span>
            <span>Backend<br/><b>{serviceHealth?.database === 'connected' ? 'Connected' : 'Checking…'}</b></span>
          </div>
        </div>

        <div className="view-switch" role="tablist" aria-label="Workspace view">
          <button className={view === 'user' ? 'selected' : ''} onClick={() => setView('user')} role="tab"><UserRound size={15}/> User view</button>
          <button className={view === 'admin' ? 'selected' : ''} onClick={openAdminView} role="tab"><Settings2 size={15}/> Admin view</button>
        </div>

        {view === 'user' ? (
          <section className="workspace user-workspace">
            <div className="phone-column">
              <div className="section-kicker"><span>01</span> CUSTOMER EXPERIENCE</div>
              <div className="phone-title">
                <div><h2>Customer chat preview</h2><p>In-app preview only; no LINE messages are sent.</p></div>
                <span className="live-pill"><i/> LIVE PREVIEW</span>
              </div>
              <div className="phone-frame">
                <div className="phone-camera"/>
                <div className="phone-screen">
                  <div className="phone-status"><span>9:41</span><span>●●●  ▰</span></div>
                  <div className="chat-header">
                    <ChevronRight size={19} className="back-chevron"/>
                    <span className="chat-avatar"><Activity size={16}/></span>
                    <div className="chat-user"><b>Flow · Finance Copilot</b><small><i/> Official Account</small></div>
                    <MoreHorizontal size={19} className="muted"/>
                  </div>
                  <div className="chat-day">TODAY</div>

                  <div className="message-list" ref={messageListRef}>
                    {messages.map((message, index) => (
                      <div key={index} className={`message-row ${message.role === 'user' ? 'from-user' : ''}`}>
                        {message.role === 'ai' && <span className="chat-avatar mini"><Activity size={11}/></span>}
                        <div className={`bubble ${message.role === 'user' ? 'user-bubble' : 'ai-bubble'}`}>
                          {message.image && (
                            <div style={{ marginBottom: message.text ? '0.45rem' : 0 }}>
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img src={message.image} alt="Uploaded document" style={{ maxWidth: '100%', maxHeight: '180px', borderRadius: '8px', objectFit: 'cover', display: 'block' }} />
                            </div>
                          )}
                          {message.text && <p>{message.text}</p>}
                          {message.kind === 'loans' && <LoanCards products={recommendationResults}/>}
                          {message.kind === 'dashboard' && <MiniDashboard data={dashboardData} onMore={() => setModal('dashboard')}/>}
                        </div>
                        <span className="message-time">10:4{index % 10} {message.role === 'user' && <CheckCheck size={11}/>}</span>
                      </div>
                    ))}
                  </div>

                  <div className="quick-chips-bar">
                    <button type="button" className="quick-chip danger" onClick={() => sendMessage('Just received an urgent repair bill of 95,000 THB. Will our liquidity hold up?')}>
                      🚨 95k Repair Bill
                    </button>
                    <button type="button" className="quick-chip" onClick={() => sendMessage('Paid a 15,000 THB supplier invoice. Please record and update our runway.')}>
                      ✅ 15k Supplier Invoice
                    </button>
                    <button type="button" className="quick-chip" onClick={() => sendMessage('Hello! What financial advisory and credit services does Flow provide for SMEs?')}>
                      💬 Service Intro
                    </button>
                    <button type="button" className="quick-chip" onClick={() => sendMessage('Looking for a 200,000 THB working capital loan. What SME options do you recommend?')}>
                      🏦 SME Loans
                    </button>
                  </div>

                  {attachedImage && (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 10px', background: 'rgba(2, 132, 199, 0.08)', borderRadius: '6px', margin: '0 8px 6px', fontSize: '11px', border: '1px solid rgba(2, 132, 199, 0.2)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '5px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#0369a1' }}>
                        📷 <b>Attached:</b> {attachedImage.name}
                      </span>
                      <button type="button" onClick={() => setAttachedImage(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#dc2626', fontWeight: 'bold', fontSize: '13px' }} title="Remove image">✕</button>
                    </div>
                  )}

                  <div className="quick-compose">
                    <input
                      type="file"
                      ref={fileInputRef}
                      style={{ display: 'none' }}
                      accept="image/png,image/jpeg,image/webp"
                      onChange={handleFileSelect}
                    />
                    <button type="button" aria-label="Attach image" onClick={() => fileInputRef.current?.click()} title="Upload invoice, receipt, or slip"><ImagePlus size={18}/></button>
                    <button type="button" aria-label="Attach file" onClick={() => fileInputRef.current?.click()} title="Upload invoice, receipt, or slip"><Paperclip size={17}/></button>
                    <div className="compose-input" tabIndex={isSending ? -1 : 0} aria-label="Message composer" aria-disabled={isSending} onKeyDown={(event) => { if (isSending) return; if (event.key === 'Enter') { event.preventDefault(); sendMessage(); } else if (event.key === 'Backspace') setInput((value) => value.slice(0, -1)); else if (event.key.length === 1 && !event.metaKey && !event.ctrlKey) setInput((value) => value + event.key); }}>
                      <span>{input || (isSending ? 'Processing…' : (attachedImage ? 'Add caption (optional)…' : 'Aa'))}</span><i/>
                    </div>
                    <button className="send-button" onClick={() => sendMessage()} aria-label={isSending ? 'Assistant is responding' : 'Send'} disabled={isSending}>
                      <Send size={15}/>
                    </button>
                  </div>

                  <div className="rich-menu">
                    <div className="menu-grabber"/>
                    <div className="rich-grid">
                      <button onClick={() => setModal(session ? 'account' : 'login')}><span className="menu-icon mint"><LogIn size={16}/></span><b>{session ? 'My account' : 'Log in / Register'}</b></button>
                      <button onClick={() => session ? setModal('account') : (notify('Please log in first.'), setModal('login'))}><span className="menu-icon peach"><UserRound size={16}/></span><b>Manage account</b></button>
                      <button onClick={findFinancing}><span className="menu-icon lavender"><Banknote size={16}/></span><b>Find financing</b></button>
                      <button onClick={loadDashboard}><span className="menu-icon blue"><LayoutDashboard size={16}/></span><b>Dashboard</b></button>
                      <button onClick={() => session ? setModal('support') : (notify('Please log in first.'), setModal('login'))}><span className="menu-icon yellow"><Headphones size={16}/></span><b>Contact support</b></button>
                    </div>
                  </div>
                  <div className="phone-home"/>
                </div>
              </div>
            </div>

            <div className="flow-column">
              <div className="section-kicker"><span>02</span> MULTI-AGENT RUNTIME</div>
              <div className="flow-title">
                <div>
                  <h2>Multi-Agent Subsystem</h2>
                  <p>Zero-hallucination pipeline &amp; live diagnostics.</p>
                </div>
                <span className="event-button">{serviceHealth?.assistant === 'reachable' ? '● AI Live' : 'AI Ready'}</span>
              </div>

              <div className="diag-card">
                <div className={`diag-metric ${diagnostics.riskLevel === 'CRITICAL' ? 'danger' : diagnostics.riskLevel === 'WARN' ? 'warn' : 'safe'}`}>
                  <small>PROJECTED CASH</small>
                  <b>{diagnostics.projectedCash != null ? formatBaht(diagnostics.projectedCash) : '฿ 450,000'}</b>
                </div>
                <div className={`diag-metric ${diagnostics.runwayDays != null && diagnostics.runwayDays < 30 ? 'danger' : 'safe'}`}>
                  <small>RUNWAY (DAYS)</small>
                  <b>{diagnostics.runwayDays != null ? `${diagnostics.runwayDays} days` : '42 days'}</b>
                </div>
                <div className={`diag-metric ${diagnostics.riskLevel === 'CRITICAL' ? 'danger' : diagnostics.riskLevel === 'WARN' ? 'warn' : 'safe'}`}>
                  <small>RISK STATUS</small>
                  <b>{diagnostics.riskLevel ?? 'LOW RISK'}</b>
                </div>
              </div>

              <div className="radar-card">
                <div className="radar-head">
                  <h3><Sparkles size={14} /> Multi-Agent Execution Radar</h3>
                  <span className={`radar-badge ${isSending ? 'busy' : ''}`}>
                    <i /> {isSending ? 'PROCESSING PIPELINE' : 'ALL NODES IDLE'}
                  </span>
                </div>
                <div className="radar-grid">
                  {RADAR_NODES.map((node) => (
                    <div key={node.id} className={`radar-node ${activeRadarNode === node.id ? 'active' : ''}`}>
                      <div className="radar-node-top">
                        <span className="radar-node-name">{node.name}</span>
                        <span className="radar-node-dot" />
                      </div>
                      <span className="radar-node-desc">{node.desc}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="terminal-card">
                <div className="terminal-head">
                  <span className="terminal-title">
                    <Activity size={12} /> REAL-TIME THOUGHT STREAM
                  </span>
                  <button type="button" className="terminal-clear" onClick={() => setThoughtLogs([])}>
                    CLEAR
                  </button>
                </div>
                <div className="terminal-body" ref={terminalBodyRef}>
                  {thoughtLogs.length === 0 ? (
                    <div className="terminal-empty">// No agent operations logged yet. Click a scenario chip or ask a question.</div>
                  ) : (
                    thoughtLogs.map((log, index) => (
                      <div key={index} className="terminal-line">
                        <span className="terminal-time">[{log.time}]</span>
                        <span className={`terminal-tag ${log.type ?? ''}`}>[{log.tag}]</span>
                        <span>{log.text}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="system-health">
                <div><span className="health-check"><Check size={13}/></span><b>MongoDB {serviceHealth?.database ?? 'checking'}</b></div>
                <span>AI service {serviceHealth?.assistant ?? 'checking'} · text masking before AI calls</span>
              </div>

              <div className="feature-rail">
                <div><span className="rail-icon"><Wallet size={15}/></span><span><b>Recorded transactions</b><small>Customer-scoped records in MongoDB</small></span><ChevronRight size={15}/></div>
                <div><span className="rail-icon"><Banknote size={15}/></span><span><b>Financing products</b><small>Live product matching from database</small></span><ChevronRight size={15}/></div>
                <div><span className="rail-icon"><Gauge size={15}/></span><span><b>Assistant</b><small>{serviceHealth?.assistant === 'reachable' ? 'AI service reachable' : serviceHealth?.assistant === 'not_configured' ? 'AI service not configured' : 'AI service unavailable'}</small></span><ChevronRight size={15}/></div>
              </div>
            </div>
          </section>
        ) : (
          <AdminView openModal={(name) => setModal(name)} onUser={(id) => {setSelectedUser(id); setModal('user');}} onNotify={notify} />
        )}

        <footer className="page-footer">
          <span>FLOW FINANCIAL COPILOT</span>
          <span>{session ? `${session.role} account` : 'Not signed in'} <i/> MongoDB-backed workspace</span>
          <a href="https://opentyphoon.ai/" target="_blank" rel="noreferrer">Powered by Thai AI, built for business ↗</a>
        </footer>
      </div>

      {modal && (
        <Modal
          name={modal}
          selectedUser={selectedUser}
          session={session}
          dashboardData={dashboardData}
          onAuthenticated={authenticated}
          onClose={() => setModal(null)}
          onRegister={() => setModal('register')}
          onNotify={notify}
          onSupport={createSupportTicket}
          onTransaction={recordTransaction}
          onLogout={() => {
            setSession(null);
            setView('user');
            setDashboardData(null);
            setRecommendationResults([]);
            setMessages(initialMessages);
            setActiveAgent('orchestrator');
            setInput('');
          }}
        />
      )}
      {toast && <div className="toast"><span><Check size={14}/></span>{toast}</div>}
    </div>
  );
}

function AgentIcon({id}: {id: string}) {
  const A = agents.find((a) => a.id === id)?.icon ?? Sparkles;
  return <A size={14}/>;
}

function LoanCards({products}: {products: FinancingProduct[]}) {
  return (
    <div className="loan-card-list">
      {products.length ? products.map((product, index) => (
        <div className="loan-card" key={product.id}>
          <span className={`loan-brand ${index % 2 ? 'brand-purple' : 'brand-green'}`}>{product.lender.slice(0, 1)}</span>
          <div className="loan-copy">
            <b>{product.name}</b>
            <small>{product.lender} · {product.description}</small>
          </div>
          <span className="match-chip">Eligible</span>
          <div className="loan-terms">
            <span>Up to <b>{formatBaht(product.maximumAmount)}</b></span>
            <span>From <b>{product.startingAnnualRate}% p.a.</b></span>
          </div>
          <div className="loan-disclaimer">Indicative terms. Contact {product.lender} for an application.</div>
        </div>
      )) : <p>No active products currently match your profile.</p>}
      <div className="loan-disclaimer">Eligibility is based on your saved profile. Final terms are set by each lender.</div>
    </div>
  );
}

function formatBaht(value: number) {
  return new Intl.NumberFormat('th-TH', { style: 'currency', currency: 'THB', maximumFractionDigits: 0 }).format(value);
}

function MiniDashboard({data, onMore}: {data: DashboardData | null; onMore: () => void}) {
  return (
    <div className="mini-dashboard">
      <div className="health-line">
        <div>
          <small>RECORDED INCOME</small>
          <b>{formatBaht(data?.totals.income.total ?? 0)}</b>
        </div>
        <span className="health-badge">MongoDB data</span>
      </div>
      <div className="spent-row"><span>Recorded expenses</span><b>{formatBaht(data?.totals.expense.total ?? 0)}</b></div>
      <div className="spent-row"><span>Saved transactions</span><b>{data?.transactions.length ?? 0}</b></div>
      <button className="see-more" onClick={onMore}>View transaction summary <ChevronRight size={13}/></button>
    </div>
  );
}

type AdminCustomer = { id: string; firstName: string; lastName: string; email: string; businessName: string; industry: string; createdAt: string };
type AdminTicket = { _id: string; customerId: { _id: string; firstName: string; lastName: string; businessName: string } | null; subject: string; message: string; status: 'open'|'in_progress'|'resolved'; createdAt: string };
type ApiHealth = ServiceHealth;

function AdminView({openModal, onUser, onNotify}: {openModal:(name:'login'|'register'|'account'|'dashboard'|'user'|'support')=>void; onUser:(id:string)=>void; onNotify:(text:string)=>void}) {
  const [customers, setCustomers] = useState<AdminCustomer[]>([]);
  const [tickets, setTickets] = useState<AdminTicket[]>([]);
  const [health, setHealth] = useState<ApiHealth|null>(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const [customerRows, ticketRows, apiHealth] = await Promise.all([
        apiRequest<AdminCustomer[]>('/customers'),
        apiRequest<AdminTicket[]>('/support/tickets'),
        getServiceHealth(),
      ]);
      setCustomers(customerRows);
      setTickets(ticketRows);
      setHealth(apiHealth);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not load admin data.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function resolveTicket(id: string) {
    try {
      await apiRequest(`/support/tickets/${id}`, { method: 'PATCH', body: JSON.stringify({ status: 'resolved' }) });
      setTickets((rows) => rows.map((ticket) => ticket._id === id ? { ...ticket, status: 'resolved' } : ticket));
      onNotify('Ticket marked resolved.');
    } catch (cause) {
      onNotify(cause instanceof Error ? cause.message : 'Could not update ticket.');
    }
  }

  const filteredCustomers = customers.filter((customer) => `${customer.firstName} ${customer.lastName} ${customer.email} ${customer.businessName}`.toLowerCase().includes(search.toLowerCase()));
  const filteredTickets = tickets.filter((ticket) => (statusFilter === 'all' || ticket.status === statusFilter) && `${ticket.subject} ${ticket.message} ${ticket.customerId?.firstName ?? ''} ${ticket.customerId?.lastName ?? ''}`.toLowerCase().includes(search.toLowerCase()));

  return (
    <section className="admin-view">
      <div className="admin-overview">
        <div>
          <div className="section-kicker"><span>ADMIN</span> OPERATIONS CONSOLE</div>
          <h2>Operations</h2>
          <p>Live customer records and support tickets from MongoDB.</p>
        </div>
        <button className="date-button" onClick={() => void refresh()}><span/> Refresh data <ChevronDown size={14}/></button>
      </div>

      <div className="stat-grid">
        <StatCard icon={<Users size={17}/>} label="Customer profiles" value={String(customers.length)} change="Stored in MongoDB" tone="violet" foot="Showing latest 200"/>
        <StatCard icon={<CircleHelp size={17}/>} label="Open support tickets" value={String(tickets.filter((ticket) => ticket.status === 'open').length)} change="Live ticket count" tone="orange" foot="Across customer accounts"/>
        <StatCard icon={<Activity size={17}/>} label="API / database" value={health?.database === 'connected' ? 'Online' : 'Offline'} change={health?.status === 'ok' ? 'API responding' : 'Needs attention'} tone="green" foot={health?.database ?? 'Checking connection'} />
        <StatCard icon={<Wallet size={17}/>} label="AI assistant" value={health?.assistant === 'reachable' ? 'Reachable' : health?.assistant === 'not_configured' ? 'Not configured' : 'Unavailable'} change="AI service health" tone="blue" foot="API reachability only"/>
      </div>

      {error && <div role="alert" className="data-note">Could not load live records: {error}</div>}

      <div className="admin-main-grid">
        <div className="admin-panel issues-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-icon issue-icon"><Headphones size={16}/></span>
              <div><h3>Support tickets</h3><p>Ticket records saved by customers.</p></div>
            </div>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All statuses</option>
              <option value="open">Open</option>
              <option value="in_progress">In progress</option>
              <option value="resolved">Resolved</option>
            </select>
          </div>
          <div className="user-toolbar">
            <div className="search-input"><SearchIcon/><input placeholder="Search tickets…" value={search} onChange={(event) => setSearch(event.target.value)}/></div>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>CUSTOMER</th><th>ISSUE</th><th>RECEIVED</th><th>STATUS</th><th/></tr></thead>
              <tbody>
                {filteredTickets.map((ticket) => (
                  <tr key={ticket._id}>
                    <td>
                      <div className="table-user">
                        <span className="avatar violet">{ticket.customerId?.firstName?.slice(0, 1) ?? '?'}</span>
                        <span><b>{ticket.customerId ? `${ticket.customerId.firstName} ${ticket.customerId.lastName}` : 'Deleted customer'}</b><small>{ticket.customerId?.businessName ?? '—'}</small></span>
                      </div>
                    </td>
                    <td className="issue-text"><b>{ticket.subject}</b><br/>{ticket.message}</td>
                    <td className="received-cell">{new Date(ticket.createdAt).toLocaleString()}</td>
                    <td><span className={`issue-status ${ticket.status}`}>{ticket.status.replace('_', ' ')}</span></td>
                    <td>
                      <div className="row-actions">
                        {ticket.customerId && <button title="View customer" onClick={() => onUser(ticket.customerId!._id)}><UserRound size={14}/></button>}
                        {ticket.status !== 'resolved' && <button title="Mark resolved" onClick={() => void resolveTicket(ticket._id)}><Check size={15}/></button>}
                      </div>
                    </td>
                  </tr>
                ))}
                {!loading && filteredTickets.length === 0 && <tr><td colSpan={5}>No tickets found.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="panel-footer">{loading ? 'Loading tickets…' : `${filteredTickets.length} ticket(s)`}</div>
        </div>

        <div className="admin-panel users-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-icon users-icon"><Users size={16}/></span>
              <div><h3>Customer accounts</h3><p>Registered profiles in the database.</p></div>
            </div>
            <button className="add-user" onClick={() => openModal('register')}><Plus size={13}/> Add user</button>
          </div>
          <div className="user-toolbar">
            <div className="search-input"><SearchIcon/><input placeholder="Search customers…" value={search} onChange={(event) => setSearch(event.target.value)}/></div>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>CUSTOMER</th><th>BUSINESS</th><th>INDUSTRY</th><th>CREATED</th><th/></tr></thead>
              <tbody>
                {filteredCustomers.map((customer) => (
                  <tr key={customer.id}>
                    <td>
                      <div className="table-user">
                        <span className="avatar violet">{customer.firstName.slice(0, 1)}{customer.lastName.slice(0, 1)}</span>
                        <span><b>{customer.firstName} {customer.lastName}</b><small>{customer.email}</small></span>
                      </div>
                    </td>
                    <td className="business-cell">{customer.businessName}</td>
                    <td>{customer.industry}</td>
                    <td className="received-cell">{new Date(customer.createdAt).toLocaleDateString()}</td>
                    <td><button className="user-more" onClick={() => onUser(customer.id)}><MoreHorizontal size={17}/></button></td>
                  </tr>
                ))}
                {!loading && filteredCustomers.length === 0 && <tr><td colSpan={5}>No customer profiles found.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="panel-footer">{loading ? 'Loading customers…' : `${filteredCustomers.length} customer(s)`}</div>
        </div>
      </div>

      <div className="data-note"><LockKeyhole size={13}/> Admin data is protected by role-based authorization. Request logs omit body, cookies, and PII.</div>
    </section>
  );
}

function StatCard({icon, label, value, change, tone, foot}: {icon:React.ReactNode; label:string; value:string; change:string; tone:string; foot:string}) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span className={`stat-icon ${tone}`}>{icon}</span>
        <span className={`stat-change ${change.startsWith('↑') ? 'up' : ''}`}>{change}</span>
      </div>
      <small>{label}</small>
      <b className="stat-number">{value}</b>
      <span className="stat-foot">{foot}</span>
    </div>
  );
}

function SearchIcon() {
  return <span className="search-icon"/>;
}

function Modal({
  name,
  selectedUser,
  session,
  dashboardData,
  onAuthenticated,
  onClose,
  onRegister,
  onNotify,
  onSupport,
  onTransaction,
  onLogout,
}: {
  name: string;
  selectedUser: string;
  session: SessionAccount | null;
  dashboardData: DashboardData | null;
  onAuthenticated: (account: SessionAccount) => void;
  onClose: () => void;
  onRegister: () => void;
  onNotify: (text: string) => void;
  onSupport: (subject: string, message: string) => Promise<void>;
  onTransaction: (transaction: {type:'income'|'expense'; description:string; category:string; amount:number}) => Promise<void>;
  onLogout: () => void;
}) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showTransactionForm, setShowTransactionForm] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState<Record<string, unknown> | null>(null);
  const [myTickets, setMyTickets] = useState<{_id:string; subject:string; status:string; createdAt:string}[]>([]);
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (name !== 'user' || session?.role !== 'admin') return;
    apiRequest<Record<string, unknown>>(`/customers/${selectedUser}`).then(setSelectedProfile).catch((error) => onNotify(error instanceof Error ? error.message : 'Could not load customer profile.'));
  }, [name, selectedUser, session?.role, onNotify]);

  useEffect(() => {
    if (name !== 'account' || !session?.profile) return;
    apiRequest<{_id:string; subject:string; status:string; createdAt:string}[]>('/support/tickets').then(setMyTickets).catch(() => setMyTickets([]));
  }, [name, session?.profile]);

  function fillDemo(type: 'customer' | 'admin') {
    if (!modalRef.current) return;
    const emailInput = modalRef.current.querySelector<HTMLInputElement>('[name="loginEmail"]');
    const passwordInput = modalRef.current.querySelector<HTMLInputElement>('[name="loginPassword"]');
    if (emailInput && passwordInput) {
      if (type === 'customer') {
        emailInput.value = 'customer@example.com';
        passwordInput.value = 'Customer12345678!';
      } else {
        emailInput.value = 'admin@example.com';
        passwordInput.value = 'Admin12345678!';
      }
    }
  }

  async function submitLogin() {
    const email = modalRef.current?.querySelector<HTMLInputElement>('[name="loginEmail"]')?.value.trim() ?? '';
    const password = modalRef.current?.querySelector<HTMLInputElement>('[name="loginPassword"]')?.value ?? '';
    setIsSubmitting(true);
    try {
      const account = await apiRequest<SessionAccount>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
      onAuthenticated(account);
      onNotify('Signed in successfully.');
      onClose();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Sign-in failed.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function saveAccount() {
    const value = (fieldName: string) => modalRef.current?.querySelector<HTMLInputElement>(`[name="${fieldName}"]`)?.value.trim() ?? '';
    try {
      const profile = await apiRequest<SessionAccount['profile']>('/customers/me', { method: 'PATCH', body: JSON.stringify({ firstName: value('profileFirstName'), lastName: value('profileLastName'), phone: value('profilePhone'), businessName: value('profileBusinessName'), industry: value('profileIndustry') }) });
      if (session && profile) onAuthenticated({ ...session, profile });
      onNotify('Account details updated.');
      onClose();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Could not save your account.');
    }
  }

  async function logout() {
    try {
      await apiRequest('/auth/logout', { method: 'POST' });
      onLogout();
      onNotify('Signed out.');
      onClose();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Could not sign out.');
    }
  }

  async function submitSupport() {
    const subject = modalRef.current?.querySelector<HTMLInputElement>('[name="ticketSubject"]')?.value.trim() ?? '';
    const message = modalRef.current?.querySelector<HTMLTextAreaElement>('[name="ticketMessage"]')?.value.trim() ?? '';
    try {
      await onSupport(subject, message);
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Could not send your support request.');
    }
  }

  async function submitTransaction() {
    const description = modalRef.current?.querySelector<HTMLInputElement>('[name="transactionDescription"]')?.value.trim() ?? '';
    const category = modalRef.current?.querySelector<HTMLInputElement>('[name="transactionCategory"]')?.value.trim() ?? '';
    const amount = Number(modalRef.current?.querySelector<HTMLInputElement>('[name="transactionAmount"]')?.value);
    const type = modalRef.current?.querySelector<HTMLSelectElement>('[name="transactionType"]')?.value;
    if (!description || !category || !Number.isFinite(amount) || amount <= 0 || !['income', 'expense'].includes(type ?? '')) {
      onNotify('Enter a description, category, and amount greater than zero.');
      return;
    }
    setIsSubmitting(true);
    try {
      await onTransaction({ type: type as 'income' | 'expense', description, category, amount });
      setShowTransactionForm(false);
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Could not save the transaction.');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function submitRegistration() {
    const value = (fieldName: string) => modalRef.current?.querySelector<HTMLInputElement | HTMLSelectElement>(`[name="${fieldName}"]`)?.value.trim() ?? '';
    const number = (fieldName: string) => Number(value(fieldName));
    const requiredFields = ['firstName', 'lastName', 'email', 'phone', 'password', 'businessName', 'legalEntityType', 'businessAge', 'ownerAge', 'ownerNationality', 'industry', 'annualRevenueBand', 'financingPurpose', 'vatRegistered', 'collateralAvailable', 'latePaymentOver90Days'];
    const numericFields = ['minimumCashReserve', 'monthlyDebtPayment', 'outstandingDebt', 'nextPaymentDueDay', 'fixedMonthlyExpenses'];
    if (requiredFields.some((fieldName) => !value(fieldName)) || numericFields.some((fieldName) => value(fieldName) === '' || !Number.isFinite(number(fieldName))) || number('nextPaymentDueDay') < 1 || number('nextPaymentDueDay') > 31) {
      onNotify('Please complete all onboarding fields.');
      return;
    }
    if (!consentGiven) {
      onNotify('Please give consent before creating your account.');
      return;
    }
    if (value('password').length < 12) {
      onNotify('Password must be at least 12 characters.');
      return;
    }

    const payload = {
      firstName: value('firstName'), lastName: value('lastName'), email: value('email'), phone: value('phone'), password: value('password'),
      businessName: value('businessName'), legalEntityType: value('legalEntityType'), vatRegistered: value('vatRegistered') === 'true',
      businessAge: value('businessAge'), ownerAge: value('ownerAge'), ownerNationality: value('ownerNationality'),
      industry: value('industry'), annualRevenueBand: value('annualRevenueBand'), minimumCashReserve: number('minimumCashReserve'),
      monthlyDebtPayment: number('monthlyDebtPayment'), outstandingDebt: number('outstandingDebt'), nextPaymentDueDay: number('nextPaymentDueDay'),
      fixedMonthlyExpenses: number('fixedMonthlyExpenses'), financingPurpose: value('financingPurpose'),
      collateralAvailable: value('collateralAvailable') === 'true', latePaymentOver90Days: value('latePaymentOver90Days'), financialDataConsent: true,
    };

    setIsSubmitting(true);
    try {
      const account = await apiRequest<SessionAccount>('/auth/register', { method: 'POST', body: JSON.stringify(payload) });
      onAuthenticated(account);
      onNotify('Account created and signed in.');
      onClose();
    } catch (error) {
      onNotify(error instanceof Error ? error.message : 'Could not reach the API. Check that the backend is running.');
    } finally {
      setIsSubmitting(false);
    }
  }

  const [registerStep, setRegisterStep] = useState(0);
  const [consentGiven, setConsentGiven] = useState(false);
  const titles: Record<string, string> = { login: 'Welcome back', register: 'Create your account', account: 'Manage account', dashboard: 'Financial summary', support: 'Contact support', user: 'Customer profile' };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={modalRef} className={`modal-card ${name === 'dashboard' ? 'wide-modal' : ''}`}>
        <button className="modal-close" onClick={onClose} aria-label="Close"><X size={17}/></button>
        <div className="modal-brand"><span className="brand-mark"><Activity size={16}/></span> flow<span className="brand-dot">.</span></div>
        <h2>{titles[name] ?? 'Flow'}</h2>

        {name === 'login' && (
          <>
            <p className="modal-intro">Sign in to access your saved business data.</p>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
              <button type="button" className="cancel-action" style={{ flex: 1, fontSize: '11px', padding: '6px 8px' }} onClick={() => fillDemo('customer')}>
                ⚡ Demo SME
              </button>
              <button type="button" className="cancel-action" style={{ flex: 1, fontSize: '11px', padding: '6px 8px' }} onClick={() => fillDemo('admin')}>
                🛡️ Admin Demo
              </button>
            </div>
            <label>Email<input name="loginEmail" type="email" autoComplete="username" placeholder="name@business.com" required/></label>
            <label>Password<input name="loginPassword" type="password" autoComplete="current-password" placeholder="Enter your password" required/></label>
            <button className="primary-action" disabled={isSubmitting} onClick={submitLogin}>{isSubmitting ? 'Signing in…' : 'Log in'}</button>
            <div className="modal-switch">No account yet? <button onClick={onRegister}>Register</button></div>
          </>
        )}

        {name === 'register' && (
          <>
            <p className="modal-intro">A few details help us match your business with the right support.</p>
            <div className="step-progress"><span>STEP {registerStep + 1} OF 4</span><div>{[0,1,2,3].map((step) => <i key={step} className={step <= registerStep ? 'current' : ''}/>)}</div></div>
            <div className="form-grid" hidden={registerStep !== 0}>
              <div className="step-heading full-field"><b>Your details</b><small>How can we reach you?</small></div>
              <label>First name<input name="firstName" placeholder="Ploy"/></label>
              <label>Last name<input name="lastName" placeholder="Pattanakul"/></label>
              <label>Email<input name="email" type="email" placeholder="you@business.com"/></label>
              <label>Phone number<input name="phone" type="tel" autoComplete="tel" placeholder="08X-XXX-XXXX"/></label>
              <label className="full-field">Password<input name="password" type="password" autoComplete="new-password" minLength={12} placeholder="At least 12 characters"/></label>
              <label className="full-field">Business name<input name="businessName" placeholder="Your registered business name"/></label>
              <button type="button" className="primary-action full-field" onClick={() => setRegisterStep(1)}>Continue <ChevronRight size={15}/></button>
            </div>
            <div className="form-grid" hidden={registerStep !== 1}>
              <div className="step-heading full-field"><b>Business profile</b><small>Eligibility details for financing recommendations.</small></div>
              <label>Legal entity type<select name="legalEntityType" defaultValue=""><option value="" disabled>Select type</option><option value="individual">Sole proprietor / individual</option><option value="commercial_registration">Commercial registration</option><option value="limited_partnership">Limited partnership</option><option value="limited_company">Limited company</option></select></label>
              <label>VAT registered?<select name="vatRegistered" defaultValue=""><option value="" disabled>Select one</option><option value="true">Yes</option><option value="false">No</option></select></label>
              <label>Business age<select name="businessAge" defaultValue=""><option value="" disabled>Select age</option><option value="under_6_months">Less than 6 months</option><option value="6_months_to_1_year">6 months–1 year</option><option value="1_to_3_years">1–3 years</option><option value="3_to_5_years">3–5 years</option><option value="over_5_years">More than 5 years</option></select></label>
              <label>Owner age<select name="ownerAge" defaultValue=""><option value="" disabled>Select range</option><option value="under_20">Under 20</option><option value="20_to_35">20–35</option><option value="36_to_50">36–50</option><option value="51_to_65">51–65</option><option value="over_65">Over 65</option></select></label>
              <label>Owner nationality<select name="ownerNationality" defaultValue=""><option value="" disabled>Select one</option><option value="Thai">Thai</option><option value="Other">Other</option></select></label>
              <label>Industry<select name="industry" defaultValue=""><option value="" disabled>Select industry</option><option>Retail &amp; wholesale</option><option>Food &amp; beverage</option><option>Manufacturing</option><option>Services</option><option>Construction &amp; property</option><option>Agriculture</option><option>Other</option></select></label>
              <label className="full-field">Estimated annual revenue<select name="annualRevenueBand" defaultValue=""><option value="" disabled>Select range</option><option value="up_to_75m">Up to ฿75 million</option><option value="75m_to_500m">฿75–500 million</option><option value="over_500m">Above ฿500 million</option></select></label>
              <div className="step-actions full-field"><button type="button" className="cancel-action" onClick={() => setRegisterStep(0)}>Back</button><button type="button" className="primary-action" onClick={() => setRegisterStep(2)}>Continue <ChevronRight size={15}/></button></div>
            </div>
            <div className="form-grid" hidden={registerStep !== 2}>
              <div className="step-heading full-field"><b>Cash-flow baseline</b><small>Used to estimate your cash runway and repayment capacity.</small></div>
              <label className="full-field">Minimum cash reserve to maintain<input name="minimumCashReserve" type="number" placeholder="฿ 50,000"/></label>
              <label>Existing monthly debt payment<input name="monthlyDebtPayment" type="number" placeholder="฿ 25,000"/></label>
              <label>Outstanding balance<input name="outstandingDebt" type="number" placeholder="฿ 420,000"/></label>
              <label>Next payment due day<input name="nextPaymentDueDay" type="number" min="1" max="31" placeholder="25"/></label>
              <label>Fixed monthly expenses<input name="fixedMonthlyExpenses" type="number" placeholder="฿ 80,000"/></label>
              <div className="step-actions full-field"><button type="button" className="cancel-action" onClick={() => setRegisterStep(1)}>Back</button><button type="button" className="primary-action" onClick={() => setRegisterStep(3)}>Continue <ChevronRight size={15}/></button></div>
            </div>
            <div className="form-grid" hidden={registerStep !== 3}>
              <div className="step-heading full-field"><b>Financing needs &amp; consent</b><small>We use these answers to avoid unsuitable recommendations.</small></div>
              <label className="full-field">What would you use financing for?<select name="financingPurpose" defaultValue=""><option value="" disabled>Select a purpose</option><option value="working_capital">Short-term working capital</option><option value="inventory_or_receivables">Purchase inventory or wait for customer payments</option><option value="equipment_or_investment">Long-term investment or equipment</option><option value="business_expansion">Business expansion</option></select></label>
              <label>Collateral available?<select name="collateralAvailable" defaultValue=""><option value="" disabled>Select one</option><option value="true">Yes</option><option value="false">No — prefer unsecured options</option></select></label>
              <label>Over 90 days late on a payment in the past 12 months?<select name="latePaymentOver90Days" defaultValue=""><option value="" disabled>Select one</option><option value="no">No</option><option value="yes">Yes</option><option value="prefer_not_to_say">Prefer not to say</option></select></label>
              <label className="consent-field full-field"><input type="checkbox" checked={consentGiven} onChange={(event) => setConsentGiven(event.target.checked)}/> I agree to the processing of my business and financial data to provide cash-flow insights and financing recommendations. <a href="#privacy">Privacy notice</a></label>
              <div className="step-actions full-field"><button type="button" className="cancel-action" onClick={() => setRegisterStep(2)}>Back</button><button className="primary-action" disabled={!consentGiven || isSubmitting} onClick={submitRegistration}>{isSubmitting ? 'Saving…' : 'Create account'} <Check size={14}/></button></div>
            </div>
            <div className="secure-note"><LockKeyhole size={12}/> Your information is encrypted and secure. No credit bureau score is requested.</div>
          </>
        )}

        {name === 'account' && (
          <>
            <p className="modal-intro">These details are saved to your account.</p>
            <div className="profile-row">
              <span className="avatar violet">{session?.profile?.firstName?.slice(0,1) ?? 'U'}</span>
              <div><b>{session?.profile ? `${session.profile.firstName} ${session.profile.lastName}` : session?.email}</b><small>{session?.email} · {session?.role}</small></div>
            </div>
            {session?.profile ? (
              <>
                <div className="form-grid">
                  <label>First name<input name="profileFirstName" defaultValue={session.profile.firstName}/></label>
                  <label>Last name<input name="profileLastName" defaultValue={session.profile.lastName}/></label>
                  <label>Phone<input name="profilePhone" defaultValue={session.profile.phone}/></label>
                  <label>Business<input name="profileBusinessName" defaultValue={session.profile.businessName}/></label>
                  <label className="full-field">Industry<input name="profileIndustry" defaultValue={session.profile.industry}/></label>
                </div>
                <button className="primary-action" onClick={saveAccount}>Save changes</button>
              </>
            ) : <p className="modal-intro">This administrator account has no customer profile.</p>}
            <div className="profile-details"><span>Recent support requests</span><b>{myTickets.length}</b></div>
            {myTickets.slice(0, 3).map((ticket) => (
              <div className="profile-row" key={ticket._id}>
                <div><b>{ticket.subject}</b><small>{ticket.status.replace('_', ' ')} · {new Date(ticket.createdAt).toLocaleDateString()}</small></div>
              </div>
            ))}
            <button className="cancel-action" style={{ width: '100%', marginTop: 8 }} onClick={logout}>Sign out</button>
          </>
        )}

        {name === 'dashboard' && (
          <>
            <p className="modal-intro">Totals calculated from your saved transactions in MongoDB.</p>
            <div className="dashboard-modal-grid">
              <div className="modal-metric"><small>Recorded income</small><b>{formatBaht(dashboardData?.totals.income.total ?? 0)}</b><span>{dashboardData?.totals.income.count ?? 0} transactions</span></div>
              <div className="modal-metric"><small>Recorded expenses</small><b>{formatBaht(dashboardData?.totals.expense.total ?? 0)}</b><span>{dashboardData?.totals.expense.count ?? 0} transactions</span></div>
            </div>
            <div className="large-chart">
              <div><b>Recent transactions</b><span>{dashboardData?.transactions.length ?? 0} records</span></div>
              {dashboardData?.transactions.length ? dashboardData.transactions.map((transaction) => (
                <div className="upcoming-row" key={transaction._id}>
                  <span className="calendar-icon"><Wallet size={14}/></span>
                  <span><b>{transaction.description}</b><small>{transaction.category} · {new Date(transaction.occurredAt).toLocaleDateString()}</small></span>
                  <b>{transaction.type === 'expense' ? '−' : '+'}{formatBaht(transaction.amount)}</b>
                </div>
              )) : <p className="modal-intro">No transactions have been recorded yet.</p>}
            </div>
            {showTransactionForm ? (
              <div className="form-grid">
                <label>Type<select name="transactionType" defaultValue="expense"><option value="expense">Expense</option><option value="income">Income</option></select></label>
                <label>Amount (THB)<input name="transactionAmount" type="number" min="0.01" step="0.01"/></label>
                <label>Description<input name="transactionDescription" maxLength={160}/></label>
                <label>Category<input name="transactionCategory" maxLength={80}/></label>
                <button className="primary-action full-field" disabled={isSubmitting} onClick={submitTransaction}>{isSubmitting ? 'Saving…' : 'Save transaction'}</button>
              </div>
            ) : <button className="primary-action" onClick={() => setShowTransactionForm(true)}>Record income or expense</button>}
            <button className="cancel-action" style={{ width: '100%', marginTop: 8 }} onClick={onClose}>Done</button>
          </>
        )}

        {name === 'support' && (
          <>
            <p className="modal-intro">Your request will be saved and visible to the support team.</p>
            <label>Subject<input name="ticketSubject" maxLength={160} placeholder="What do you need help with?" required/></label>
            <label>Details<textarea name="ticketMessage" maxLength={4000} rows={5} placeholder="Describe your question or issue" required/></label>
            <button className="primary-action" onClick={submitSupport}>Send support request</button>
          </>
        )}

        {name === 'user' && (
          <>
            <p className="modal-intro">Customer profile loaded from the secured backend.</p>
            {selectedProfile ? (
              <>
                <div className="profile-row">
                  <span className="avatar violet">{String(selectedProfile.firstName ?? '?').slice(0, 1)}{String(selectedProfile.lastName ?? '').slice(0, 1)}</span>
                  <div><b>{String(selectedProfile.firstName ?? '')} {String(selectedProfile.lastName ?? '')}</b><small>{String(selectedProfile.email ?? '')}</small></div>
                  <span className="issue-status open">Stored</span>
                </div>
                <div className="profile-details">
                  <span>Business</span><b>{String(selectedProfile.businessName ?? '—')}</b>
                  <span>Industry</span><b>{String(selectedProfile.industry ?? '—')}</b>
                  <span>Phone</span><b>{String(selectedProfile.phone ?? '—')}</b>
                  <span>Member since</span><b>{selectedProfile.createdAt ? new Date(String(selectedProfile.createdAt)).toLocaleDateString() : '—'}</b>
                  <span>Profile</span><b>{String(selectedProfile.id ?? selectedUser)}</b>
                </div>
                <p className="modal-intro">Sensitive account fields are only visible to authorized admins.</p>
              </>
            ) : <p className="modal-intro">Loading customer record…</p>}
            <button className="cancel-action" style={{ width: '100%' }} onClick={onClose}>Close</button>
          </>
        )}
      </div>
    </div>
  );
}
