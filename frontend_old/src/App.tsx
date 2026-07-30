import { useState, useEffect, useRef } from 'react'

export default function App() {
  const [messages, setMessages] = useState<{role: string, text: string}[]>([]);
  const [input, setInput] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Assuming user_id = 1 for prototype
    const ws = new WebSocket('ws://localhost:8000/ws/chat/1');
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'token') {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            return [...prev.slice(0, -1), { role: 'assistant', text: lastMsg.text + data.content }];
          } else {
            return [...prev, { role: 'assistant', text: data.content }];
          }
        });
      } else if (data.type === 'stt_result') {
        setMessages((prev) => [...prev, { role: 'user', text: data.content }]);
      } else if (data.type === 'tts_audio') {
        // Play the audio
        // const audio = new Audio(data.url);
        // audio.play();
        console.log("Audio URL received:", data.url);
      }
    };
    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, []);

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current) return;
    wsRef.current.send(JSON.stringify({ type: 'text', content: input }));
    setMessages((prev) => [...prev, { role: 'user', text: input }]);
    setInput('');
  };

  const toggleRecording = () => {
    setIsRecording(!isRecording);
    // Real implementation would capture MediaRecorder data and send it.
    if (!isRecording) {
      console.log("Started recording...");
    } else {
      console.log("Stopped recording, sending audio blob...");
      if (wsRef.current) {
        wsRef.current.send(JSON.stringify({ type: 'audio', content: 'base64_audio_payload_here' }));
      }
    }
  };

  return (
    <div className="flex h-screen bg-neutral-900 text-neutral-100 font-sans">
      {/* Sidebar */}
      <div className="w-64 bg-neutral-800 p-4 flex flex-col gap-4 border-r border-neutral-700">
        <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-500 bg-clip-text text-transparent">Eno AI</h1>
        <nav className="flex flex-col gap-2">
          <button className="text-left px-3 py-2 rounded bg-neutral-700 hover:bg-neutral-600 transition">Chat</button>
          <button className="text-left px-3 py-2 rounded hover:bg-neutral-700 transition text-neutral-400">Library</button>
          <button className="text-left px-3 py-2 rounded hover:bg-neutral-700 transition text-neutral-400">Courses</button>
          <button className="text-left px-3 py-2 rounded hover:bg-neutral-700 transition text-neutral-400">Memory</button>
        </nav>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Chat History */}
        <div className="flex-1 p-6 overflow-y-auto flex flex-col gap-4">
          {messages.map((msg, idx) => (
            <div key={idx} className={`p-4 rounded-xl max-w-[80%] ${msg.role === 'user' ? 'bg-blue-600 self-end' : 'bg-neutral-800 self-start border border-neutral-700 shadow-lg'}`}>
              <span className="whitespace-pre-wrap">{msg.text}</span>
            </div>
          ))}
        </div>

        {/* Input Area */}
        <div className="p-4 bg-neutral-800 border-t border-neutral-700 flex gap-2">
          <input
            type="text"
            className="flex-1 bg-neutral-900 text-white px-4 py-3 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 transition-shadow"
            placeholder="Ask Eno anything..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          />
          <button onClick={toggleRecording} className={`p-3 rounded-full transition-colors flex items-center justify-center ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-neutral-700 hover:bg-neutral-600'}`}>
            🎤
          </button>
          <button onClick={sendMessage} className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-full transition-colors font-medium">
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
