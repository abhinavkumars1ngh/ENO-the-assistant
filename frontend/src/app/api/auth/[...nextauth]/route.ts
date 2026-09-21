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
          const res = await fetch("http://127.0.0.1:8000/api/login", {
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
              return { id: user.user_id, name: credentials.username, apiToken: user.access_token, role: user.role };
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
      }
      // If user logged in with Google, we need to sync them with FastAPI
      if (account?.provider === "google" && user?.email) {
        try {
          const res = await fetch("http://127.0.0.1:8000/api/auth/sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: user.email })
          });
          if (res.ok) {
            const data = await res.json();
            token.apiToken = data.access_token;
            token.role = data.role;
          }
        } catch (e) {
          console.error("Google sync error:", e);
        }
      }
      return token;
    },
    async session({ session, token }) {
      session.apiToken = token.apiToken as string;
      if (session.user) session.user.role = token.role as string;
      return session;
    }
  },
  session: {
    strategy: "jwt",
  },
  pages: {
    signIn: '/login',
  }
})

export { handler as GET, handler as POST }
