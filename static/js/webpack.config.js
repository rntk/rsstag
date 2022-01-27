var path = require('path');
var webpack = require('webpack');

var plugins = [
    new webpack.EnvironmentPlugin(['NODE_ENV'])
];

if (process.env.NODE_ENV === 'production') {
    plugins = plugins.concat([
        /*new webpack.optimize.UglifyJsPlugin({
            compress: {
                warnings: false
            }
        })*/
    ]);
}

module.exports = {
    devtool: 'cheap-module-source-map',
    entry: path.join(__dirname, 'apps', 'app.js'),
    module: {
        rules: [
            {
                test: /\.js/,
                include: path.join(__dirname, 'components'),
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ["@babel/preset-react", '@babel/preset-env']
                    }
                }
            },
            {
                test: /\.js/,
                include: [path.join(__dirname, 'storages'), path.join(__dirname, 'libs')],
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env']
                    }
                }
            },
            {
                test: /app.js/,
                include: path.join(__dirname, 'apps'),
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-react', '@babel/preset-env'],
                    }
                }
            }
        ]
    },
    plugins: plugins,
    output: {
        path: __dirname,
        filename: 'bundle.js',
        publicPath: '/static/js'
    },
}
