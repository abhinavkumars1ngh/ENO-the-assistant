/**
 * On-device chat vault (IndexedDB).
 *
 * Chats are stored in the browser, namespaced by the account's opaque `uid`, and are NOT sent to
 * the ENO server for storage. (The text of a message does travel to the server transiently so the
 * model can answer it; the server keeps no copy.)
 *
 * Each chat is a single record containing its messages, which keeps writes atomic and makes
 * export/import trivial.
 */

export interface VaultMessage {
  role: "user" | "assistant";
  content: string;
  ts: number;
}

export interface VaultChat {
  uid: string;
  id: string;
  title: string;
  created: number;
  updated: number;
  messages: VaultMessage[];
}

export type ChatSummary = Pick<VaultChat, "id" | "title" | "updated"> & { messageCount: number };

export interface VaultStats {
  chats: number;
  messages: number;
  bytes: number;
}

/** Shape written into an exported `.vault` file (before encryption). */
export interface VaultExport {
  app: "eno";
  version: 1;
  exportedAt: number;
  chats: Omit<VaultChat, "uid">[];
}

const DB_NAME = "eno-vault";
const DB_VERSION = 1;
const STORE = "chats";

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("IndexedDB is not available in this browser"));
  }
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: ["uid", "id"] });
          store.createIndex("byUid", "uid", { unique: false });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => {
        dbPromise = null;
        reject(req.error);
      };
    });
  }
  return dbPromise;
}

function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> {
  return openDb().then(
    (db) =>
      new Promise<T | undefined>((resolve, reject) => {
        const transaction = db.transaction(STORE, mode);
        const store = transaction.objectStore(STORE);
        const req = run(store);
        transaction.oncomplete = () => resolve(req ? (req.result as T) : undefined);
        transaction.onerror = () => reject(transaction.error);
        transaction.onabort = () => reject(transaction.error);
      })
  );
}

function allForUser(uid: string): Promise<VaultChat[]> {
  return openDb().then(
    (db) =>
      new Promise<VaultChat[]>((resolve, reject) => {
        const req = db.transaction(STORE, "readonly").objectStore(STORE).index("byUid").getAll(IDBKeyRange.only(uid));
        req.onsuccess = () => resolve(req.result as VaultChat[]);
        req.onerror = () => reject(req.error);
      })
  );
}

export async function listChats(uid: string): Promise<ChatSummary[]> {
  const chats = await allForUser(uid);
  return chats
    .map((c) => ({ id: c.id, title: c.title, updated: c.updated, messageCount: c.messages.length }))
    .sort((a, b) => b.updated - a.updated);
}

export async function getChat(uid: string, id: string): Promise<VaultChat | undefined> {
  return (await tx<VaultChat>("readonly", (s) => s.get([uid, id]))) || undefined;
}

export async function saveChat(chat: VaultChat): Promise<void> {
  await tx("readwrite", (s) => s.put(chat));
}

export async function deleteChat(uid: string, id: string): Promise<void> {
  await tx("readwrite", (s) => s.delete([uid, id]));
}

/** Erase everything this browser holds for one account. */
export async function wipeUser(uid: string): Promise<void> {
  const chats = await allForUser(uid);
  await tx("readwrite", (s) => {
    chats.forEach((c) => s.delete([uid, c.id]));
  });
}

export async function getStats(uid: string): Promise<VaultStats> {
  const chats = await allForUser(uid);
  let messages = 0;
  let bytes = 0;
  for (const c of chats) {
    messages += c.messages.length;
    bytes += new Blob([JSON.stringify(c)]).size;
  }
  return { chats: chats.length, messages, bytes };
}

export async function exportVault(uid: string): Promise<VaultExport> {
  const chats = await allForUser(uid);
  return {
    app: "eno",
    version: 1,
    exportedAt: Date.now(),
    chats: chats.map(({ uid: _uid, ...rest }) => rest),
  };
}

function isValidMessage(m: unknown): m is VaultMessage {
  if (!m || typeof m !== "object") return false;
  const x = m as Record<string, unknown>;
  return (x.role === "user" || x.role === "assistant") && typeof x.content === "string";
}

/**
 * Merge an imported vault into this account's local vault. A chat that already exists is only
 * replaced if the imported copy is newer, so importing an old backup never destroys newer work.
 */
export async function importVault(uid: string, data: unknown): Promise<{ added: number; updated: number; skipped: number }> {
  const payload = data as Partial<VaultExport> | null;
  if (!payload || payload.app !== "eno" || payload.version !== 1 || !Array.isArray(payload.chats)) {
    throw new Error("This file is not an ENO vault.");
  }

  const existing = new Map((await allForUser(uid)).map((c) => [c.id, c]));
  let added = 0;
  let updated = 0;
  let skipped = 0;

  for (const raw of payload.chats) {
    if (!raw || typeof raw.id !== "string" || !Array.isArray(raw.messages)) {
      skipped++;
      continue;
    }
    const chat: VaultChat = {
      uid,
      id: raw.id,
      title: typeof raw.title === "string" ? raw.title.slice(0, 200) : "Imported chat",
      created: Number(raw.created) || Date.now(),
      updated: Number(raw.updated) || Date.now(),
      messages: raw.messages
        .filter(isValidMessage)
        .map((m) => ({ role: m.role, content: m.content, ts: Number(m.ts) || Date.now() })),
    };
    const current = existing.get(chat.id);
    if (!current) {
      await saveChat(chat);
      added++;
    } else if (chat.updated > current.updated) {
      await saveChat(chat);
      updated++;
    } else {
      skipped++;
    }
  }
  return { added, updated, skipped };
}

/** Ask the browser not to evict our storage under pressure (best effort; iOS honours it for installed PWAs). */
export async function requestPersistentStorage(): Promise<boolean> {
  try {
    if (navigator.storage?.persist) return await navigator.storage.persist();
  } catch {
    /* ignore */
  }
  return false;
}
