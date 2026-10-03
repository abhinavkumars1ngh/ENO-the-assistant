import NextAuth from "next-auth"
import GoogleProvider from "next-auth/providers/google"
import CredentialsProvider from "next-auth/providers/credentials"

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
      authorization: {
        params: {
          prompt: "select_account"
        }
      }
    }),
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        username: { label: "Username", type: "text", placeholder: "admin" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials, req) {
        if (!credentials?.username || !credentials?.password) return null;

        try {
          const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
          const res = await fetch(`${API_URL}/api/login`, {
            method: "POST",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
              username: credentials.username,
              password: credentials.password,
            }),
          });
          
          if (res.ok) {
            const user = await res.json();
            if (user && user.access_token) {
              return { id: user.user_id, name: credentials.username, apiToken: user.access_token, role: user.role, uid: user.uid };
            }
          }
          return null;
        } catch (e) {
          console.error("Auth error:", e);
          return null;
        }
      }
    })
  ],
  callbacks: {
    async jwt({ token, user, account }) {
      // If user logged in with Credentials
      if (user?.apiToken) {
        token.apiToken = user.apiToken;
        token.role = user.role;
        token.uid = user.uid;
      }
      // If user logged in with Google, we need to sync them with FastAPI.
      // We hand the backend Google's signed ID token (not a bare email) so it can verify who we are.
      if (account?.provider === "google" && account.id_token) {
        try {
          const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
          const res = await fetch(`${API_URL}/api/auth/sync`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: account.id_token })
          });
          if (res.ok) {
            const data = await res.json();
            token.apiToken = data.access_token;
            token.role = data.role;
            token.uid = data.uid;
            token.syncError = false;
          } else {
            console.error("Google sync rejected by backend:", res.status);
            token.syncError = true;
          }
        } catch (e) {
          console.error("Google sync error:", e);
          token.syncError = true;
        }
      }
      return token;
    },
    async session({ session, token }) {
      session.apiToken = token.apiToken as string;
      session.syncError = Boolean(token.syncError);
      if (session.user) {
        session.user.role = token.role as string;
        session.user.uid = token.uid as string;
      }
      return session;
    }
  },
  session: {
    strategy: "jwt",
    // Match the backend access-token lifetime (7 days) so the UI never holds an expired API token.
    maxAge: 60 * 60 * 24 * 7,
  },
  pages: {
    signIn: '/login',
  }
})

export { handler as GET, handler as POST }
