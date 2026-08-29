"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Mic, Send, Bot, Sparkles, Copy, Check, Square, Trash2, Plus, MessageSquare, BookOpen, Brain, Settings, X, Headphones, Paperclip } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import TextareaAutosize from "react-textarea-autosize";

interface Message {
  role: "user" | "eno" | "assistant";
  text?: string;
  content?: string; // from API
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
const NGROK_HEADERS = { "ngrok-skip-browser-warning": "true" };

interface ChatSession {
  id: string;
  title: string;
  updated: string;
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
function Modal({ title, isOpen, onClose, children }: { title: string, isOpen: boolean, onClose: () => void, children: React.ReactNode }) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">
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
function PdfUploader() {
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
        headers: NGROK_HEADERS
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
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [currentChatId, setCurrentChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [activeModel, setActiveModel] = useState<"standard" | "bro">("standard");
  
  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Modals
  const [activeModal, setActiveModal] = useState<"courses" | "memory" | "settings" | null>(null);
  const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);
  const [personaMemory, setPersonaMemory] = useState<string[]>([]);
  
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const lastSpokenIndexRef = useRef<number>(-1);

  const fetchChats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/chats`, { headers: NGROK_HEADERS });
      if (res.ok) {
        const data = await res.json();
        setChats(data.chats);
        if (data.chats.length > 0 && !currentChatId) {
          setCurrentChatId(data.chats[0].id);
        } else if (data.chats.length === 0) {
          createNewChat();
        }
      }
    } catch (e) {
      console.error("Failed to fetch chats", e);
    }
  };

  // Fetch initial chats
  useEffect(() => {
    fetchChats();
  }, []);

  const createNewChat = async () => {
    try {
      const res = await fetch(`${API_URL}/api/chats`, { method: "POST", headers: NGROK_HEADERS });
      const data = await res.json();
      setChats([data, ...chats]);
      setCurrentChatId(data.id);
    } catch (e) {
      console.error("Failed to create chat", e);
    }
  };
  
  const deleteChat = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await fetch(`${API_URL}/api/chats/${id}`, { method: "DELETE", headers: NGROK_HEADERS });
      const remaining = chats.filter(c => c.id !== id);
      setChats(remaining);
      if (currentChatId === id) {
        if (remaining.length > 0) setCurrentChatId(remaining[0].id);
        else createNewChat();
      }
    } catch (err) {
      console.error("Failed to delete chat", err);
    }
  };

  const fetchMemory = async () => {
    try {
      const res = await fetch(`${API_URL}/api/memory`, { headers: NGROK_HEADERS });
      const data = await res.json();
      setPersonaMemory(data.persona);
    } catch (e) {
      console.error(e);
    }
  };

  // Switch chats
  useEffect(() => {
    if (!currentChatId) return;
    
    // 1. Fetch messages
    const loadMessages = async () => {
      try {
        const res = await fetch(`${API_URL}/api/chats/${currentChatId}/messages`, { headers: NGROK_HEADERS });
        const data = await res.json();
        // API returns { role, content }, map to our state format
        setMessages(data.messages.map((m: { role: string; content: string }) => ({ role: m.role === "assistant" ? "eno" : "user", text: m.content })));
      } catch (e) {
        console.error("Failed to fetch messages", e);
      }
    };
    loadMessages();

    // 2. Connect WebSocket with Auto-Reconnect
    let ws: WebSocket;
    let reconnectTimer: NodeJS.Timeout;
    let isUnmounted = false;

    const connect = () => {
      if (isUnmounted || !currentChatId) return;
      if (wsRef.current) wsRef.current.close();
      
      ws = new WebSocket(`${WS_URL}/ws/chat/${currentChatId}`);
      ws.onopen = () => {
        setIsConnected(true);
        console.log("WebSocket connected.");
      };
      ws.onclose = () => {
        setIsConnected(false);
        setIsGenerating(false);
        if (!isUnmounted) {
          console.log("WebSocket disconnected. Reconnecting in 3 seconds...");
          reconnectTimer = setTimeout(connect, 3000);
        }
      };
      ws.onerror = () => {
        setIsGenerating(false);
      };
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "token") {
          setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (lastMsg && lastMsg.role === "eno") {
              return [...prev.slice(0, -1), { role: "eno", text: (lastMsg.text || "") + data.content }];
            } else {
              return [...prev, { role: "eno", text: data.content }];
            }
          });
        } else if (data.type === "done") {
          setIsGenerating(false);
          fetchChats(); // Refresh titles
        } else if (data.type === "stt_result") {
          setMessages((prev) => [...prev, { role: "user", text: data.content }]);
        }
      };
      wsRef.current = ws;
    };

    connect();

    return () => {
      isUnmounted = true;
      clearTimeout(reconnectTimer);
      if (wsRef.current) wsRef.current.close();
    };
  }, [currentChatId]);

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

  // Voice Mode TTS Trigger
  useEffect(() => {
    if (!isVoiceModeOpen) return;
    
    // When generation finishes in voice mode, speak the response
    if (!isGenerating && messages.length > 0) {
      const currentIndex = messages.length - 1;
      const lastMsg = messages[currentIndex];
      
      if (lastMsg.role === "eno" && lastMsg.text && lastSpokenIndexRef.current !== currentIndex) {
        lastSpokenIndexRef.current = currentIndex;
        
        window.speechSynthesis.cancel();
        // Remove markdown artifacts for cleaner speech (naive regex)
        const cleanText = lastMsg.text.replace(/[*_~`#]/g, "");
        const utterance = new SpeechSynthesisUtterance(cleanText);
        
        // Prefer a good native voice if available
        const voices = window.speechSynthesis.getVoices();
        const preferredVoice = voices.find(v => v.name.includes("Samantha") || v.name.includes("Google US English"));
        if (preferredVoice) utterance.voice = preferredVoice;
        
        window.speechSynthesis.speak(utterance);
      }
    }
  }, [isGenerating, isVoiceModeOpen, messages]);

  const [isUploadingChatFile, setIsUploadingChatFile] = useState(false);
  const handleChatFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !currentChatId) return;
    setIsUploadingChatFile(true);
    
    // Optimistically show system message
    setMessages(prev => [...prev, { role: "assistant", text: `[System] Uploading and processing ${file.name} for this chat...` }]);
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("chat_id", currentChatId);

    try {
      const res = await fetch(`${API_URL}/api/ingest/chat_file`, {
        method: "POST",
        body: formData,
        headers: NGROK_HEADERS
      });
      if (res.ok) {
        setMessages(prev => [...prev.slice(0, -1), { role: "assistant", text: `[System] ✅ Successfully uploaded **${file.name}**. You can now ask questions about it.` }]);
      } else {
        setMessages(prev => [...prev.slice(0, -1), { role: "assistant", text: `[System] ❌ Failed to upload ${file.name}.` }]);
      }
    } catch (e) {
      setMessages(prev => [...prev.slice(0, -1), { role: "assistant", text: `[System] ❌ Error uploading ${file.name}.` }]);
    }
    setIsUploadingChatFile(false);
  };

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || isGenerating) return;
    setIsGenerating(true);
    wsRef.current.send(JSON.stringify({ type: "text", content: input, model: activeModel }));
    setMessages((prev) => [...prev, { role: "user", text: input }]);
    setInput("");
  };

  const startRecording = async () => {
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
          setMessages((prev) => [...prev, { role: "user", text: "🎤 *Transcribing audio...*" }]);

          const formData = new FormData();
          formData.append("file", audioBlob, "audio.webm");

          const res = await fetch(`${API_URL}/api/transcribe`, {
            method: "POST",
            headers: { "ngrok-skip-browser-warning": "true" },
            body: formData,
          });

          if (!res.ok) throw new Error(`Transcription failed: ${res.status}`);
          const data = await res.json();
          const transcribedText = data.text?.trim();

          if (!transcribedText) {
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "eno", text: "I couldn't hear anything clearly. Could you try again?" },
            ]);
            setIsGenerating(false);
            return;
          }

          // Replace the placeholder with the actual transcription
          setMessages((prev) => [...prev.slice(0, -1), { role: "user", text: transcribedText }]);

          // Send transcribed text over WebSocket as a normal text message
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "text", content: transcribedText, model: activeModel }));
          } else {
            setMessages((prev) => [...prev, { role: "eno", text: "Connection lost. Please refresh." }]);
            setIsGenerating(false);
          }
        } catch (err) {
          console.error("Audio transcription error:", err);
          setMessages((prev) => [...prev.slice(0, -1), { role: "eno", text: "Voice transcription failed. Please try typing instead." }]);
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
    <div className="flex h-dvh bg-black overflow-hidden font-sans">
      {/* Sidebar */}
      <div className="w-64 border-r border-white/5 hidden md:flex flex-col z-10 bg-zinc-950/80 backdrop-blur-xl">
        <div className="p-4 flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-white">Eno AI</h1>
        </div>
        
        <div className="px-3 pb-3">
          <button 
            onClick={createNewChat}
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
              onClick={() => setCurrentChatId(chat.id)}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors ${currentChatId === chat.id ? "bg-indigo-500/10 text-indigo-300" : "hover:bg-white/5 text-zinc-400 hover:text-white"}`}
            >
              <div className="flex items-center gap-2 truncate">
                <MessageSquare className="w-4 h-4 flex-shrink-0 opacity-70" />
                <span className="text-sm truncate">{chat.title}</span>
              </div>
              <button 
                onClick={(e) => deleteChat(chat.id, e)}
                className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>

        <nav className="p-3 border-t border-white/5 space-y-1">
          <button onClick={() => setActiveModal("courses")} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white text-sm">
            <BookOpen className="w-4 h-4" /> Courses
          </button>
          <button onClick={() => { fetchMemory(); setActiveModal("memory"); }} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white text-sm">
            <Brain className="w-4 h-4" /> Memory
          </button>
          <button onClick={() => setActiveModal("settings")} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-zinc-400 hover:text-white text-sm">
            <Settings className="w-4 h-4" /> Settings
          </button>
        </nav>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 z-10">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-center pt-[20vh]">
                <div className="w-16 h-16 mb-4 rounded-2xl bg-indigo-500/20 flex items-center justify-center">
                  <Sparkles className="w-8 h-8 text-indigo-400" />
                </div>
                <h2 className="text-xl font-medium text-white">How can I help?</h2>
                <p className="text-zinc-500 text-sm mt-2">Start a new conversation with Eno.</p>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`flex w-full ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  {msg.role === "eno" && (
                    <div className="w-7 h-7 rounded-lg bg-indigo-500 flex items-center justify-center mr-3 flex-shrink-0">
                      <Bot className="w-4 h-4 text-white" />
                    </div>
                  )}
                  <div className={`text-[14px] leading-relaxed ${msg.role === "user" ? "max-w-[80%] px-4 py-3 bg-indigo-600 text-white rounded-2xl rounded-br-sm" : "max-w-[85%] text-zinc-200"}`}>
                    {msg.role === "user" ? msg.text : <MarkdownRenderer content={msg.text || ""} />}
                  </div>
                </div>
              ))
            )}
            
            {isGenerating && messages.length > 0 && messages[messages.length - 1]?.role !== "eno" && (
              <div className="flex items-center gap-3 pl-10 pt-2 text-indigo-400 text-sm">
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce delay-150" />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce delay-300" />
              </div>
            )}
          </div>
        </div>

        <div className="p-4 border-t border-white/5 bg-black/50 backdrop-blur-md">
          <div className="max-w-3xl mx-auto flex justify-center mb-3">
            <div className="bg-zinc-900/80 rounded-full p-1 flex gap-1 ring-1 ring-white/5">
              <button 
                onClick={() => setActiveModel("standard")}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${activeModel === "standard" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20" : "text-zinc-400 hover:text-white hover:bg-white/5"}`}
              >
                Standard (Gemma)
              </button>
              <button 
                onClick={() => setActiveModel("bro")}
                className={`px-4 py-1.5 rounded-full text-xs font-medium transition-all ${activeModel === "bro" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20" : "text-zinc-400 hover:text-white hover:bg-white/5"}`}
              >
                Bro (Qwen)
              </button>
            </div>
          </div>
          <div className="max-w-3xl mx-auto flex gap-2 items-center p-1.5 rounded-2xl bg-zinc-900 focus-within:ring-1 focus-within:ring-indigo-500/50">
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
            <button onClick={isRecording ? stopRecording : startRecording} className={`p-2.5 rounded-xl transition-colors ${isRecording ? "bg-red-500 text-white animate-pulse" : "text-zinc-400 hover:text-white"}`}>
              {isRecording ? <Square className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
            <TextareaAutosize
              className="flex-1 bg-transparent text-white px-2 py-2.5 focus:outline-none placeholder:text-zinc-600 resize-none"
              placeholder={!isConnected ? "Reconnecting..." : isRecording ? "Recording audio..." : "Message Eno..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              disabled={isGenerating || isRecording || !isConnected}
              maxRows={8}
            />
            <button onClick={sendMessage} disabled={!input.trim() || isGenerating || !isConnected} className="p-2.5 bg-indigo-600 text-white rounded-xl disabled:opacity-30">
              <Send className="w-4 h-4" />
            </button>
            <button 
              onClick={() => setIsVoiceModeOpen(true)} 
              disabled={isGenerating || !isConnected} 
              className="p-2.5 bg-zinc-800 hover:bg-indigo-500/20 text-indigo-400 rounded-xl transition-colors disabled:opacity-30 ml-1"
              title="Voice Chat Mode"
            >
              <Headphones className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Modals */}
      <Modal title="Your Memory Persona" isOpen={activeModal === "memory"} onClose={() => setActiveModal(null)}>
        <div className="text-zinc-300 text-sm leading-relaxed space-y-4">
          <p>Eno continually analyzes your conversation history to adapt to your texting style, tone, and preferences. Here is what Eno currently knows about you:</p>
          <div className="p-4 bg-zinc-950 rounded-xl border border-white/5 font-mono text-xs text-indigo-300 whitespace-pre-wrap">
            {personaMemory.length > 0 ? personaMemory[0] : "No memory profile built yet. Keep chatting with Eno so it can learn your style!"}
          </div>
        </div>
      </Modal>

      <Modal title="Courses (Knowledge Base)" isOpen={activeModal === "courses"} onClose={() => setActiveModal(null)}>
        <div className="py-2">
          <PdfUploader />
        </div>
      </Modal>

      <Modal title="Settings" isOpen={activeModal === "settings"} onClose={() => setActiveModal(null)}>
        <div className="space-y-4 text-sm text-zinc-300">
          <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span>LLM Model</span>
            <span className="px-2 py-1 bg-indigo-500/20 text-indigo-300 rounded">Qwen 2.5 (Local)</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-white/5">
            <span>Voice Transcription</span>
            <span className="px-2 py-1 bg-indigo-500/20 text-indigo-300 rounded">Whisper (Local)</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span>Connection Status</span>
            <span className={`px-2 py-1 rounded ${isConnected ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
              {isConnected ? "Online" : "Offline"}
            </span>
          </div>
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
  );
}
