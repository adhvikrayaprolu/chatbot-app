// Per-browser UI preferences only; conversations and documents live on the server.
export function remember(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode or blocked storage: preferences simply reset */
  }
}

export function recall(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
