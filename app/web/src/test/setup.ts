import "@testing-library/jest-dom";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const ResizeObserver = ResizeObserverMock as unknown as typeof globalThis.ResizeObserver;
globalThis.ResizeObserver = ResizeObserver;
window.ResizeObserver = ResizeObserver;

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}

const IntersectionObserver = IntersectionObserverMock as unknown as typeof globalThis.IntersectionObserver;
globalThis.IntersectionObserver = IntersectionObserver;
window.IntersectionObserver = IntersectionObserver;

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});
