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

const YOUTUBE_READONLY = "https://www.googleapis.com/auth/youtube.readonly";
const YOUTUBE_SCOPES = [YOUTUBE_READONLY, "https://www.googleapis.com/auth/yt-analytics.readonly"];

/**
 * "Continue with YouTube" (creators): a Google sign-in that also asks for read-only YouTube
 * access, so the server can see which channel this Google account owns. Returns the ID token
 * (who you are) and the access token, which the server uses once and never keeps.
 */
export async function youtubeSignIn(): Promise<{ idToken: string; accessToken: string }> {
  const { auth, instance } = await load();
  const provider = new auth.GoogleAuthProvider();
  provider.addScope(YOUTUBE_READONLY);
  provider.setCustomParameters({ prompt: "select_account" });
  const result = await auth.signInWithPopup(instance, provider);
  const accessToken = auth.GoogleAuthProvider.credentialFromResult(result)?.accessToken;
  if (!accessToken) {
    await auth.signOut(instance);
    throw new Error("Google didn't return YouTube access. Try again and allow DealMeet to see your YouTube account.");
  }
  return { idToken: await result.user.getIdToken(), accessToken };
}

/**
 * Asks Google for read-only YouTube access, only when a creator clicks "Connect YouTube
 * Analytics" (ordinary sign-in never asks, so brands are never asked). Returns the
 * access token for the server to use once; it isn't kept anywhere.
 */
export async function youtubeAnalyticsToken(): Promise<string> {
  const { auth, instance } = await load();
  const provider = new auth.GoogleAuthProvider();
  YOUTUBE_SCOPES.forEach((s) => provider.addScope(s));
  provider.setCustomParameters({ prompt: "consent" });
  const result = await auth.signInWithPopup(instance, provider);
  const token = auth.GoogleAuthProvider.credentialFromResult(result)?.accessToken;
  await auth.signOut(instance);
  if (!token) throw new Error("Google didn't return YouTube access. Try again and allow both YouTube permissions.");
  return token;
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
