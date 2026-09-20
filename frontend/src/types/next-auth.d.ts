import NextAuth, { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    apiToken?: string
    user: {
      id: string
      role?: string
    } & DefaultSession["user"]
  }

  interface User {
    apiToken?: string
    role?: string
  }
}
