import { createContext, useContext } from "react";
import { copyFor, type Copy } from "./copy";

export const CopyContext = createContext<Copy>(copyFor("en"));

/** Frontend chrome text for the current locale. */
export function useCopy(): Copy {
  return useContext(CopyContext);
}
