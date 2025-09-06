const path = require("path");
const fs = require("fs");

module.exports = {
  packagerConfig: {
    asar: true,
    prune: true,
    icon: path.resolve(__dirname, "assets", "icon.icns"),
    asarUnpack: ["**/*.node"],
    ignore: [
      "^/tests($|/)",
      "^/\\.github($|/)",
      "^/docs($|/)",
      "\\.map$",
      "\\.md$",
      "\\.ts$",
      "^/releases($|/)"
    ],
    // On inclut le backend binaire dans Resources/backend
    extraResource: [
      path.resolve(__dirname, "../dist/backend") // => Resources/backend
    ],
    osxSign: false,   // pas de signature (pour l’instant)
    osxNotarize: false
  },

  makers: [
    {
      name: "@electron-forge/maker-dmg",
      config: {
        // DMG “drag to Applications”
        format: "ULFO",
        background: path.resolve(__dirname, "assets", "dmg-background.png"), // optionnel
        icon: path.resolve(__dirname, "assets", "icon.icns"),
        overwrite: true,
        debug: false,
        contents: (opts) => [
          {
            x: 130, y: 220, type: "file",
            path: path.join(opts.appPath, path.basename(opts.appPath))
          },
          {
            x: 410, y: 220, type: "link",
            path: "/Applications"
          }
        ]
      }
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"]
    }
  ],

  plugins: [
    {
      name: "@electron-forge/plugin-auto-unpack-natives",
      config: {}
    },
    // Si tu utilises le plugin webpack, conserve ta config actuelle :
    {
      name: "@electron-forge/plugin-webpack",
      config: {
        mainConfig: "./webpack.main.config.js",
        renderer: {
          config: "./webpack.renderer.config.js",
          entryPoints: [
            {
              html: "./public/index.html",
              js: "./src/renderer.js",
              name: "main_window",
              preload: {
                js: "./src/preload.js",
              },
            },
          ],
        },
        devServer: { hot: true }
      }
    }
  ],

  hooks: {
    prePackage: async (forgeConfig, buildPath) => {
      const fs = require('fs-extra');
      const path = require('path');

      // Nettoyage
      await fs.remove(path.join(__dirname, 'out'));
      await fs.remove(path.join(__dirname, '.webpack'));

      const backendPath = path.resolve(__dirname, "../dist/backend/backend");
      if (!await fs.pathExists(backendPath)) {
        throw new Error(`Backend not found at ${backendPath} — build it first with PyInstaller.`);
      }

      // Copier .env (public) à côté du backend si présent
      const envSource = path.resolve(__dirname, "../.env");
      const envDest = path.resolve(__dirname, "../dist/backend/.env");
      if (await fs.pathExists(envSource)) {
        await fs.copy(envSource, envDest);
      }
      // S’assurer que le binaire est exécutable
      await fs.chmod(backendPath, 0o755);
    },
    postMake: async (forgeConfig, makeResults) => {
      const fs = require('fs-extra');
      const path = require('path');
      const releaseDir = path.join(__dirname, '../releases');

      await fs.ensureDir(releaseDir);

      for (const result of makeResults) {
        for (const artifact of result.artifacts) {
          if (artifact.endsWith('.dmg') || artifact.endsWith('.zip')) {
            const fileName = path.basename(artifact);
            const destPath = path.join(releaseDir, fileName);
            await fs.copy(artifact, destPath);
          }
        }
      }

      // Nettoyage (on ne supprime pas dist/backend pour pouvoir itérer)
      await fs.remove(path.join(__dirname, 'out'));
      await fs.remove(path.join(__dirname, '.webpack'));
      await fs.remove(path.join(__dirname, '../build'));
      // NE PAS supprimer ../dist (on en a besoin pour copies ultérieures)
    }
  }
};
