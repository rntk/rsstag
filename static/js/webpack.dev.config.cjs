const path = require('path');
const baseConfig = require('./webpack.config.js');

module.exports = {
  ...baseConfig,
  devServer: {
    static: {
      directory: path.join(__dirname, '..'),
    },
    compress: true,
    port: 8886,
    hot: true,
    open: false,
    historyApiFallback: true,
    proxy: [
      {
        context: ['/api', '/static/css'],
        target: 'http://localhost:8885',
        changeOrigin: true,
      },
    ],
  },
};
