import { API_URL, getHeaders, type Account } from "./api";

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
  const res = await fetch(`${API_URL}${path}`, {
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
  }>(token, "/api/billing/order", { plan });

  await loadRazorpay();

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
          // The plan only changes after the server verifies Razorpay's signature.
          await api(token, "/api/billing/verify", resp);
          const me = await fetch(`${API_URL}/api/me`, { headers: getHeaders(token) });
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

export async function resetPlanForDemo(token: string): Promise<Account> {
  await api(token, "/api/billing/reset", {});
  const me = await fetch(`${API_URL}/api/me`, { headers: getHeaders(token) });
  return (await me.json()) as Account;
}
