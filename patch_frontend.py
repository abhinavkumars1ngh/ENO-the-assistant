import re

with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# Add imports
imports = """import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
"""
content = content.replace('import { useState', imports + 'import { useState')

# Add session to Home
home_hook = """export default function Home() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);

  const apiToken = session?.apiToken || "";

"""
content = content.replace("export default function Home() {\n", home_hook)

# Update NGROK_HEADERS reference
content = content.replace(
    'const NGROK_HEADERS = { "ngrok-skip-browser-warning": "true" };',
    'const getHeaders = (token: string) => ({ "ngrok-skip-browser-warning": "true", ...(token ? { Authorization: `Bearer ${token}` } : {}) });'
)

# Replace all `{ headers: NGROK_HEADERS }` with `{ headers: getHeaders(apiToken) }`
content = content.replace('{ headers: NGROK_HEADERS }', '{ headers: getHeaders(apiToken) }')
content = content.replace('{ method: "POST", headers: NGROK_HEADERS }', '{ method: "POST", headers: getHeaders(apiToken) }')
content = content.replace('{ method: "DELETE", headers: NGROK_HEADERS }', '{ method: "DELETE", headers: getHeaders(apiToken) }')

# For formData fetches, we need to add the auth header
# find: fetch(`${API_URL}/api/ingest/chat_file`, {
# replace it carefully.
content = content.replace(
    'const res = await fetch(`${API_URL}/api/ingest/chat_file`, {',
    'const res = await fetch(`${API_URL}/api/ingest/chat_file`, {\n            headers: { Authorization: `Bearer ${apiToken}` },'
)
content = content.replace(
    'const res = await fetch(`${API_URL}/api/ingest/pdf`, {',
    'const res = await fetch(`${API_URL}/api/ingest/pdf`, {\n        headers: { Authorization: `Bearer ${apiToken}` },'
)
content = content.replace(
    'const res = await fetch(`${API_URL}/api/transcribe`, {',
    'const res = await fetch(`${API_URL}/api/transcribe`, {\n            headers: { Authorization: `Bearer ${apiToken}` },'
)

# Update Websocket URL
content = content.replace(
    'wsRef.current = new WebSocket(`${WS_URL}/api/ws/chat/${currentChatId}`);',
    'wsRef.current = new WebSocket(`${WS_URL}/api/ws/chat/${currentChatId}?token=${apiToken}`);'
)

# Return null while loading session
content = content.replace(
    'return (\n    <div className="flex h-screen bg-[#09090b] text-zinc-100 font-sans">',
    'if (status === "loading" || status === "unauthenticated") return <div className="min-h-screen flex items-center justify-center bg-gray-950 text-white">Loading...</div>;\n\n  return (\n    <div className="flex h-screen bg-[#09090b] text-zinc-100 font-sans">'
)

with open("frontend/src/app/page.tsx", "w") as f:
    f.write(content)
