const path = require('path');
const webpack = require('webpack');
const fs = require('fs');
const sass = require('sass');

// Compile SASS to CSS
const cssDir = path.resolve(__dirname, '..', 'css');
const scssPath = path.join(cssDir, 'style.scss');
const cssPath = path.join(cssDir, 'style.css');

try {
    if (fs.existsSync(scssPath)) {
        const result = sass.compile(scssPath);
        fs.writeFileSync(cssPath, result.css);
        console.log('✓ SASS compiled successfully');
    } else {
        console.warn('⚠ SASS file not found, skipping compilation');
    }
} catch (error) {
    console.error('✗ SASS compilation failed:', error.message);
}

const isProduction = process.env.NODE_ENV === 'production';

module.exports = {
    mode: isProduction ? 'production' : 'development',
    devtool: isProduction ? 'source-map' : 'eval-source-map',
    entry: path.join(__dirname, 'apps', 'app.js'),
    module: {
        rules: [
            {
                test: /\.js$/,
                include: [
                    path.join(__dirname, 'apps'),
                    path.join(__dirname, 'components'),
                    path.join(__dirname, 'storages'),
                    path.join(__dirname, 'libs')
                ],
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: [
                            '@babel/preset-react',
                            ['@babel/preset-env', {
                                targets: '> 0.25%, not dead',
                                useBuiltIns: 'usage',
                                corejs: 3
                            }]
                        ],
                        cacheDirectory: true
                    }
                }
            }
        ]
    },
    plugins: [
        new webpack.EnvironmentPlugin({
            NODE_ENV: 'development'
        })
    ],
    output: {
        path: __dirname,
        filename: 'bundle.js',
        publicPath: '/static/js/'
    },
    resolve: {
        extensions: ['.js', '.jsx']
    },
    performance: {
        hints: isProduction ? 'warning' : false,
        maxEntrypointSize: 512000,
        maxAssetSize: 512000
    }
};
