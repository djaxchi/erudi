const { FusesPlugin } = require("@electron-forge/plugin-fuses");
const { FuseV1Options, FuseVersion } = require("@electron/fuses");
const path = require("path");

module.exports = {
  packagerConfig: {
    asar: true,
    prune: true,
    
    // Unpack native modules & backend for runtime access (critical for CUDA/MLX)
    asarUnpack: ["**/*.node"],
    
    // Resource bundling: include backend for all platforms
    extraResource: [
      "../backend/dist/backend"
    ],
    
    // Exclude unnecessary files to reduce bundle size
    ignore: [
      "^/tests($|/)",
      "^/\\.github($|/)",
      "^/docs($|/)",
      "^/\\.gitignore$",
      "^/\\.env($|/)",
      "\\.map$",
      "\\.md$",
      "\\.ts$"
    ],
    
    // Application metadata (cross-platform)
    name: "erudi",
    executableName: "erudi",
    appBundleId: "com.erudi.app",
    appCategoryType: "public.app-category.productivity",
    icon: "./assets/icons/icon",
    appCopyright: "Copyright © 2025 Erudi Team",
    appVersion: "1.0.0",
    buildVersion: "1.0.0",
    
    // macOS-specific code signing & notarization
    ...(process.platform === "darwin" && {
      ...(process.env.APPLE_SIGNING_IDENTITY && {
        osxSign: {
          identity: process.env.APPLE_SIGNING_IDENTITY,
          hardenedRuntime: true,
          entitlements: "./entitlements.plist",
          entitlementsInherit: "./entitlements.plist",
          gatekeeper: false,
        },
      }),
      ...(process.env.APPLE_ID && {
        osxNotarize: {
          tool: "notarytool",
          appleId: process.env.APPLE_ID,
          appleIdPassword: process.env.APPLE_ID_PASSWORD,
          teamId: process.env.APPLE_TEAM_ID,
        },
      }),
    }),
    
    // Windows-specific metadata
    ...(process.platform === "win32" && {
      win32metadata: {
        CompanyName: "Erudi AI",
        FileDescription: "Erudi: Local LLM Specialization Desktop App",
        OriginalFilename: "erudi.exe",
        ProductName: "Erudi",
        InternalName: "erudi",
      },
    }),
  },

  rebuildConfig: {
    // Rebuild native modules for the target platform
    buildPath: path.resolve(__dirname, "forge-local-build"),
  },

  makers: [
    // macOS: DMG installer
    {
      name: "@electron-forge/maker-dmg",
      platforms: ["darwin"],
      config: {
        name: "erudi-Installer",
        icon: "./assets/icons/icon.icns",
        background: "./assets/installers/dmg-background.png",
        format: "UDZO",
        window: {
          x: 420,
          y: 200,
          width: 640,
          height: 440,
        },
        contents: [
          {
            x: 200,
            y: 200,
            type: "file",
            path: "./out/erudi-darwin-arm64/erudi.app",
          },
          {
            x: 400,
            y: 200,
            type: "link",
            path: "/Applications",
          },
        ],
        iconSize: 80,
        textColor: "#FFFFFF",
      },
    },
    
    // macOS: ZIP archive
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"],
    },
    
    // Windows: ZIP portable
    // (Squirrel removed — it silently fails for nupkgs > ~1 GB and produces a
    //  dummy 290 KB Setup.exe. Migrate to electron-builder NSIS for a real installer.)
    {
      name: "@electron-forge/maker-zip",
      platforms: ["win32"],
    },
    
    // Linux: DEB
    {
      name: "@electron-forge/maker-deb",
      platforms: ["linux"],
      config: {
        icon: "./assets/icons/icon.png",
      },
    },
    
    // Linux: RPM
    {
      name: "@electron-forge/maker-rpm",
      platforms: ["linux"],
      config: {
        icon: "./assets/icons/icon.png",
      },
    },
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
      
      const existingFiles = await fs.readdir(releaseDir);
      const exeCount = existingFiles.filter(file => file.endsWith('.exe')).length;
      const nextVersion = exeCount + 1;
      
      for (const result of makeResults) {
        for (const artifact of result.artifacts) {
          if (artifact.endsWith('.exe')) {
            const fileName = path.basename(artifact);
            const newName = fileName.replace('.exe', `-alpha-v0.${nextVersion}.exe`);
            const destPath = path.join(releaseDir, newName);
            
            await fs.copy(artifact, destPath);
          }
        }
      }
      
      // Nettoyage automatique après copie - tout est intégré dans le .exe
      await fs.remove(path.join(__dirname, 'out'));
      await fs.remove(path.join(__dirname, '.webpack'));
      await fs.remove(path.join(__dirname, '../build'));
      await fs.remove(path.join(__dirname, '../dist'));
      await fs.remove(path.join(__dirname, '../backend.spec'));
    }
  }
};