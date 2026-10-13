import { useCreator } from "./CreatorShell";

/** The creator's own words for posts and audience: videos and subscribers on YouTube,
 * reels and followers on Instagram (from the server's terms on the creator view). */
export function useTerms() {
  const terms = useCreator().data?.terms;
  return {
    youtube: terms?.platform === "youtube",
    post: terms?.post ?? "reel",
    posts: terms?.posts ?? "reels",
    audience: terms?.audience ?? "followers",
  };
}
