var path = require('path');
var webpack = require('webpack');

module.exports = {
    devtool: 'cheap-module-source-map',
    entry: path.join(__dirname, 'apps', 'app.js'),
    plugins: [
        new webpack.DefinePlugin({
            'process.env': { 
                NODE_ENV: JSON.stringify(process.env.NODE_ENV)
            }
        })
    ],
    module: {
        loaders: [
            {
                test: /\.js/,
                loader: 'babel-loader',
                include: path.join(__dirname, 'components'),
                query: {
                    presets: ['react', 'es2015']
                }
            },
            {
                test: /\.js/,
                loader: 'babel-loader',
                include: [path.join(__dirname, 'storages'), path.join(__dirname, 'libs')],
                query: {
                    presets: ['es2015']
                }
            },
            {
                test: /app.js/,
                loader: 'babel-loader',
                include: path.join(__dirname, 'apps'),
                query: {
                    presets: ['es2015', 'react']
                }
            },
        ]
    },
    output: {
        path: __dirname,
        filename: 'bundle.js',
        publicPath: '/static/js'
    },
}