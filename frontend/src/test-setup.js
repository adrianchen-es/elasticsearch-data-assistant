// Test setup file for Vitest and React Testing Library
import '@testing-library/jest-dom';

// Mock window.matchMedia

// Mock IntersectionObserver
// Ensure React testing environment is set so React's testing utilities avoid act(...) warnings
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});
global.IntersectionObserver = class IntersectionObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
};
