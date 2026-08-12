import "@testing-library/jest-dom/vitest";

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();

  return {
    get length() {
      return values.size;
    },

    clear() {
      values.clear();
    },

    getItem(key: string) {
      return values.get(String(key)) ?? null;
    },

    key(index: number) {
      return Array.from(values.keys())[index] ?? null;
    },

    removeItem(key: string) {
      values.delete(String(key));
    },

    setItem(key: string, value: string) {
      values.set(String(key), String(value));
    },
  };
}

const testLocalStorage = createMemoryStorage();

Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: testLocalStorage,
});

Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: testLocalStorage,
});
