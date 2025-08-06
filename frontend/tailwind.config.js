/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
  resolve: {
    fallback: {
      "util": require.resolve("util/"),
      "path": require.resolve("path-browserify"),
      "http": require.resolve("stream-http",
    }
  },
}