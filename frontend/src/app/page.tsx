"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useState, useEffect, useRef, useCallback } from "react";
import { Mic, Send, Bot, Sparkles, Copy, Check, Square, Trash2, Plus, MessageSquare, BookOpen, Brain, Settings, X, Headphones, Paperclip, LogOut, User, Shield, MoreHorizontal, Lock, Crown, Menu, Smartphone, HardDrive, Volume2, VolumeX, Share } from "lucide-react";
import { signOut, signIn } from "next-auth/react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import TextareaAutosize from "react-textarea-autosize";
import { API_URL, WS_URL, getHeaders, fetchAccount, fetchMyEndpoint, type Account, type EndpointInfo } from "@/lib/api";
import { listChats, getChat, saveChat, deleteChat as deleteVaultChat, requestPersistentStorage, type ChatSummary, type VaultMessage } from "@/lib/vaultDb";
import PlanCards from "@/components/PlanCards";
import VaultPanel from "@/components/VaultPanel";

interface Message {
  role: "user" | "eno" | "assistant";
  text?: string;
  content?: string; // from API
}

// Max prior messages sent with each turn (server accepts 20 total). Chats live on this device, so the
// server is stateless and the client supplies the context window.
const HISTORY_LIMIT = 19;

function buildHistory(msgs: Message[]): { role: "user" | "assistant"; content: string }[] {
  const items = msgs
    .filter((m) => m.text && !m.text.startsWith("[System]"))
    .map((m) => ({ role: (m.role === "user" ? "user" : "assistant") as "user" | "assistant", content: m.text as string }));
  const recent = items.slice(-HISTORY_LIMIT);
  // If the active @become persona was set earlier than the window, carry it along so it doesn't silently reset.
  for (let i = items.length - 1; i >= 0; i--) {
    const it = items[i];
    if (it.role !== "user") continue;
    if (it.content.startsWith("@/become")) break;
    if (it.content.startsWith("@become ")) {
      if (i < items.length - HISTORY_LIMIT) recent.unshift(it);
      break;
    }
  }
  return recent;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="p-1.5 rounded-md hover:bg-zinc-600 text-zinc-400 hover:text-white transition-all"
      title="Copy code"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

function MarkdownRenderer({ content }: { content: string }) {
  // Pre-process Gemma's LaTeX brackets into standard Markdown dollar signs
  const formattedContent = content
    .replace(/\\\[/g, '$$$$')
    .replace(/\\\]/g, '$$$$')
    .replace(/\\\(/g, '$')
    .replace(/\\\)/g, '$');

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeKatex]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          const codeString = String(children).replace(/\n$/, "");

          if (match) {
            return (
              <div className="my-3 rounded-xl overflow-hidden border border-zinc-700/50">
                <div className="flex items-center justify-between bg-zinc-800/80 px-4 py-2 text-xs text-zinc-400 font-mono">
                  <span>{match[1]}</span>
                  <CopyButton text={codeString} />
                </div>
                <SyntaxHighlighter
                  style={oneDark}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{ margin: 0, borderRadius: 0, padding: "1rem", fontSize: "0.8rem", background: "#0d1117" }}
                >
                  {codeString}
                </SyntaxHighlighter>
              </div>
            );
          }
          return <code className="bg-zinc-800 text-indigo-300 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>{children}</code>;
        }
      }}
    >
      {formattedContent}
    </ReactMarkdown>
  );
}

