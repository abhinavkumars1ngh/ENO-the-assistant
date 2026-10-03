import NextAuth, { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    apiToken?: string
    /** True when Google sign-in worked but the ENO backend could not be reached / rejected the login. */
    syncError?: boolean
    user: {
      id: string
      role?: string
      /** Opaque, stable account ID. Namespaces the on-device chat vault. */
      uid?: string
    } & DefaultSession["user"]
  }

  interface User {
    apiToken?: string
    role?: string
    uid?: string
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    apiToken?: string
    role?: string
    uid?: string
    syncError?: boolean
  }
}
