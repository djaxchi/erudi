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

// Image loader for PNG, JPG, JPEG, GIF, SVG
rules.push({
  test: /\.(png|jpe?g|gif|svg)$/i,
  type: 'asset/resource',
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
        "Content-Security-Policy": `
          default-src 'self' 'unsafe-inline' data: http://localhost:8000 http://127.0.0.1:8000;
          connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws: wss: https://script.google.com;
          script-src 'self' 'unsafe-inline' https://script.google.com;
          style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
          font-src 'self' https://fonts.gstatic.com;
          img-src 'self' data: https://fonts.gstatic.com https://fonts.googleapis.com;
        `,
      },
    }),
  ],
  resolve: {
    extensions: [".js", ".jsx", ".json"],
  },
};
