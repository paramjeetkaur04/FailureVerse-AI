import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

class ResizeObserverStub {
  observe() { /* jsdom has no layout engine. Real layout is checked in the browser. */ }
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;
