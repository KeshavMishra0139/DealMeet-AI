// Firebase Auth (Google and phone OTP) in the browser. Used only when its web config
// is present in .env; the SDK is loaded lazily, so pages without it never download it.
//
// Firebase proves who you are; the server checks the ID token (POST /api/auth/firebase)
// and gives the app its own session. After that exchange the Firebase session in the
// browser is signed out, so there's only one session to think about.
import type { ConfirmationResult } from "firebase/auth";

const env = import.meta.env;

const config = {
  apiKey: env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  appId: env.VITE_FIREBASE_APP_ID as string | undefined,
};

export const firebaseEnabled = Boolean(config.apiKey && config.projectId && config.appId);

async function load() {
  const [{ initializeApp, getApps }, auth] = await Promise.all([import("firebase/app"), import("firebase/auth")]);
  const app = getApps()[0] ?? initializeApp(config);
  return { auth, instance: auth.getAuth(app) };
}

const CANCELLED = new Set(["auth/popup-closed-by-user", "auth/cancelled-popup-request", "auth/user-cancelled"]);

/** Turns Firebase errors into plain sentences. Returns null for a cancelled popup. */
export function firebaseMessage(e: unknown): string | null {
  const code = (e as { code?: string })?.code ?? "";
  if (CANCELLED.has(code)) return null;
  if (code === "auth/popup-blocked") return "Your browser blocked the sign-in window. Allow pop-ups for this site and try again.";
  if (code === "auth/invalid-phone-number") return "That phone number doesn't look right. Include the country code, like +91 98765 43210.";
  if (code === "auth/invalid-verification-code") return "That code isn't right. Check the SMS and try again.";
  if (code === "auth/code-expired") return "That code expired. Send a new one.";
  if (code === "auth/too-many-requests") return "Too many tries. Wait a few minutes and try again.";
  if (code === "auth/unauthorized-domain") return "This website isn't on Firebase's list of authorised domains yet.";
  return e instanceof Error ? e.message : "Sign-in didn't work. Try again.";
}

/** Google sign-in in a popup. Resolves to a Firebase ID token for the server to verify. */
export async function googleIdToken(): Promise<string> {
  const { auth, instance } = await load();
  const result = await auth.signInWithPopup(instance, new auth.GoogleAuthProvider());
  return result.user.getIdToken();
}

/** Sends an SMS code. `containerId` is an element for the invisible reCAPTCHA. */
export async function sendPhoneCode(phone: string, containerId: string): Promise<ConfirmationResult> {
  const { auth, instance } = await load();
  const verifier = new auth.RecaptchaVerifier(instance, containerId, { size: "invisible" });
  return auth.signInWithPhoneNumber(instance, phone, verifier);
}

export async function confirmPhoneCode(confirmation: ConfirmationResult, code: string): Promise<string> {
  const result = await confirmation.confirm(code);
  return result.user.getIdToken();
}

export async function signOutFirebase() {
  if (!firebaseEnabled) return;
  try {
    const { auth, instance } = await load();
    await auth.signOut(instance);
  } catch {
    /* the app session is what matters */
  }
}
