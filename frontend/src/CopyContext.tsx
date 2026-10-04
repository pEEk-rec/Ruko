import { createContext, useContext } from "react";
import { copyFor, type Copy } from "./copy";
import type { Locale } from "./types/api";

export const CopyContext = createContext<Copy>(copyFor("en"));
export const LocaleContext = createContext<Locale>("en");

/** Frontend chrome text for the current locale. */
export function useCopy(): Copy {
  return useContext(CopyContext);
}

/** The language the app is currently shown (and spoken) in. */
export function useLocale(): Locale {
  return useContext(LocaleContext);
}
