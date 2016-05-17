var path = require("path");
var webpack = require("webpack");
var BundleTracker = require('webpack-bundle-tracker');

module.exports = {
    entry: [
        "./bower_components/jquery/dist/jquery.js",
        "./bower_components/bootstrap/dist/js/bootstrap.js",
        "./assets/js"
    ],
    output: {
        path: './assets/bundles',
        filename: "main.js"
    },
    resolve: {
        modulesDirectories: ["node_modules"]
    },
    module:  {
    loaders: [
      {test: /(\.jsx|\.js)$/, loader: 'script'}
    ]
    },
    plugins: [
        new webpack.ProvidePlugin({
                $:      "jquery",
                jQuery: "jquery"
            }),
        new BundleTracker({filename: './webpack-stats.json'})

    ]
};
