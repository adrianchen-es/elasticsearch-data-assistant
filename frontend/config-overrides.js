const webpack = require('webpack');
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = function override(config, env) {
    config.resolve.fallback = {
        fs: false,
        path: false,
        net: false,
        tls: false,
        dns: false,
        http2: false,
        zlib: require.resolve('browserify-zlib'),
        timers: require.resolve('timers-browserify'),
        console: require.resolve('console-browserify'),
        domain: false,
        async_hooks: false,
        diagnostics_channel: false,
        querystring: require.resolve("querystring-es3"),
        url: require.resolve('url/'),
        assert: require.resolve('assert'),
        crypto: require.resolve('crypto-browserify'),
        http: require.resolve('stream-http'),
        https: require.resolve('https-browserify'),
        buffer: require.resolve('buffer'),
        stream: require.resolve('stream-browserify'),
    };
    config.plugins.push(
        new webpack.ProvidePlugin({
            process: 'process/browser',
            Buffer: ['buffer', 'Buffer'],
        }),
    );

    // Add cache configuration
    config.cache = {
        type: 'filesystem',
        buildDependencies: {
            config: [__filename],
        },
    };

    if (env === 'production') {
        config.plugins.push(new CompressionPlugin());
        config.optimization = {
            minimize: true,
            minimizer: [
                new TerserPlugin({
                    parallel: true,
                    terserOptions: {
                        compress: {
                            drop_console: true,
                        },
                    },
                }),
            ],
        };
    }

    return config;
}