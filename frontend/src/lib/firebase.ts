// Firebase Auth is used only when its web config is present in .env.
// Without it the app shows the demo role picker and never loads Firebase.
const env = import.meta.env;

const config = {
  apiKey: env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  appId: env.VITE_FIREBASE_APP_ID as string | undefined,
};

export const firebaseEnabled = Boolean(config.apiKey && config.projectId && config.appId);

/** Returns the signed-in display name, or null if sign-in failed or was cancelled. */
export async function signInWithGoogle(): Promise<string | null> {
  if (!firebaseEnabled) return null;
  try {
    const [{ initializeApp, getApps }, auth] = await Promise.all([import("firebase/app"), import("firebase/auth")]);
    const app = getApps()[0] ?? initializeApp(config);
    const result = await auth.signInWithPopup(auth.getAuth(app), new auth.GoogleAuthProvider());
    return result.user.displayName ?? result.user.email ?? "your account";
  } catch {
    return null;
  }
}
