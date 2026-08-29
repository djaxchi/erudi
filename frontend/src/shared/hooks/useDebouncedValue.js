import { useEffect, useState } from "react";

/**
 * Trail `value` by `delayMs`: the returned value only updates once the input
 * has been stable for that long. Used to run the catalog search a beat after
 * the last keystroke (#380) instead of on every one.
 */
export default function useDebouncedValue(value, delayMs = 150) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debounced;
}
