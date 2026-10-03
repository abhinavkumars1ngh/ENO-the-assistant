"use client";

import { useEffect, useState } from "react";
import { Check, Crown, Loader2, Zap } from "lucide-react";
import { fetchPlans, formatPrice, type Account, type PlanInfo } from "@/lib/api";
import { CheckoutCancelled, resetPlanForDemo, startCheckout } from "@/lib/billing";

const RANK = { free: 0, plus: 1, pro: 2 } as const;

function features(p: PlanInfo): string[] {
  return [
    p.daily_messages === null ? "Unlimited messages" : `${p.daily_messages} messages / day`,
    p.models.includes("bro") ? "Standard + Bro (bigger Qwen model)" : "Standard (Gemma) model",
    p.voice ? "Voice chat" : "Text chat only",
    "Chats stored on your device",
    "Encrypted vault export / import",
  ];
}

export default function PlanCards({
  token,
  account,
  onAccountChange,
  highlight,
}: {
  token: string;
  account: Account | null;
  onAccountChange: (a: Account) => void;
  highlight?: "plus" | "pro";
}) {
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [razorpay, setRazorpay] = useState(false);
  const [testMode, setTestMode] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    fetchPlans().then((r) => {
      if (!r) return;
      setPlans(r.plans);
      setRazorpay(r.razorpay_enabled);
      setTestMode(r.test_mode);
    });
  }, []);

  const current = account?.plan ?? "free";

  async function upgrade(plan: "plus" | "pro") {
    setMsg(null);
    setBusy(plan);
    try {
      const updated = await startCheckout(token, plan);
      onAccountChange(updated);
      setMsg({ kind: "ok", text: `You're now on ${updated.plan_label}. Unlocked instantly.` });
    } catch (e) {
      if (!(e instanceof CheckoutCancelled)) setMsg({ kind: "err", text: e instanceof Error ? e.message : "Checkout failed" });
    } finally {
      setBusy(null);
    }
  }

  async function reset() {
    setMsg(null);
    setBusy("reset");
    try {
      onAccountChange(await resetPlanForDemo(token));
      setMsg({ kind: "ok", text: "Back on Free (demo reset)." });
    } catch (e) {
      setMsg({ kind: "err", text: e instanceof Error ? e.message : "Reset failed" });
    } finally {
      setBusy(null);
    }
  }

  if (plans.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-zinc-500 text-sm gap-2">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading plans...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {testMode && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200 leading-relaxed">
          <b>Test mode:</b> no real money moves. Use card <span className="font-mono">4111 1111 1111 1111</span>, any future
          expiry and any CVV, or UPI <span className="font-mono">success@razorpay</span>.
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        {plans.map((p) => {
          const isCurrent = p.id === current;
          const canBuy = RANK[p.id] > RANK[current];
          const featured = p.id === (highlight ?? "plus");
          return (
            <div
              key={p.id}
              className={`relative flex flex-col rounded-2xl border p-5 ${
                isCurrent ? "border-emerald-500/50 bg-emerald-500/5" : featured ? "border-indigo-500/50 bg-indigo-500/5" : "border-white/10 bg-zinc-900/60"
              }`}
            >
              {isCurrent && (
                <span className="absolute -top-2.5 left-4 rounded-full bg-emerald-500 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-black">
                  Current plan
                </span>
              )}
              <div className="flex items-center gap-2 text-white font-semibold">
                {p.id === "pro" ? <Crown className="w-4 h-4 text-amber-400" /> : p.id === "plus" ? <Zap className="w-4 h-4 text-indigo-400" /> : null}
                {p.label}
              </div>
              <div className="mt-1 text-2xl font-bold text-white">
                {formatPrice(p.price_paise, p.currency)}
                {p.price_paise > 0 && <span className="text-xs font-normal text-zinc-500"> / month</span>}
              </div>
              <div className="text-xs text-zinc-500">{p.tagline}</div>

              <ul className="mt-4 space-y-2 text-sm text-zinc-300 flex-1">
                {features(p).map((f) => (
                  <li key={f} className="flex gap-2">
                    <Check className="w-4 h-4 mt-0.5 shrink-0 text-emerald-400" />
                    {f}
                  </li>
                ))}
              </ul>

              <button
                disabled={!canBuy || !razorpay || busy !== null}
                onClick={() => p.id !== "free" && upgrade(p.id)}
                className="mt-5 w-full rounded-xl bg-indigo-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:bg-zinc-800 disabled:text-zinc-500 flex items-center justify-center gap-2"
              >
                {busy === p.id && <Loader2 className="w-4 h-4 animate-spin" />}
                {isCurrent ? "Your plan" : canBuy ? `Upgrade to ${p.label}` : "Included"}
              </button>
            </div>
          );
        })}
      </div>

      {!razorpay && <p className="text-xs text-zinc-500">Checkout isn&apos;t configured on this server yet.</p>}
      {msg && (
        <div className={`rounded-lg px-3 py-2 text-sm ${msg.kind === "ok" ? "bg-emerald-500/10 text-emerald-300" : "bg-red-500/10 text-red-300"}`}>{msg.text}</div>
      )}
      {testMode && current !== "free" && (
        <button onClick={reset} disabled={busy !== null} className="text-xs text-zinc-500 underline hover:text-zinc-300">
          Reset my account to Free (demo only)
        </button>
      )}
    </div>
  );
}
