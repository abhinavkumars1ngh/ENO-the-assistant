"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { ArrowLeft } from "lucide-react";
import PlanCards from "@/components/PlanCards";
import { fetchAccount, type Account } from "@/lib/api";

export default function PricingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [account, setAccount] = useState<Account | null>(null);
  const token = session?.apiToken || "";

  useEffect(() => {
    if (status === "unauthenticated") router.replace("/login");
  }, [status, router]);

  useEffect(() => {
    if (token) fetchAccount(token).then(setAccount);
  }, [token]);

  return (
    <main className="min-h-dvh bg-black px-4 py-8 text-white">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => router.push("/")} className="mb-6 flex items-center gap-2 text-sm text-zinc-400 hover:text-white">
          <ArrowLeft className="h-4 w-4" /> Back to chat
        </button>
        <h1 className="text-3xl font-bold">Plans</h1>
        <p className="mt-2 mb-8 text-sm text-zinc-400">
          Every plan keeps your chats on your own device. Upgrading unlocks the bigger model, voice and higher limits.
          {account && (
            <>
              {" "}
              You&apos;re on <b className="text-zinc-200">{account.plan_label}</b>
              {account.daily_limit !== null && ` (${account.used_today}/${account.daily_limit} messages used today)`}.
            </>
          )}
        </p>
        {token ? (
          <PlanCards token={token} account={account} onAccountChange={setAccount} />
        ) : (
          <p className="text-sm text-zinc-500">Loading...</p>
        )}
      </div>
    </main>
  );
}
