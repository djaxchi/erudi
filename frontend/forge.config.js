const { FusesPlugin } = require("@electron-forge/plugin-fuses");
const { FuseV1Options, FuseVersion } = require("@electron/fuses");
const path = require("path");

module.exports = {
  packagerConfig: {
    asar: true,
    prune: true,
    icon: path.resolve(__dirname, "assets", "icon.ico"),
    // Unpack native modules for performance
    asarUnpack: ["**/*.node"],
    // Exclude unnecessary files to slim bundle
    ignore: [
      "^/tests($|/)",
      "^/\.github($|/)",
      "^/docs($|/)",
      "\\.map$",
      "\\.md$",
      "\\.ts$"
    ],
    extraResource: [
      // Backend executable
      path.resolve(__dirname, "../dist/backend")
    ],
    win32metadata: {
      CompanyName: "erudi AI",
      FileDescription: "erudi AI Desktop App",
      OriginalFilename: "erudiSetup.exe",
      ProductName: "erudi",
      InternalName: "erudi"
    }
  },

  rebuildConfig: {
    // Skip rebuilding large native modules if already packaged
    buildPath: path.resolve(__dirname, "forge-local-build"),
  },

  makers: [
    {
      name: "@felixrieseberg/electron-forge-maker-nsis",
      config: {
        // Windows code signing to be filled in when we have a certificate
        // codesigning: {
        //   certificateFile: process.env.WIN_CERT_FILE,
        //   certificatePassword: process.env.WIN_CERT_PASS,
        //   timestampServer: 'http://timestamp.digicert.com',
        //   description: 'erudi',
        //   website: 'https://erudi.ai'
        // },

        // Auto‑update config – commented until configured on Git
        // updater: {
        //   url: 'https://downloads.erudi.ai/desktop',
        //   updaterCacheDirName: 'erudi-updater',
        //   channel: 'latest',
        //   publisherName: 'erudi AI'
        // },

        // IMPORTANT: The maker expects getAppBuilderConfig (not getAdditionalConfig)
        // Everything returned merges straight into electron-builder's config.
        getAppBuilderConfig: () => ({
          artifactName: "${productName}-Setup-${version}-${os}.${ext}",
          win: { icon: path.resolve(__dirname,'assets','icon.ico') },
          nsis: {
            oneClick: false,
            perMachine: false,
            allowToChangeInstallationDirectory: true,
            createDesktopShortcut: true,
            createStartMenuShortcut: true,
            shortcutName: 'erudi',
            runAfterFinish: true,
            license: path.resolve(__dirname, 'LICENSE.txt'),
            installerIcon: path.resolve(__dirname, 'assets', 'icon.ico'),
            uninstallerIcon: path.resolve(__dirname, 'assets', 'icon.ico'),
            installerHeaderIcon: path.resolve(__dirname, 'assets', 'icon.ico'),
            include: path.resolve(__dirname, 'scripts', 'uninstall_cleanup.nsh'),
            installerLanguages: ['en_US', 'fr_FR'],
            displayLanguageSelector: true,
          }
        })
      }
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"],
    },
    {
      name: "@electron-forge/maker-deb",
      config: {
        options: {
          icon: path.resolve(__dirname, "assets", "icon.png"),
        }
      }
    },
    {
      name: "@electron-forge/maker-rpm",
      config: {
        options: {
          icon: path.resolve(__dirname, "assets", "icon.ico"),
        }
      }
    }
  ],

  plugins: [
    {
      name: "@electron-forge/plugin-auto-unpack-natives",
      config: {
        // Auto-unpack native modules for faster startup
      }
    },
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
        // Enable persistent caching to speed up repeated builds
        devServer: {
          hot: true
        }
      }
    },
    new FusesPlugin({
      version: FuseVersion.V1,
      [FuseV1Options.RunAsNode]: false,
      [FuseV1Options.EnableCookieEncryption]: true,
      [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
      [FuseV1Options.EnableNodeCliInspectArguments]: false,
      [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
      [FuseV1Options.OnlyLoadAppFromAsar]: true,
    }),
  ],

  // Custom script hooks for optimizing build
  hooks: {
    prePackage: async (forgeConfig, buildPath) => {
      const fs = require('fs-extra');
      const path = require('path');
      
      await fs.remove(path.join(__dirname, 'out'));
      await fs.remove(path.join(__dirname, '.webpack'));
      
      const backendPath = path.resolve(__dirname, '../dist/backend/backend.exe');
      if (!await fs.pathExists(backendPath)) {
        throw new Error(`Backend not found at ${backendPath}`);
      }

      // Copier le .env (il n'y a que les variables publiques)
      const envSource = path.resolve(__dirname, '../.env');
      const envDest = path.resolve(__dirname, '../dist/backend/.env');
      if (await fs.pathExists(envSource)) {
        await fs.copy(envSource, envDest);
      }
    },
    postMake: async (forgeConfig, makeResults) => {
      const fs = require('fs-extra');
      const path = require('path');
      const releaseDir = path.join(__dirname, '../releases');
      
      await fs.ensureDir(releaseDir);
      
      for (const result of makeResults) {
        for (const artifact of result.artifacts) {
          if (artifact.endsWith('.exe')) {
            const fileName = path.basename(artifact);
            const destPath = path.join(releaseDir, fileName);
            
            await fs.copy(artifact, destPath);
          }
        }
      }
      
      // Nettoyage automatique après copie - tout est intégré dans le .exe
      await fs.remove(path.join(__dirname, 'out'));
      await fs.remove(path.join(__dirname, '.webpack'));
      // Do NOT remove the BACKEND files and dir until the final building method has been found.
      await fs.remove(path.join(__dirname, '../build'));
      await fs.remove(path.join(__dirname, '../dist'));
      await fs.remove(path.join(__dirname, '../backend.spec'));
    }
  }
};