// Modal Component
function Modal({ title, isOpen, onClose, children, wide }: { title: string, isOpen: boolean, onClose: () => void, children: React.ReactNode, wide?: boolean }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className={`bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl w-full ${wide ? "max-w-4xl" : "max-w-lg"} overflow-hidden`}>
        <div className="flex items-center justify-between p-4 border-b border-white/5 bg-zinc-950/50">
          <h2 className="text-lg font-medium text-white">{title}</h2>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-6 max-h-[70vh] overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
function PdfUploader({ apiToken }: { apiToken: string }) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<{type: 'success' | 'error', msg: string} | null>(null);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setStatus(null);
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("course", "Knowledge Base");
    formData.append("title", file.name);

    try {
      const res = await fetch(`${API_URL}/api/ingest/pdf`, {
        method: "POST",
        body: formData,
        headers: getHeaders(apiToken)
      });
      if (res.ok) {
        setStatus({type: 'success', msg: 'Document successfully ingested to Qdrant Vector DB!'});
        setFile(null);
      } else {
        setStatus({type: 'error', msg: 'Failed to upload document.'});
      }
    } catch (e) {
      setStatus({type: 'error', msg: 'Error uploading document.'});
    }
    setUploading(false);
  };

  return (
    <div className="space-y-4 px-2">
      <div className="border-2 border-dashed border-zinc-700/50 bg-zinc-900/50 rounded-xl p-6 text-center hover:border-indigo-500/50 transition-colors">
        <input 
          type="file" 
          accept=".pdf" 
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="hidden" 
          id="pdf-upload"
        />
        <label htmlFor="pdf-upload" className="cursor-pointer flex flex-col items-center">
          <BookOpen className="w-10 h-10 text-indigo-500/70 mb-3" />
          <span className="text-zinc-300 font-medium">
            {file ? file.name : "Click to select a PDF"}
          </span>
          <span className="text-zinc-500 text-xs mt-1">Upload resumes, syllabi, or docs for RAG</span>
        </label>
      </div>
      
      {status && (
        <div className={`p-3 rounded-lg text-xs font-medium text-center ${status.type === 'success' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
          {status.msg}
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2 shadow-lg"
      >
        {uploading ? (
           <>
            <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"/>
            Chunking & Embedding...
           </>
        ) : (
          "Upload to Knowledge Base"
        )}
      </button>
    </div>
  );
}

export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");

  const handleCredentialsLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    const res = await signIn("credentials", {
      username: loginUsername,
      password: loginPassword,
      redirect: false
    });
    if (res?.error) {
      setLoginError("Invalid username or password");
    }
  };

  const apiToken = session?.apiToken || "";
  const uid = session?.user?.uid || "";

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeModel, setActiveModel] = useState<"standard" | "bro">("standard");
  
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isGenerating, setIsGeneratingState] = useState(false);
  const [aiMood, setAiMood] = useState<string>("Neutral");
  const [aiName, setAiName] = useState<string>("ENO");

  const [account, setAccount] = useState<Account | null>(null);
  const [upgradePrompt, setUpgradePrompt] = useState<{ message: string; required_plan?: "plus" | "pro" } | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [installEvent, setInstallEvent] = useState<any>(null);
  
  // Modals
  const [activeModal, setActiveModal] = useState<"courses" | "memory" | "settings" | "vault" | "plans" | null>(null);
  const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const [discoveredHostUrl, setDiscoveredHostUrl] = useState<string | null>(null);
  const [isAutoSpeakEnabled, setIsAutoSpeakEnabled] = useState(false);
  const [showIosPrompt, setShowIosPrompt] = useState(false);
  const getActivePersonaName = () => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === "user" && msg.text) {
        if (msg.text.startsWith("@/become")) return "ENO";
        if (msg.text.startsWith("@become ")) {
           const personaName = msg.text.replace("@become ", "").trim();
           if (personaName.toLowerCase().includes("girlfriend")) return "Sarah";
           if (personaName.toLowerCase().includes("pirate")) return "Blackbeard";
           return personaName;
        }
      }
    }
    return "ENO";
  };

  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const lastSpokenIndexRef = useRef<number>(-1);

  // Refs are the source of truth for things async callbacks (websocket, recorder) need to read
  // *right now*, without waiting for a React render.
  const messagesRef = useRef<Message[]>([]);
  const currentChatIdRef = useRef<string | null>(null);
  const isGeneratingRef = useRef(false);
  const uidRef = useRef("");

  const setIsGenerating = (v: boolean) => {
    isGeneratingRef.current = v;
    setIsGeneratingState(v);
  };

  const applyMessages = (updater: (prev: Message[]) => Message[]) => {
    const next = updater(messagesRef.current);
    messagesRef.current = next;
    setMessages(next);
  };

  const refreshChats = useCallback(async () => {
    if (!uidRef.current) return [];
    const list = await listChats(uidRef.current);
    setChats(list);
    return list;
  }, []);

  const refreshAccount = useCallback(async () => {
    if (!apiToken) return;
    const a = await fetchAccount(apiToken);
    if (a) setAccount(a);
  }, [apiToken]);

  /** Write a chat to the on-device vault. Never sent to the server. */
  const persistChat = useCallback(async (chatId: string, msgs: Message[]) => {
    const u = uidRef.current;
    if (!u || !chatId) return;
    const clean = msgs.filter((m) => (m.text || "").length > 0 && !(m.text || "").startsWith("[System]"));
    try {
      const existing = await getChat(u, chatId);
      const now = Date.now();
      const out: VaultMessage[] = clean.map((m, i) => {
        const role = m.role === "user" ? "user" : "assistant";
        const content = m.text || "";
        const old = existing?.messages[i];
        return { role, content, ts: old && old.role === role && old.content === content ? old.ts : now };
      });
      let title = existing?.title ?? "New Chat";
      if (title === "New Chat") {
        const first = out.find((m) => m.role === "user");
        if (first) title = first.content.slice(0, 30) + (first.content.length > 30 ? "..." : "");
      }
      await saveChat({ uid: u, id: chatId, title, created: existing?.created ?? now, updated: now, messages: out });
      refreshChats();
    } catch (e) {
      console.error("Failed to save chat to the vault", e);
    }
  }, [refreshChats]);

  async function createNewChat() {
    const u = uidRef.current;
    if (!u) return;
    // Don't pile up empty chats: if the open one is still empty, just reuse it.
    if (currentChatIdRef.current && messagesRef.current.length === 0) return;
    const id = crypto.randomUUID();
    const now = Date.now();
    try {
      await saveChat({ uid: u, id, title: "New Chat", created: now, updated: now, messages: [] });
      messagesRef.current = [];
      setMessages([]);
      setCurrentChatId(id);
      await refreshChats();
    } catch (e) {
      console.error("Failed to create chat", e);
    }
  };
  
  const deleteChat = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteVaultChat(uidRef.current, id);
      const remaining = await refreshChats();
      if (currentChatId === id) {
        if (remaining.length > 0) setCurrentChatId(remaining[0].id);
        else {
          currentChatIdRef.current = null;
          setCurrentChatId(null);
          await createNewChat();
        }
      }
    } catch (err) {
      console.error("Failed to delete chat", err);
    }
  };

  // Load this account's chats from the on-device vault
  useEffect(() => {
    uidRef.current = uid;
    if (!uid) return;
    let cancelled = false;
    (async () => {
      requestPersistentStorage();
      try {
        const list = await listChats(uid);
        if (cancelled) return;
        setChats(list);
        if (list.length > 0) setCurrentChatId(list[0].id);
        else await createNewChat();
      } catch (e) {
        console.error("Could not open the on-device vault", e);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uid]);

  // Plan / usage info
  useEffect(() => {
    refreshAccount();
  }, [refreshAccount]);

  // PWA install prompt (Chrome/Android). iOS has no prompt; the Vault/Settings copy explains Add to Home Screen.
  useEffect(() => {
    const onPrompt = (e: Event) => { e.preventDefault(); setInstallEvent(e); };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  // iOS Safari "Add to Home Screen" prompt: One-time dismissible prompt after the first chat on mobile Safari,
  // explaining that installing prevents iOS from purging IndexedDB vault history after 7 days of inactivity.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const isDismissed = localStorage.getItem("eno_ios_pwa_dismissed") === "true";
      if (isDismissed) return;

      const ua = window.navigator.userAgent;
      const isIos = /iPad|iPhone|iPod/.test(ua) && !(window as any).MSStream;
      const isSafari = /Safari/i.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS|Chrome/i.test(ua);
      const isStandalone = (window.navigator as any).standalone === true || window.matchMedia("(display-mode: standalone)").matches;

      const hasCompletedExchange = messages.some((m) => m.role === "eno" && (m.text?.length ?? 0) > 0);
      if (isIos && isSafari && !isStandalone && hasCompletedExchange && !isGenerating) {
        setShowIosPrompt(true);
      }
    } catch {
      // Ignore storage/UA errors
    }
  }, [messages, isGenerating]);

  const dismissIosPrompt = () => {
    setShowIosPrompt(false);
    try {
      localStorage.setItem("eno_ios_pwa_dismissed", "true");
    } catch {
      // Ignore
    }
  };

  // Switch chats: load messages from the vault
  useEffect(() => {
    currentChatIdRef.current = currentChatId;
    if (!currentChatId || !uid) return;
    let cancelled = false;
    getChat(uid, currentChatId).then((chat) => {
      if (cancelled) return;
      const msgs: Message[] = (chat?.messages ?? []).map((m) => ({ role: m.role === "assistant" ? "eno" : "user", text: m.content }));
      messagesRef.current = msgs;
      setMessages(msgs);
    });
    return () => { cancelled = true; };
  }, [currentChatId, uid]);

  // Connect WebSocket with Auto-Reconnect
  useEffect(() => {
    if (!currentChatId || !apiToken) return;
    const chatId = currentChatId;

    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;
    let isUnmounted = false;

    const connect = async () => {
      if (isUnmounted) return;
      if (wsRef.current) wsRef.current.close();
      
      let targetWs = WS_URL;
      try {
        const ep = await fetchMyEndpoint(apiToken);
        if (ep && ep.status === "online" && ep.endpoint_url) {
          setDiscoveredHostUrl(ep.endpoint_url);
          targetWs = ep.endpoint_url.replace(/^http/, "ws");
        }
      } catch {
        // Fallback to static WS_URL
      }

      ws = new WebSocket(`${targetWs}/ws/chat/${chatId}?token=${apiToken}`);
      ws.onopen = () => {
        setIsConnected(true);
        console.log("WebSocket connected to:", targetWs);
      };
      ws.onclose = () => {
        setIsConnected(false);
        if (!isUnmounted) {
          // Connection dropped mid-answer: keep what we received.
          if (isGeneratingRef.current) persistChat(chatId, messagesRef.current);
          console.log("WebSocket disconnected. Reconnecting in 3 seconds...");
          reconnectTimer = setTimeout(connect, 3000);
        }
        setIsGenerating(false);
      };
      ws.onerror = () => {
        setIsGenerating(false);
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "token") {
          applyMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.role === "eno") {
              return [...prev.slice(0, -1), { role: "eno", text: (lastMsg.text || "") + data.content }];
            } else {
              return [...prev, { role: "eno", text: data.content }];
            }
          });
        } else if (data.type === "done") {
          setIsGenerating(false);
          persistChat(chatId, messagesRef.current);
          refreshAccount(); // usage counter
        } else if (data.type === "error") {
          // Plan gate / daily limit: hand the user's text back and show the upgrade prompt.
          const last = messagesRef.current[messagesRef.current.length - 1];
          if (last?.role === "user") {
            setInput(last.text || "");
            applyMessages((prev) => prev.slice(0, -1));
          }
          setUpgradePrompt({ message: data.message, required_plan: data.required_plan });
        } else if (data.type === "stt_result") {
          applyMessages((prev) => [...prev, { role: "user", text: data.content }]);
        } else if (data.type === "mood") {
          setAiMood(data.content);
          if (data.name) setAiName(data.name);
        }
      };
      wsRef.current = ws;
    };

    connect();

    return () => {
      isUnmounted = true;
      clearTimeout(reconnectTimer);
      if (isGeneratingRef.current) persistChat(chatId, messagesRef.current);
      if (wsRef.current) wsRef.current.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentChatId, apiToken]);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, isGenerating]);

  // When Voice Mode opens, mark the current last message as "spoken" so it doesn't read history
  useEffect(() => {
    if (isVoiceModeOpen) {
      lastSpokenIndexRef.current = messages.length - 1;
    } else {
      window.speechSynthesis.cancel();
    }
  }, [isVoiceModeOpen]); // Intentionally not including messages in dependency array

  // Voice Mode & Read Aloud TTS Trigger
  useEffect(() => {
    if (!isVoiceModeOpen && !isAutoSpeakEnabled) return;
    
    // When generation finishes, speak the response
    if (!isGenerating && messages.length > 0) {
      const currentIndex = messages.length - 1;
      const lastMsg = messages[currentIndex];
      
      if (lastMsg.role === "eno" && lastMsg.text && lastSpokenIndexRef.current !== currentIndex) {
        lastSpokenIndexRef.current = currentIndex;
        
        window.speechSynthesis.cancel();
        // Remove markdown artifacts for cleaner speech
        const cleanText = lastMsg.text.replace(/[*_~`#\[\]\(\)]/g, "");
        const utterance = new SpeechSynthesisUtterance(cleanText);
        
        // Prefer a good native voice if available
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.name.includes("Samantha") || v.name.includes("Google US English"));
        if (preferredVoice) utterance.voice = preferredVoice;
        
        window.speechSynthesis.speak(utterance);
      }
    }
  }, [isGenerating, isVoiceModeOpen, isAutoSpeakEnabled, messages]);

  const [isUploadingChatFile, setIsUploadingChatFile] = useState(false);
  
  const handleChatFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setPendingFiles(prev => [...prev, ...Array.from(e.target.files as FileList)]);
    }
  };
  
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    const files: File[] = [];
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const file = items[i].getAsFile();
        if (file) files.push(file);
      }
    }
    if (files.length > 0) {
      setPendingFiles(prev => [...prev, ...files]);
    }
  };

  const removePendingFile = (index: number) => {
    setPendingFiles(prev => prev.filter((_, i) => i !== index));
  };

  const sendMessage = async () => {
    if ((!input.trim() && pendingFiles.length === 0) || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || isGenerating) return;
    setIsGenerating(true);
    
    let currentInput = input;
    
    if (pendingFiles.length > 0) {
      setIsUploadingChatFile(true);
      applyMessages((prev) => [...prev, { role: "assistant", text: `[System] Processing ${pendingFiles.length} file(s)...` }]);
      
      for (const file of pendingFiles) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("chat_id", currentChatId!);
        try {
          const res = await fetch(`${API_URL}/api/ingest/chat_file`, {
            method: "POST",
            body: formData,
            headers: getHeaders(apiToken)
          });
          if (res.ok) {
             const data = await res.json();
             if (data.extracted_text) {
                currentInput += `\n\n[OCR from attached file ${file.name}]:\n${data.extracted_text}`;
             }
          }
        } catch (e) {
          console.error("Failed to upload", file.name);
        }
      }
      
      // Remove system message
      applyMessages((prev) => prev.slice(0, -1));
      
      if (!input.trim()) {
        currentInput = `[User attached ${pendingFiles.length} file(s)]\n` + currentInput;
      }
      
      setPendingFiles([]);
      setIsUploadingChatFile(false);
    }

    const history = buildHistory(messagesRef.current);
    wsRef.current.send(JSON.stringify({ type: "text", content: currentInput, model: activeModel, history }));
    applyMessages((prev) => [...prev, { role: "user", text: currentInput }]);
    if (currentChatId) persistChat(currentChatId, messagesRef.current);
    setInput("");
  };

  /** Voice needs server support AND a plan that includes it. Returns true if the user may proceed. */
  const guardVoice = () => {
    if (account && !account.capabilities.voice_transcription) {
      alert("Voice transcription isn't enabled on this server.");
      return false;
    }
    if (account && !account.voice) {
      setUpgradePrompt({ message: "Voice chat is available on the Plus plan and above.", required_plan: "plus" });
      return false;
    }
    return true;
  };

  const startRecording = async () => {
    if (!guardVoice()) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });

        // POST the audio blob directly to /api/transcribe (more reliable than WebSocket binary)
        try {
          setIsGenerating(true);
          applyMessages((prev) => [...prev, { role: "user", text: "🎤 *Transcribing audio...*" }]);

          const formData = new FormData();
          formData.append("file", audioBlob, "audio.webm");

          const res = await fetch(`${API_URL}/api/transcribe`, {
            headers: getHeaders(apiToken),
            method: "POST",
            body: formData,
          });

          if (res.status === 402) {
            applyMessages((prev) => prev.slice(0, -1));
            setIsGenerating(false);
            setUpgradePrompt({ message: "Voice chat is available on the Plus plan and above.", required_plan: "plus" });
            return;
          }
          if (!res.ok) throw new Error(`Transcription failed: ${res.status}`);
          const data = await res.json();
          const transcribedText = data.text?.trim();

          if (!transcribedText) {
            applyMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "eno", text: "I couldn't hear anything clearly. Could you try again?" },
            ]);
            setIsGenerating(false);
            return;
          }

          // Replace the placeholder with the actual transcription
          applyMessages((prev) => [...prev.slice(0, -1), { role: "user", text: transcribedText }]);

          // Send transcribed text over WebSocket as a normal text message
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            const history = buildHistory(messagesRef.current.slice(0, -1));
            wsRef.current.send(JSON.stringify({ type: "text", content: transcribedText, model: activeModel, history }));
            if (currentChatId) persistChat(currentChatId, messagesRef.current);
          } else {
            applyMessages((prev) => [...prev, { role: "eno", text: "Connection lost. Please refresh." }]);
            setIsGenerating(false);
          }
        } catch (err) {
          console.error("Audio transcription error:", err);
          applyMessages((prev) => [...prev.slice(0, -1), { role: "eno", text: "Voice transcription failed. Please try typing instead." }]);
          setIsGenerating(false);
        }
      };

      mediaRecorder.start(250);
      mediaRecorderRef.current = mediaRecorder;
      setIsRecording(true);
    } catch (err) {
      alert("Microphone access is required for voice input.");
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
  };

  return (
    <>
      {status === "unauthenticated" && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4 sm:px-6 lg:px-8">
          <div className="max-w-md w-full space-y-8 bg-gray-900 p-10 rounded-2xl border border-gray-800 shadow-2xl relative">
            <div>
              <h2 className="mt-2 text-center text-3xl font-extrabold text-white">
                Welcome to Eno
              </h2>
              <p className="mt-2 text-center text-sm text-gray-400">
                Sign in to access your offline intelligence
              </p>
            </div>
            
            {loginError && (
              <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg text-sm text-center">
                {loginError}
              </div>
            )}

            <form className="mt-8 space-y-6" onSubmit={handleCredentialsLogin}>
              <div className="space-y-4 rounded-md shadow-sm">
                <div>
                  <input
                    name="username"
                    type="text"
                    required
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    className="appearance-none rounded-xl relative block w-full px-4 py-3 border border-gray-700 bg-gray-800 placeholder-gray-500 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent sm:text-sm transition-colors"
                    placeholder="Username (e.g. admin)"
                  />
                </div>
                <div>
                  <input
                    name="password"
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className="appearance-none rounded-xl relative block w-full px-4 py-3 border border-gray-700 bg-gray-800 placeholder-gray-500 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent sm:text-sm transition-colors"
                    placeholder="Password"
                  />
                </div>
              </div>

              <div>
                <button
                  type="submit"
                  className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-xl text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors shadow-lg shadow-blue-900/20"
                >
                  Sign in with Credentials
                </button>
              </div>
            </form>

            <div className="mt-6">
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-gray-900 text-gray-400">Or continue with</span>
              </div>
              <div className="mt-6">
                <button
                  onClick={() => signIn("google", { callbackUrl: "/" })}
                  className="w-full flex items-center justify-center px-4 py-3 border border-gray-700 rounded-xl shadow-sm text-sm font-medium text-white bg-gray-800 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors"
                >
                  <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                  </svg>
                  Sign in with Google
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    <div className="flex h-dvh bg-black overflow-hidden font-sans">
      {/* Mobile drawer backdrop */}
      {sidebarOpen && <div className="fixed inset-0 z-30 bg-black/60 md:hidden" onClick={() => setSidebarOpen(false)} />}

      {/* Sidebar (drawer on phones, fixed column on desktop) */}
      <div className={`${sidebarOpen ? "flex" : "hidden"} md:flex fixed md:static inset-y-0 left-0 z-40 md:z-10 w-72 md:w-64 border-r border-white/5 flex-col bg-zinc-950 md:bg-zinc-950/80 md:backdrop-blur-xl pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]`}>
        <div className="p-4 flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-white">Eno AI</h1>
        </div>
        
        <div className="px-3 pb-3">
          <button 
            onClick={() => { createNewChat(); setSidebarOpen(false); }}
            className="w-full flex items-center gap-2 justify-center px-4 py-2.5 rounded-xl bg-white/10 hover:bg-white/15 text-white text-sm font-medium transition-colors ring-1 ring-white/5"
          >
            <Plus className="w-4 h-4" /> New Chat
          </button>
        </div>

        {/* Dynamic Chats List */}
        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          <div className="px-2 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-zinc-500 uppercase">Recent Chats</div>
          {chats.map(chat => (
            <div 
              key={chat.id}
              onClick={() => { setCurrentChatId(chat.id); setSidebarOpen(false); }}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${currentChatId === chat.id ? "bg-indigo-500/10 text-indigo-300" : "hover:bg-white/5 text-zinc-400 hover:text-white"}`}
            >
              <div className="flex items-center gap-2 truncate">
                <MessageSquare className="w-4 h-4 flex-shrink-0 opacity-70" />
                <span className="text-sm truncate">{chat.title}</span>
              </div>
              <button 
                onClick={(e) => deleteChat(chat.id, e)}
                className="opacity-100 md:opacity-0 md:group-hover:opacity-100 p-1 hover:text-red-400 transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>

        <nav className="p-3 border-t border-white/5 space-y-1">
          <button onClick={() => { setActiveModal("vault"); setSidebarOpen(false); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white text-sm">
            <Lock className="w-4 h-4" /> Your Vault
          </button>
          {(!account || account.capabilities.documents) && (
            <button onClick={() => { setActiveModal("courses"); setSidebarOpen(false); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white text-sm">
              <BookOpen className="w-4 h-4" /> Courses (Knowledge Base)
            </button>
          )}
          <button onClick={() => { setActiveModal("memory"); setSidebarOpen(false); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white text-sm">
            <Brain className="w-4 h-4" /> Personalization Memory
          </button>
        </nav>

        <div className="relative p-3 border-t border-white/5">
          <button 
            onClick={() => setIsProfileMenuOpen(!isProfileMenuOpen)}
            className="w-full flex items-center justify-between p-2 rounded-xl hover:bg-white/5 transition-colors group"
          >
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-medium text-sm shadow-inner">
                {session?.user?.name?.[0]?.toUpperCase() || session?.user?.email?.[0]?.toUpperCase() || "U"}
              </div>
              <div className="flex flex-col items-start">
                <span className="text-sm font-medium text-zinc-200">{session?.user?.name || session?.user?.email?.split('@')[0] || "User"}</span>
                <span className="text-xs text-zinc-500">
                  {session?.user?.role === 'admin' ? 'Administrator' : account ? `${account.plan_label} plan${account.daily_limit !== null ? ` · ${account.used_today}/${account.daily_limit} today` : ""}` : "..."}
                </span>
              </div>
            </div>
            <MoreHorizontal className="w-4 h-4 text-zinc-500 group-hover:text-zinc-300" />
          </button>

          {isProfileMenuOpen && (
            <div className="absolute bottom-full left-3 right-3 mb-2 bg-zinc-800 border border-white/10 rounded-xl shadow-2xl p-1 z-50 animate-in slide-in-from-bottom-2 fade-in duration-200">
              {session?.user?.role === 'admin' && (
                <button onClick={() => { setIsProfileMenuOpen(false); setActiveModal("settings"); }} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/10 text-zinc-200 text-sm transition-colors">
                  <Shield className="w-4 h-4 text-indigo-400" /> Admin Dashboard
                </button>
              )}
              <button onClick={() => { setIsProfileMenuOpen(false); setActiveModal("plans"); }} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/10 text-zinc-200 text-sm transition-colors">
                <Crown className="w-4 h-4 text-amber-400" /> Plans &amp; upgrade
              </button>
              {installEvent && (
                <button onClick={async () => { setIsProfileMenuOpen(false); installEvent.prompt(); await installEvent.userChoice; setInstallEvent(null); }} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/10 text-zinc-200 text-sm transition-colors">
                  <Smartphone className="w-4 h-4" /> Install app
                </button>
              )}
              <button onClick={() => { setIsProfileMenuOpen(false); setActiveModal("settings"); }} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/10 text-zinc-200 text-sm transition-colors">
                <Settings className="w-4 h-4" /> Settings
              </button>
              <div className="h-px bg-white/5 my-1 mx-2" />
              <button onClick={() => signOut({ callbackUrl: '/' })} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-red-500/10 hover:text-red-400 text-zinc-200 text-sm transition-colors">
                <LogOut className="w-4 h-4" /> Log out
              </button>
            </div>
          )}
        </div>

      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 z-10">
        {/* Mobile top bar */}
        <div className="md:hidden flex items-center justify-between px-3 pb-2 pt-[max(0.5rem,env(safe-area-inset-top))] border-b border-white/5 bg-black/60 backdrop-blur-md">
          <button onClick={() => setSidebarOpen(true)} className="p-2 rounded-lg text-zinc-300 hover:bg-white/5" aria-label="Open menu">
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2 text-white font-semibold text-sm">
            <Bot className="w-4 h-4 text-indigo-400" /> Eno AI
          </div>
          <button onClick={() => createNewChat()} className="p-2 rounded-lg text-zinc-300 hover:bg-white/5" aria-label="New chat">
            <Plus className="w-5 h-5" />
          </button>
        </div>
        {session?.syncError && (
          <div className="px-4 py-2 text-xs text-center bg-red-500/10 text-red-300 border-b border-red-500/20">
            Signed in, but the ENO server couldn&apos;t be reached. Try signing out and back in.
          </div>
        )}
        {showIosPrompt && (
          <div className="mx-4 mt-3 mb-1 p-3.5 bg-gradient-to-r from-indigo-950/80 to-zinc-900/90 border border-indigo-500/30 rounded-2xl shadow-xl flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
            <div className="p-2 bg-indigo-500/20 text-indigo-400 rounded-xl flex-shrink-0 mt-0.5">
              <Share className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0 pr-1">
              <div className="flex items-center justify-between gap-2">
                <h4 className="text-xs font-semibold text-white">Save Chat History Permanently</h4>
                <button
                  onClick={dismissIosPrompt}
                  className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
                  aria-label="Dismiss banner"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
              <p className="text-[12px] leading-relaxed text-zinc-300 mt-1">
                Safari purges local browser vaults after 7 days of inactivity. Tap{" "}
                <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-white/10 text-indigo-300 font-medium text-[11px]">
                  <Share className="w-3 h-3 inline" /> Share
                </span>{" "}
                then <strong className="text-white font-medium">&ldquo;Add to Home Screen&rdquo;</strong> to keep your offline chat vault safe forever.
              </p>
              <div className="mt-2.5 flex items-center gap-2">
                <button
                  onClick={dismissIosPrompt}
                  className="px-3 py-1 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors shadow-sm"
                >
                  Got it
                </button>
              </div>
            </div>
          </div>
        )}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-center pt-[20vh]">
                <div className="w-16 h-16 mb-4 rounded-2xl bg-indigo-500/20 flex items-center justify-center">
                  <Sparkles className="w-8 h-8 text-indigo-400" />
                </div>
                <h2 className="text-xl font-medium text-white">How can I help?</h2>
                <p className="text-zinc-500 text-sm mt-2">Start a new conversation with Eno.</p>
                <p className="text-zinc-600 text-xs mt-4 flex items-center gap-1.5"><HardDrive className="w-3.5 h-3.5" /> Chats are saved on this device, not on our servers.</p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  {msg.role === "eno" && (
                    <div className="group relative mr-3 flex-shrink-0">
                      <div className="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center cursor-help">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                      <div className="absolute left-0 bottom-full mb-2 hidden group-hover:flex flex-col bg-zinc-800 text-xs text-white p-2.5 rounded-xl whitespace-nowrap shadow-xl border border-white/10 z-50 animate-in fade-in zoom-in-95 duration-200">
                        <span className="font-semibold text-indigo-400">{aiName}</span>
                        <span className="text-zinc-400 mt-0.5">Mood: {aiMood}</span>
                      </div>
                    </div>
                  )}
                  <div className={`text-[14px] leading-relaxed ${msg.role === "user" ? "max-w-[80%] px-4 py-3 bg-indigo-600 text-white rounded-2xl rounded-br-sm" : "max-w-[85%] text-zinc-200"}`}>
                    {msg.role === "user" ? msg.text : <MarkdownRenderer content={msg.text || ""} />}
                  </div>
                </div>
              ))
            )}
            
            {isGenerating && messages.length > 0 && messages[messages.length - 1]?.role !== "eno" && (
              <div className="flex items-start gap-3 py-1 animate-in fade-in duration-200">
                <div className="w-7 h-7 rounded-lg bg-indigo-500/80 flex items-center justify-center flex-shrink-0 shadow-lg shadow-indigo-500/20 animate-pulse">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="flex items-center gap-2.5 px-4 py-2.5 rounded-2xl bg-zinc-900/90 border border-white/5 text-zinc-300 shadow-sm">
                  <span className="text-xs font-medium text-indigo-300 tracking-wide">Eno is thinking</span>
                  <div className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                    <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.4s]" />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="p-4 pb-[max(1rem,env(safe-area-inset-bottom))] border-t border-white/5 bg-black/50 backdrop-blur-md">
          <div className="max-w-3xl mx-auto flex justify-center mb-3">
            <div className="bg-zinc-900/80 rounded-full p-1 flex gap-1 ring-1 ring-white/5">
              <button 
                onClick={() => setActiveModel("standard")}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${activeModel === "standard" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20" : "text-zinc-400 hover:text-white hover:bg-white/5"}`}
              >
                Standard (Gemma)
              </button>
              <button 
                onClick={() => {
                  if (account && !account.models.includes("bro")) {
                    setUpgradePrompt({ message: "The bigger 'Bro' model is available on the Plus plan and above.", required_plan: "plus" });
                    return;
                  }
                  setActiveModel("bro");
                }}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 ${activeModel === "bro" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20" : "text-zinc-400 hover:text-white hover:bg-white/5"}`}
              >
                Bro (Qwen)
                {account && !account.models.includes("bro") && <Lock className="w-3 h-3" />}
              </button>
            </div>
          </div>
          <div className="max-w-3xl mx-auto flex gap-2 items-center p-1.5 rounded-2xl bg-zinc-900 focus-within:ring-1 focus-within:ring-indigo-500/50 flex-col">
            {pendingFiles.length > 0 && (
              <div className="flex gap-2 w-full p-2 overflow-x-auto flex-wrap border-b border-white/5 pb-3">
                {pendingFiles.map((file, i) => (
                  <div key={i} className="relative group bg-zinc-800 rounded-lg p-2 flex items-center gap-2 text-xs text-zinc-300 w-fit">
                    <Paperclip className="w-4 h-4 text-indigo-400" />
                    <span className="truncate max-w-[100px]">{file.name}</span>
                    <button 
                      onClick={() => removePendingFile(i)}
                      className="absolute -top-1.5 -right-1.5 bg-zinc-700 hover:bg-red-500 rounded-full p-0.5 text-white shadow-lg transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2 items-center w-full">
              {(!account || account.capabilities.documents) && (
                <>
                  <input 
                    type="file" 
                    accept=".pdf,.png,.jpg,.jpeg,.webp,.heic" 
                    onChange={handleChatFileUpload}
                    className="hidden" 
                    id="chat-file-upload"
                    disabled={isUploadingChatFile || !isConnected}
                  />
                  <label htmlFor="chat-file-upload" className={`p-2.5 rounded-xl cursor-pointer transition-colors ${isUploadingChatFile ? "text-indigo-400 animate-pulse" : "text-zinc-400 hover:text-white"}`}>
                    <Paperclip className="w-5 h-5" />
                  </label>
                </>
              )}
              <button onClick={isRecording ? stopRecording : startRecording} className={`relative p-2.5 rounded-xl transition-colors ${isRecording ? "bg-red-500 text-white animate-pulse" : "text-zinc-400 hover:text-white"}`}>
                {isRecording ? <Square className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                {account && !account.voice && !isRecording && <Lock className="w-2.5 h-2.5 absolute top-1.5 right-1.5 text-amber-400" />}
              </button>
              <TextareaAutosize
                className="flex-1 bg-transparent text-white px-2 py-2.5 focus:outline-none placeholder:text-zinc-600 resize-none"
                placeholder={!isConnected ? "Reconnecting..." : isRecording ? "Recording audio..." : "Message Eno..."}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPaste={handlePaste}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                  }
                }}
                disabled={isGenerating || isRecording || !isConnected}
                maxRows={8}
              />
              <button onClick={sendMessage} disabled={(!input.trim() && pendingFiles.length === 0) || isGenerating || !isConnected} className="p-2.5 bg-indigo-600 text-white rounded-xl disabled:opacity-30">
                <Send className="w-4 h-4" />
              </button>
            </div>
            <button 
              onClick={() => { if (guardVoice()) setIsVoiceModeOpen(true); }} 
              disabled={isGenerating || !isConnected} 
              className="p-2.5 bg-zinc-800 hover:bg-indigo-500/20 text-indigo-400 rounded-xl transition-colors disabled:opacity-30 ml-1"
              title="Voice Chat Mode"
            >
              <Headphones className="w-4 h-4" />
            </button>
            <button 
              onClick={() => {
                const next = !isAutoSpeakEnabled;
                setIsAutoSpeakEnabled(next);
                if (!next) window.speechSynthesis.cancel();
              }} 
              className={`p-2.5 rounded-xl transition-colors ml-1 ${
                isAutoSpeakEnabled ? "bg-indigo-600 text-white" : "bg-zinc-800 hover:bg-indigo-500/20 text-zinc-400"
              }`}
              title={isAutoSpeakEnabled ? "Read Aloud Enabled (Click to Mute)" : "Read Aloud (Speak assistant reply on finish)"}
            >
              {isAutoSpeakEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Modals */}
      <Modal title="Personalization Memory" isOpen={activeModal === "memory"} onClose={() => setActiveModal(null)}>
        <div className="text-zinc-300 text-sm leading-relaxed space-y-4">
          <p>Personalization is <b>paused</b>. ENO no longer keeps your conversations on its servers, so it has nothing to learn your style from.</p>
          <p className="text-zinc-500 text-xs">On-device personalization (learned from your own vault, never uploaded) is on the roadmap.</p>
        </div>
      </Modal>

      <Modal title="Courses (Knowledge Base)" isOpen={activeModal === "courses"} onClose={() => setActiveModal(null)}>
        <div className="py-2">
          <PdfUploader apiToken={apiToken} />
        </div>
      </Modal>

      <Modal title="Settings" isOpen={activeModal === "settings"} onClose={() => setActiveModal(null)}>
        <div className="space-y-4 text-sm text-zinc-300">
          <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span>Inference</span>
            <span className="px-2 py-1 bg-indigo-500/20 text-indigo-300 rounded">{account?.capabilities.mode === "cloud" ? "Hosted open-weights model" : "Local (Apple MLX)"}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span>Chat storage</span>
            <span className="px-2 py-1 bg-indigo-500/20 text-indigo-300 rounded">On this device</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span>Plan</span>
            <span className="px-2 py-1 bg-indigo-500/20 text-indigo-300 rounded">{account?.plan_label ?? "..."}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span>Connection Status</span>
            <span className={`px-2 py-1 rounded ${isConnected ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
              {isConnected ? "Online" : "Offline"}
            </span>
          </div>
          <p className="text-xs text-zinc-500 leading-relaxed pt-1">
            <b className="text-zinc-400">Install on your phone:</b> iPhone: Share &rarr; Add to Home Screen. Android: menu &rarr; Install app. Installing also stops
            iOS from clearing your on-device chats after a week of inactivity.
          </p>
        </div>
      </Modal>

      <Modal title="Your Vault" isOpen={activeModal === "vault"} onClose={() => setActiveModal(null)}>
        {uid ? (
          <VaultPanel
            uid={uid}
            onChanged={async () => {
              const list = await refreshChats();
              if (list.length === 0) {
                currentChatIdRef.current = null;
                setCurrentChatId(null);
                await createNewChat();
              } else if (!currentChatIdRef.current || !list.some((c) => c.id === currentChatIdRef.current)) {
                setCurrentChatId(list[0].id);
              } else {
                // current chat may have been replaced by a newer imported copy
                const chat = await getChat(uid, currentChatIdRef.current);
                const msgs: Message[] = (chat?.messages ?? []).map((m) => ({ role: m.role === "assistant" ? "eno" : "user", text: m.content }));
                messagesRef.current = msgs;
                setMessages(msgs);
              }
            }}
          />
        ) : (
          <p className="text-sm text-zinc-500">Sign in to use your vault.</p>
        )}
      </Modal>

      <Modal wide title="Plans" isOpen={activeModal === "plans" || upgradePrompt !== null} onClose={() => { setActiveModal(null); setUpgradePrompt(null); }}>
        <div className="space-y-4">
          {upgradePrompt && (
            <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-100">{upgradePrompt.message}</div>
          )}
          <PlanCards token={apiToken} account={account} onAccountChange={setAccount} highlight={upgradePrompt?.required_plan} />
        </div>
      </Modal>

      {/* Voice Mode Overlay */}
      <Modal title="Voice Chat Mode" isOpen={isVoiceModeOpen} onClose={() => setIsVoiceModeOpen(false)}>
        <div className="flex flex-col items-center justify-center py-10 space-y-8">
          <div className="relative">
            {isGenerating && (
              <div className="absolute inset-0 bg-indigo-500 rounded-full animate-ping opacity-20 scale-150 duration-1000"></div>
            )}
            {isRecording && (
              <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-20 scale-150 duration-1000"></div>
            )}
            <button 
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isGenerating}
              className={`relative z-10 w-24 h-24 rounded-full flex items-center justify-center transition-all shadow-2xl ${
                isGenerating ? "bg-indigo-500/50 cursor-not-allowed" : 
                isRecording ? "bg-red-500 hover:bg-red-600 shadow-red-500/50" : 
                "bg-indigo-600 hover:bg-indigo-500 shadow-indigo-500/50"
              }`}
            >
              {isGenerating ? (
                <Brain className="w-10 h-10 text-white animate-pulse" />
              ) : isRecording ? (
                <Square className="w-10 h-10 text-white" />
              ) : (
                <Mic className="w-10 h-10 text-white" />
              )}
            </button>
          </div>
          
          <div className="text-center space-y-2">
            <h3 className="text-xl font-medium text-white">
              {isGenerating ? "Eno is thinking..." : isRecording ? "Listening..." : "Tap to Speak"}
            </h3>
            <p className="text-zinc-400 text-sm max-w-[250px] mx-auto">
              {isGenerating ? "The AI is processing your voice and typing a response." : isRecording ? "Tap the square when you are done speaking." : "Tap the microphone to ask a question hands-free."}
            </p>
          </div>
        </div>
      </Modal>
    </div>
    </>
  );
}
