// Test setup file for Vitest and React Testing Library
import '@testing-library/jest-dom';

// Shim React testing utilities to reduce deprecation warnings.
// Some tests and third-party libs import act from 'react-dom/test-utils'
// which is deprecated; map it to React.act when possible and set the
// IS_REACT_ACT_ENVIRONMENT flag so React knows tests support act().
import * as React from 'react';
try {
  // eslint-disable-next-line global-require, import/no-extraneous-dependencies
  const ReactDOMTestUtils = require('react-dom/test-utils');
  if (React && React.act && ReactDOMTestUtils && ReactDOMTestUtils.act !== React.act) {
    ReactDOMTestUtils.act = React.act;
  }
} catch (e) {
  // If require fails in some environments, ignore — the flag below still helps.
}

// Signal to React testing runtime that act() support exists.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Mock window.matchMedia
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
