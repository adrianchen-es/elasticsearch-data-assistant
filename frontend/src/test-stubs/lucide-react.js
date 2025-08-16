import React from 'react';

// Minimal SVG icon stub for tests. Exports named icon components used by the app.
const Icon = (props) => React.createElement('svg', { 'data-test-icon': true, ...props });

export const Database = Icon;
export const Cpu = Icon;
export const RefreshCw = Icon;
export const Layers = Icon;

export default {};
