const path = require("path");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");
const TerserPlugin = require("terser-webpack-plugin");
const CssMinimizerPlugin = require("css-minimizer-webpack-plugin");

const outputDir = path.resolve(__dirname, "../core/posts/static/posts");

module.exports = {
  entry: {
    main: "./src/scss/main.scss",
    detail: "./src/scss/detail.scss",
    add: "./src/scss/add.scss",
    categories: "./src/scss/categories.scss",
    index: "./src/scss/index.scss",
    list: "./src/scss/list.scss",
    form: "./src/scss/form.scss",
    gallery: "./src/scss/gallery.scss",
    "j-index": "./src/js/index.js",
    "j-detail": "./src/js/detail.js",
    "j-gallery": "./src/js/gallery.js"
  },
  context: __dirname,
  target: ["web", "es2017"],
  output: {
    path: outputDir,
    filename: "[name].js",
    clean: false
  },
  optimization: {
    minimize: true,
    minimizer: [
      new TerserPlugin({
        extractComments: false,
        terserOptions: {
          format: { comments: false },
          toplevel: true
        }
      }),
      new CssMinimizerPlugin()
    ]
  },
  module: {
    rules: [
      {
        test: /\.scss$/,
        use: [
          MiniCssExtractPlugin.loader,
          "css-loader",
          {
            loader: "sass-loader",
            options: {
              implementation: require("sass"),
              sassOptions: {
                quietDeps: true
              }
            }
          }
        ]
      },
      {
        test: /\.css$/,
        use: [
          MiniCssExtractPlugin.loader,
          {
            loader: "css-loader",
            options: { url: false }
          }
        ]
      },
      {
        test: /\.(woff(2)?|ttf|eot|svg)(\?v=\d+\.\d+\.\d+)?$/,
        type: "asset/resource"
      }
    ]
  },
  plugins: [
    new MiniCssExtractPlugin({
      filename: "[name].css",
      chunkFilename: "[id].css"
    })
  ]
};
