// filepath: /workspaces/elasticsearch-data-assistant/frontend/webpack.config.js
const webpack = require('webpack');

module.exports = {
  // ...existing config...
  resolve: {
    fallback: {
      "buffer": require.resolve("buffer/"),
      "stream": require.resolve("stream-browserify"),
      "crypto": require.resolve("crypto-browserify"),
      "assert": require.resolve("assert/"),
      "util": require.resolve("util/"),
      "process": require.resolve("process/browser"),
      "path": require.resolve("path-browserify"),
      "http": require.resolve("stream-http"),
    }
  },
  plugins: [
    new webpack.ProvidePlugin({
      Buffer: ['buffer', 'Buffer'],
      process: 'process/browser',
    }),
  ],
};