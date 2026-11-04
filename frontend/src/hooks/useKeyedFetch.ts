import { useEffect, useState } from "react";

export type FetchState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string };

/**
 * Loads data whenever `key` changes, ignoring responses that arrive after the
 * key has moved on. A null key means "nothing to load yet".
 */
export function useKeyedFetch<T>(
  key: string | null,
  fetcher: () => Promise<T>,
): FetchState<T> {
  const [settled, setSettled] = useState<{ key: string; state: FetchState<T> } | null>(
    null,
  );

  useEffect(() => {
    if (key === null) return;
    let active = true;
    fetcher()
      .then((data) => {
        if (active) setSettled({ key, state: { status: "ready", data } });
      })
      .catch((error: unknown) => {
        if (active) {
          setSettled({
            key,
            state: {
              status: "error",
              message: error instanceof Error ? error.message : "Request failed.",
            },
          });
        }
      });
    return () => {
      active = false;
    };
    // The key encodes every input the fetcher reads, so the fetcher is
    // deliberately excluded from the dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (key === null) return { status: "idle" };
  if (settled === null || settled.key !== key) return { status: "loading" };
  return settled.state;
}
