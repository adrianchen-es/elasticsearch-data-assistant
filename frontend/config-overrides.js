const webpack = require('webpack');
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = function override(config, env) {
    // config.resolve.fallback = {
    //     child_process: false,
    //     fs: false,
    //     path: false,
    //     net: false,
    //     tls: false,
    //     dns: false,
    //     http2: false,
    //     os: false,
    //     zlib: false,
    //     events: false,
    //     timers: require.resolve('timers-browserify'),
    //     console: false,
    //     domain: false,
    //     async_hooks: false,
    //     diagnostics_channel: false,
    //     crypto: false,
    //     querystring: require.resolve("querystring-es3"),
    //     url: require.resolve('url/'),
    //     assert: require.resolve('assert'),
    //     http: require.resolve('stream-http'),
    //     https: require.resolve('https-browserify'),
    //     buffer: require.resolve('buffer'),
    //     stream: require.resolve('stream-browserify'),
    // };
    // config.plugins.push(
    //     new CompressionPlugin()
    // );

    // Add cache configuration
    config.cache = {
        type: 'filesystem',
        buildDependencies: {
            config: [__filename],
        },
    };

    if (env === 'production') {
        config.plugins.push(new CompressionPlugin());
    }

    return config;
}