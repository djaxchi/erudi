// webpack.preload.config.js
const path = require("path");

module.exports = {
  target: "electron-preload",
  entry: {
    preload: path.resolve(__dirname, "src/preload.js"),
  },
  output: {
    filename: "[name].js",
    path: path.resolve(__dirname, ".webpack/main_window"),
  },
  // 1) on n’inclut pas systeminformation dans le bundle
  externals: ["systeminformation"],
  // 2) on désactive les fallback pour tous les modules Node qui posaient problème
  resolve: {
    fallback: {
      fs: false,
      child_process: false,
      os: false,
      path: false,
      net: false,
      util: false,
      http: false,
      https: false,
    },
  },
};
