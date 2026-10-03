import re

with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# We need to add a login modal when status === "unauthenticated"
# Right now, it redirects:
old_redirect = """  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login");
    }
  }, [status, router]);"""

new_redirect = """  // Redirect removed: we render an overlay instead
  
  // Login form state
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  
  const handleCredentialsLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    const res = await signIn("credentials", {
      username: loginUsername,
      password: loginPassword,
      redirect: false
    });
    if (res?.error) {
      setLoginError("Invalid username or password");
    }
  };"""

content = content.replace(old_redirect, new_redirect)

# We need to render the login modal at the bottom of the return statement
old_return = "  return (\n    <div className"
new_return = """  return (
    <>
      {status === "unauthenticated" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/80 backdrop-blur-sm px-4 sm:px-6 lg:px-8">
          <div className="max-w-md w-full space-y-8 bg-gray-900 p-10 rounded-2xl border border-gray-800 shadow-2xl relative">
            <div>
              <h2 className="mt-2 text-center text-3xl font-extrabold text-white">
                Welcome to Eno
              </h2>
              <p className="mt-2 text-center text-sm text-gray-400">
                Sign in to access your offline intelligence
              </p>
            </div>
            
            {loginError && (
              <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg text-sm text-center">
                {loginError}
              </div>
            )}

            <form className="mt-8 space-y-6" onSubmit={handleCredentialsLogin}>
              <div className="space-y-4 rounded-md shadow-sm">
                <div>
                  <input
                    name="username"
                    type="text"
                    required
                    value={loginUsername}
                    onChange={(e) => setLoginUsername(e.target.value)}
                    className="appearance-none rounded-xl relative block w-full px-4 py-3 border border-gray-700 bg-gray-800 placeholder-gray-500 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent sm:text-sm transition-colors"
                    placeholder="Username (e.g. admin)"
                  />
                </div>
                <div>
                  <input
                    name="password"
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    className="appearance-none rounded-xl relative block w-full px-4 py-3 border border-gray-700 bg-gray-800 placeholder-gray-500 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent sm:text-sm transition-colors"
                    placeholder="Password"
                  />
                </div>
              </div>

              <div>
                <button
                  type="submit"
                  className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-xl text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors shadow-lg shadow-blue-900/20"
                >
                  Sign in with Credentials
                </button>
              </div>
            </form>

            <div className="mt-6">
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-700" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-gray-900 text-gray-400">Or continue with</span>
                </div>
              </div>

              <div className="mt-6">
                <button
                  onClick={() => signIn("google", { callbackUrl: "/" })}
                  className="w-full flex items-center justify-center px-4 py-3 border border-gray-700 rounded-xl shadow-sm text-sm font-medium text-white bg-gray-800 hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition-colors"
                >
                  <svg className="h-5 w-5 mr-2" viewBox="0 0 24 24">
                    <path
                      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      fill="#4285F4"
                    />
                    <path
                      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      fill="#34A853"
                    />
                    <path
                      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                      fill="#FBBC05"
                    />
                    <path
                      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                      fill="#EA4335"
                    />
                  </svg>
                  Sign in with Google
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    <div className"""

content = content.replace(old_return, new_return)

# Add signIn to imports
if "signIn" not in content:
    content = content.replace('import { signOut } from "next-auth/react";', 'import { signOut, signIn } from "next-auth/react";')

# Close the trailing tag
content += "\n    </>\n  );\n}\n"
# Actually the file already had closing tags, we just wrapped the main div in <>
# Wait! Let's check how the file ends before modifying it randomly.
