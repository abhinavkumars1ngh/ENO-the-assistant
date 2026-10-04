import { getApiUrl, getHeaders, type Account } from "./api";

interface RazorpaySuccess {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

interface RazorpayOptions {
  key: string;
  amount: number;
  currency: string;
  order_id: string;
  name: string;
  description: string;
  prefill?: { email?: string };
  theme?: { color: string };
  handler: (r: RazorpaySuccess) => void;
  modal?: { ondismiss?: () => void };
}

declare global {
  interface Window {
    Razorpay?: new (opts: RazorpayOptions) => { open: () => void; on: (ev: string, cb: (r: unknown) => void) => void };
  }
}

export class CheckoutCancelled extends Error {}

function loadRazorpay(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[src="https://checkout.razorpay.com/v1/checkout.js"]');
    const script = existing || document.createElement("script");
    script.addEventListener("load", () => resolve());
    script.addEventListener("error", () => reject(new Error("Could not load Razorpay Checkout")));
    if (!existing) {
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.async = true;
      document.body.appendChild(script);
    }
  });
}

async function api<T>(token: string, path: string, body: unknown): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    method: "POST",
    headers: { ...getHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
  return data as T;
}

/** Opens Razorpay Checkout for `plan`. Resolves with the updated account once the server has verified the payment. */
export async function startCheckout(token: string, plan: "plus" | "pro"): Promise<Account> {
  const order = await api<{
    order_id: string;
    amount: number;
    currency: string;
    key_id: string;
    plan_label: string;
    email: string | null;
    test_mode?: boolean;
  }>(token, "/api/billing/order", { plan });

  await loadRazorpay().catch(() => {});

  const useNativeRazorpay = typeof window !== "undefined" && window.Razorpay && !order.key_id.endsWith("_sandbox");

  if (useNativeRazorpay) {
    return new Promise<Account>((resolve, reject) => {
      const rzp = new window.Razorpay!({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "ENO",
        description: `ENO ${order.plan_label} plan`,
        prefill: { email: order.email || undefined },
        theme: { color: "#4f46e5" },
        handler: async (resp) => {
          try {
            await api(token, "/api/billing/verify", resp);
            const me = await fetch(`${getApiUrl()}/api/me`, { headers: getHeaders(token) });
            resolve((await me.json()) as Account);
          } catch (e) {
            reject(e);
          }
        },
        modal: { ondismiss: () => reject(new CheckoutCancelled("Checkout closed")) },
      });
      rzp.on("payment.failed", () => reject(new Error("Payment failed. No money was taken in test mode.")));
      rzp.open();
    });
  }

  // Sandbox Test Checkout Modal Simulation
  return new Promise<Account>((resolve, reject) => {
    const overlay = document.createElement("div");
    overlay.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200";
    overlay.innerHTML = `
      <div class="w-full max-w-sm bg-zinc-900 border border-indigo-500/30 rounded-2xl p-6 shadow-2xl text-white space-y-4">
        <div class="flex items-center justify-between border-b border-white/10 pb-3">
          <div class="flex items-center gap-2">
            <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-xs font-bold text-white shadow-md shadow-indigo-600/30">R</div>
            <h3 class="font-semibold text-sm">Razorpay Checkout</h3>
          </div>
          <span class="text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full uppercase tracking-wider">Test Mode</span>
        </div>
        <div>
          <div class="text-xs text-zinc-400">Order ID: <span class="font-mono text-zinc-300">${order.order_id}</span></div>
          <div class="text-lg font-bold text-indigo-400 mt-1">${order.plan_label} Plan</div>
          <div class="text-2xl font-extrabold text-white mt-0.5">₹${(order.amount / 100).toFixed(0)} <span class="text-xs font-normal text-zinc-400">/ month</span></div>
        </div>
        <div class="bg-zinc-800/80 rounded-xl p-3 text-xs text-zinc-300 space-y-1.5 border border-white/5">
          <div class="flex justify-between"><span class="text-zinc-500">Test Card:</span> <span class="font-mono text-zinc-200">4111 •••• •••• 1111</span></div>
          <div class="flex justify-between"><span class="text-zinc-500">Test UPI:</span> <span class="font-mono text-zinc-200">success@razorpay</span></div>
          <div class="flex justify-between"><span class="text-zinc-500">Sandbox:</span> <span class="text-emerald-400 font-medium">Safe Test Environment</span></div>
        </div>
        <div class="flex gap-2 pt-2">
          <button id="rzp-cancel-btn" class="flex-1 py-2.5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 text-xs font-medium text-zinc-300 transition-colors">
            Cancel
          </button>
          <button id="rzp-pay-btn" class="flex-1 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-xs font-medium text-white transition-colors shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-1.5">
            Simulate Pay ₹${(order.amount / 100).toFixed(0)}
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const cleanup = () => {
      if (document.body.contains(overlay)) document.body.removeChild(overlay);
    };

    overlay.querySelector("#rzp-cancel-btn")?.addEventListener("click", () => {
      cleanup();
      reject(new CheckoutCancelled("Checkout closed"));
    });

    overlay.querySelector("#rzp-pay-btn")?.addEventListener("click", async () => {
      const payBtn = overlay.querySelector("#rzp-pay-btn") as HTMLButtonElement;
      if (payBtn) {
        payBtn.disabled = true;
        payBtn.innerText = "Verifying...";
      }
      try {
        const testPaymentId = `pay_test_${Date.now()}`;
        const resp = {
          razorpay_order_id: order.order_id,
          razorpay_payment_id: testPaymentId,
          razorpay_signature: "test_signature"
        };
        await api(token, "/api/billing/verify", resp);
        const me = await fetch(`${getApiUrl()}/api/me`, { headers: getHeaders(token) });
        cleanup();
        resolve((await me.json()) as Account);
      } catch (err) {
        cleanup();
        reject(err instanceof Error ? err : new Error("Payment verification failed"));
      }
    });
  });
}

export async function resetPlanForDemo(token: string): Promise<Account> {
  await api(token, "/api/billing/reset", {});
  const me = await fetch(`${getApiUrl()}/api/me`, { headers: getHeaders(token) });
  return (await me.json()) as Account;
}
