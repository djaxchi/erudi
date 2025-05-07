const HtmlWebpackPlugin = require("html-webpack-plugin");
const rules = require("./webpack.rules");
const path = require("path");

rules.push({
  test: /\.css$/,
  use: [
    { loader: "style-loader" },
    { loader: "css-loader" },
    {
      loader: "postcss-loader",
      options: {
        postcssOptions: {
          plugins: [require("tailwindcss"), require("autoprefixer")],
        },
      },
    },
  ],
});

module.exports = {
  // Put your normal webpack config below here
  entry: "./src/renderer.js", // Entry point for the renderer process
  output: {
    path: path.resolve(__dirname, ".webpack/renderer"),
    filename: "renderer.js",
  },
  module: {
    rules,
  },
  plugins: [
    new HtmlWebpackPlugin({
      template: "./public/index.html", // Path to your HTML template
      inject: true,
      scriptLoading: "blocking",
      meta: {
        "Content-Security-Policy":
          "default-src 'self'; connect-src 'self' http://localhost:8000; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';",
      },
    }),
  ],
  resolve: {
    extensions: [".js", ".jsx", ".json"],
  },
};
