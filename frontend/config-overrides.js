const webpack = require('webpack');
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = function override(config, env) {
    // Completely disable react-refresh in development to fix runtime errors
    if (env === 'development') {
        // Remove any existing react-refresh plugins
        config.plugins = config.plugins.filter(plugin => {
            const name = plugin.constructor.name;
            return name !== 'ReactRefreshPlugin' && name !== 'ReactRefreshWebpackPlugin';
        });
        
        // Find and modify babel-loader to remove react-refresh
        const oneOfRules = config.module.rules.find(rule => rule.oneOf);
        if (oneOfRules) {
            oneOfRules.oneOf.forEach(rule => {
                if (rule.test && (rule.test.toString().includes('jsx') || rule.test.toString().includes('tsx'))) {
                    if (rule.use && Array.isArray(rule.use)) {
                        rule.use.forEach(loader => {
                            if (loader.loader && loader.loader.includes('babel-loader')) {
                                if (loader.options && loader.options.plugins) {
                                    loader.options.plugins = loader.options.plugins.filter(plugin => {
                                        if (typeof plugin === 'string') {
                                            return !plugin.includes('react-refresh');
                                        }
                                        if (Array.isArray(plugin)) {
                                            return !plugin[0].includes('react-refresh');
                                        }
                                        return true;
                                    });
                                }
                            }
                        });
                    }
                }
            });
        }
        
        // Disable fast refresh completely
        config.resolve.alias = {
            ...config.resolve.alias,
            'react-refresh/runtime': false
        };
    }

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
                            drop_console: false,
                        },
                    },
                }),
            ],
        };
    }

    return config;
}