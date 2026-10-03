"use client";

import { useCallback, useEffect, useState } from "react";
import { Download, HardDrive, KeyRound, Lock, ShieldCheck, Trash2, Upload } from "lucide-react";
import { decryptVault, encryptVault, MIN_PASSPHRASE_LENGTH, VaultCryptoError } from "@/lib/vaultCrypto";
import { exportVault, getStats, importVault, wipeUser, type VaultStats } from "@/lib/vaultDb";

function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

type Msg = { kind: "ok" | "err"; text: string } | null;

export default function VaultPanel({ uid, onChanged }: { uid: string; onChanged: () => void }) {
  const [stats, setStats] = useState<VaultStats | null>(null);
  const [pass, setPass] = useState("");
  const [pass2, setPass2] = useState("");
  const [exportMsg, setExportMsg] = useState<Msg>(null);
  const [file, setFile] = useState<File | null>(null);
  const [importPass, setImportPass] = useState("");
  const [importMsg, setImportMsg] = useState<Msg>(null);
  const [busy, setBusy] = useState<"export" | "import" | null>(null);
  const [confirmWipe, setConfirmWipe] = useState(false);

  const refresh = useCallback(() => {
    getStats(uid).then(setStats).catch(() => setStats(null));
  }, [uid]);
  useEffect(refresh, [refresh]);

  async function doExport() {
    setExportMsg(null);
    if (pass.length < MIN_PASSPHRASE_LENGTH) return setExportMsg({ kind: "err", text: `Use at least ${MIN_PASSPHRASE_LENGTH} characters.` });
    if (pass !== pass2) return setExportMsg({ kind: "err", text: "Passphrases don't match." });
    setBusy("export");
    try {
      const data = await exportVault(uid);
      if (data.chats.length === 0) throw new VaultCryptoError("There are no chats to save yet.");
      const blob = await encryptVault(data, pass);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `eno-vault-${new Date().toISOString().slice(0, 10)}.vault`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setExportMsg({ kind: "ok", text: `Saved ${data.chats.length} chat(s), encrypted with your passphrase.` });
      setPass("");
      setPass2("");
    } catch (e) {
      setExportMsg({ kind: "err", text: e instanceof Error ? e.message : "Export failed." });
    } finally {
      setBusy(null);
    }
  }

  async function doImport() {
    setImportMsg(null);
    if (!file) return setImportMsg({ kind: "err", text: "Choose a .vault file first." });
    if (!importPass) return setImportMsg({ kind: "err", text: "Enter the passphrase you used when saving it." });
    setBusy("import");
    try {
      const text = await file.text();
      const payload = await decryptVault(text, importPass);
      const r = await importVault(uid, payload);
      setImportMsg({ kind: "ok", text: `Loaded: ${r.added} new, ${r.updated} updated, ${r.skipped} unchanged.` });
      setFile(null);
      setImportPass("");
      refresh();
      onChanged();
    } catch (e) {
      setImportMsg({ kind: "err", text: e instanceof Error ? e.message : "Import failed." });
    } finally {
      setBusy(null);
    }
  }

  async function doWipe() {
    await wipeUser(uid);
    setConfirmWipe(false);
    refresh();
    onChanged();
  }

  const input =
    "w-full rounded-lg border border-white/10 bg-zinc-950 px-3 py-2 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:ring-1 focus:ring-indigo-500/60";
  const Notice = ({ m }: { m: Msg }) =>
    m ? <div className={`rounded-lg px-3 py-2 text-xs ${m.kind === "ok" ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"}`}>{m.text}</div> : null;

  return (
    <div className="space-y-5 text-sm text-zinc-300">
      <div className="rounded-xl border border-white/10 bg-zinc-950/60 p-4 space-y-2">
        <div className="flex items-center gap-2 text-white font-medium">
          <HardDrive className="w-4 h-4 text-indigo-400" /> Your chats live on this device
        </div>
        <p className="text-xs leading-relaxed text-zinc-400">
          Conversations are saved in your browser, tied to your account, and are <b className="text-zinc-200">not stored on ENO&apos;s servers</b>. When you
          send a message, its text and recent context pass through the server to the model so it can answer; they are not kept or logged. Only
          account, plan and usage counts are stored server-side.
        </p>
        {stats && (
          <div className="flex gap-4 pt-1 text-xs text-zinc-500">
            <span>{stats.chats} chats</span>
            <span>{stats.messages} messages</span>
            <span>{fmtBytes(stats.bytes)}</span>
          </div>
        )}
      </div>

      <section className="space-y-2">
        <div className="flex items-center gap-2 text-white font-medium">
          <Download className="w-4 h-4 text-indigo-400" /> Save your vault
        </div>
        <p className="text-xs text-zinc-500">Downloads an encrypted <span className="font-mono">.vault</span> file you can load on any device.</p>
        <input type="password" autoComplete="new-password" className={input} placeholder="Choose a passphrase" value={pass} onChange={(e) => setPass(e.target.value)} />
        <input type="password" autoComplete="new-password" className={input} placeholder="Repeat passphrase" value={pass2} onChange={(e) => setPass2(e.target.value)} />
        <p className="flex gap-1.5 text-[11px] text-amber-300/80">
          <KeyRound className="w-3.5 h-3.5 shrink-0 mt-px" /> We never see this passphrase. If you forget it, the file can&apos;t be recovered.
        </p>
        <button onClick={doExport} disabled={busy !== null} className="w-full rounded-lg bg-indigo-600 py-2 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-50">
          {busy === "export" ? "Encrypting..." : "Save encrypted vault"}
        </button>
        <Notice m={exportMsg} />
      </section>

      <section className="space-y-2 border-t border-white/5 pt-5">
        <div className="flex items-center gap-2 text-white font-medium">
          <Upload className="w-4 h-4 text-indigo-400" /> Load your vault on a new device
        </div>
        <input
          type="file"
          accept=".vault,application/octet-stream"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
          className="block w-full text-xs text-zinc-400 file:mr-3 file:rounded-lg file:border-0 file:bg-zinc-800 file:px-3 file:py-2 file:text-sm file:text-zinc-200 hover:file:bg-zinc-700"
        />
        <input type="password" autoComplete="off" className={input} placeholder="Vault passphrase" value={importPass} onChange={(e) => setImportPass(e.target.value)} />
        <button onClick={doImport} disabled={busy !== null} className="w-full rounded-lg bg-zinc-800 py-2 text-white text-sm font-medium hover:bg-zinc-700 disabled:opacity-50">
          {busy === "import" ? "Decrypting..." : "Unlock & load"}
        </button>
        <Notice m={importMsg} />
        <p className="text-[11px] text-zinc-500">Merging is safe: a chat is only replaced if the file has a newer version.</p>
      </section>

      <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-3 text-xs text-indigo-200/90 flex gap-2">
        <ShieldCheck className="w-4 h-4 shrink-0 mt-px" />
        <span>
          <b>Today:</b> manual encrypted export / import. <b>Roadmap:</b> seamless end-to-end encrypted sync across your devices.
        </span>
      </div>

      <section className="border-t border-white/5 pt-5 space-y-2">
        <div className="flex items-center gap-2 text-white font-medium">
          <Lock className="w-4 h-4 text-zinc-400" /> This device
        </div>
        <p className="text-xs text-zinc-500">
          Signing out keeps your chats on this device. On a shared computer, erase them here (save your vault first if you want a copy).
        </p>
        {confirmWipe ? (
          <div className="flex gap-2">
            <button onClick={doWipe} className="flex-1 rounded-lg bg-red-600 py-2 text-white text-sm font-medium hover:bg-red-500">
              Yes, erase local chats
            </button>
            <button onClick={() => setConfirmWipe(false)} className="flex-1 rounded-lg bg-zinc-800 py-2 text-white text-sm hover:bg-zinc-700">
              Cancel
            </button>
          </div>
        ) : (
          <button onClick={() => setConfirmWipe(true)} className="flex items-center gap-2 rounded-lg border border-red-500/30 px-3 py-2 text-xs text-red-300 hover:bg-red-500/10">
            <Trash2 className="w-3.5 h-3.5" /> Erase chats on this device
          </button>
        )}
      </section>
    </div>
  );
}
