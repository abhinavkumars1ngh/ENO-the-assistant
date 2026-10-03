/**
 * Passphrase-based encryption for `.vault` files, using only the browser's Web Crypto API.
 *
 *   passphrase --PBKDF2-SHA256 (600k iterations, random 16-byte salt)--> AES-256 key
 *   plaintext JSON --AES-GCM (random 12-byte IV, header bound as AAD)--> ciphertext
 *
 * The passphrase never leaves the device and is not stored anywhere. If it is forgotten the file
 * cannot be recovered, by design: ENO's servers never see it.
 */

const MAGIC = "ENO-VAULT";
const FORMAT_VERSION = 1;
const PBKDF2_ITERATIONS = 600_000;
// Reject files asking for absurd work factors (DoS) or trivially weak ones.
const MIN_ITERATIONS = 100_000;
const MAX_ITERATIONS = 5_000_000;

interface VaultFileHeader {
  magic: string;
  v: number;
  kdf: { name: "PBKDF2"; hash: "SHA-256"; iterations: number; salt: string };
  cipher: { name: "AES-GCM"; iv: string };
}

interface VaultFile extends VaultFileHeader {
  data: string; // base64 ciphertext (includes the GCM tag)
}

export class VaultCryptoError extends Error {}

function toB64(bytes: Uint8Array): string {
  let bin = "";
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

function fromB64(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(bin.length));
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function randomBytes(n: number): Uint8Array<ArrayBuffer> {
  const out = new Uint8Array(new ArrayBuffer(n));
  crypto.getRandomValues(out);
  return out;
}

async function deriveKey(passphrase: string, salt: Uint8Array<ArrayBuffer>, iterations: number): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(passphrase.normalize("NFKC")), "PBKDF2", false, [
    "deriveKey",
  ]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

/** Everything in the header is authenticated, so tampering with KDF params is detected. */
function aad(h: VaultFileHeader): Uint8Array<ArrayBuffer> {
  const bytes = new TextEncoder().encode(
    [h.magic, h.v, h.kdf.name, h.kdf.hash, h.kdf.iterations, h.kdf.salt, h.cipher.name, h.cipher.iv].join("|")
  );
  const out = new Uint8Array(new ArrayBuffer(bytes.length));
  out.set(bytes);
  return out;
}

export function assertCryptoAvailable() {
  if (typeof crypto === "undefined" || !crypto.subtle) {
    throw new VaultCryptoError("Encryption needs a secure (HTTPS) connection.");
  }
}

export async function encryptVault(payload: unknown, passphrase: string): Promise<Blob> {
  assertCryptoAvailable();
  const salt = randomBytes(16);
  const iv = randomBytes(12);
  const header: VaultFileHeader = {
    magic: MAGIC,
    v: FORMAT_VERSION,
    kdf: { name: "PBKDF2", hash: "SHA-256", iterations: PBKDF2_ITERATIONS, salt: toB64(salt) },
    cipher: { name: "AES-GCM", iv: toB64(iv) },
  };
  const key = await deriveKey(passphrase, salt, PBKDF2_ITERATIONS);
  const plaintext = new TextEncoder().encode(JSON.stringify(payload));
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad(header) }, key, plaintext)
  );
  const file: VaultFile = { ...header, data: toB64(ciphertext) };
  return new Blob([JSON.stringify(file)], { type: "application/octet-stream" });
}

export async function decryptVault(fileText: string, passphrase: string): Promise<unknown> {
  assertCryptoAvailable();
  let file: VaultFile;
  try {
    file = JSON.parse(fileText);
  } catch {
    throw new VaultCryptoError("This doesn't look like an ENO vault file.");
  }
  if (!file || file.magic !== MAGIC || typeof file.data !== "string" || !file.kdf || !file.cipher) {
    throw new VaultCryptoError("This doesn't look like an ENO vault file.");
  }
  if (file.v !== FORMAT_VERSION) {
    throw new VaultCryptoError("This vault was made by a newer version of ENO.");
  }
  const { iterations, salt, name, hash } = file.kdf;
  if (name !== "PBKDF2" || hash !== "SHA-256" || file.cipher.name !== "AES-GCM") {
    throw new VaultCryptoError("Unsupported vault encryption settings.");
  }
  if (!Number.isInteger(iterations) || iterations < MIN_ITERATIONS || iterations > MAX_ITERATIONS) {
    throw new VaultCryptoError("Unsupported vault encryption settings.");
  }

  try {
    const key = await deriveKey(passphrase, fromB64(salt), iterations);
    const { data, ...header } = file;
    const plaintext = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: fromB64(file.cipher.iv), additionalData: aad(header) },
      key,
      fromB64(data)
    );
    return JSON.parse(new TextDecoder().decode(plaintext));
  } catch {
    // AES-GCM failure means wrong passphrase OR a modified file; we can't (and shouldn't) tell which.
    throw new VaultCryptoError("Couldn't unlock this vault. Check your passphrase, or the file may be damaged.");
  }
}

export const MIN_PASSPHRASE_LENGTH = 8;
