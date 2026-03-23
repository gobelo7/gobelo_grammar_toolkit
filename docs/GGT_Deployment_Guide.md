# GGT Multi-Platform Deployment Guide

This guide provides comprehensive instructions for packaging the Gobelo Grammar Toolkit (GGT) for web and desktop deployment.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GGT Multi-Platform Stack                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Web App    │    │ Desktop App  │    │ Python Core  │      │
│  │  (Next.js)   │    │  (Electron)  │    │   (GGT)      │      │
│  │              │    │              │    │              │      │
│  │ - React UI   │    │ - Same UI    │    │ - Loader     │      │
│  │ - API Routes │    │ - Bundled    │    │ - Analyzer   │      │
│  │ - PWA Cache  │    │ - Offline    │    │ - Generator  │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │              │
│         └───────────────────┴───────────────────┘              │
│                             │                                   │
│                    ┌────────▼────────┐                         │
│                    │  Shared API     │                         │
│                    │  Interface      │                         │
│                    └─────────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Web Application
- **Framework**: Next.js 16 with App Router
- **UI**: React 19 + TypeScript + Tailwind CSS 4
- **Components**: shadcn/ui (New York style)
- **PWA**: next-pwa for offline caching

### Desktop Application
- **Framework**: Electron (primary) or Tauri (lightweight alternative)
- **Python Backend**: PyInstaller bundled executable
- **Communication**: IPC (Inter-Process Communication) or HTTP localhost

### Python Backend
- **Library**: GGT Python package
- **Bundling**: PyInstaller for standalone executable
- **Data**: YAML grammar files bundled in executable

## Directory Structure

```
ggt-deployment/
├── web/                          # Next.js web application
│   ├── src/
│   │   ├── app/
│   │   │   ├── api/ggt/         # API routes
│   │   │   └── page.tsx         # Main UI
│   │   ├── lib/
│   │   │   └── ggt-data.ts      # Type definitions & mock data
│   │   └── components/ui/       # shadcn/ui components
│   ├── public/
│   ├── package.json
│   └── next.config.ts
│
├── desktop/                      # Electron desktop application
│   ├── src/
│   │   ├── main.ts              # Electron main process
│   │   ├── preload.ts           # Preload script (IPC bridge)
│   │   └── renderer/            # React app (same as web)
│   ├── python-backend/          # Bundled Python executable
│   │   ├── ggt-service.exe      # PyInstaller output
│   │   └── languages/           # Grammar YAML files
│   ├── electron-builder.yml     # Build configuration
│   └── package.json
│
├── python/                       # GGT Python package
│   ├── gobelo_grammar_toolkit/
│   │   ├── core/
│   │   ├── apps/
│   │   └── languages/
│   ├── service/                 # FastAPI service for local HTTP
│   │   ├── main.py              # FastAPI endpoints
│   │   └── requirements.txt
│   ├── build.spec               # PyInstaller spec file
│   └── pyproject.toml
│
└── docs/
    ├── deployment-guide.md
    ├── api-reference.md
    └── user-manual.md
```

## Step-by-Step Implementation

### Phase 1: Python Backend Service

1. **Create FastAPI Service** (for local HTTP communication):

```python
# python/service/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from gobelo_grammar_toolkit import GobeloGrammarLoader, GrammarConfig
from gobelo_grammar_toolkit.apps.morphological_analyzer import MorphologicalAnalyzer

app = FastAPI(title="GGT Local Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pre-load all languages
loaders = {}
analyzers = {}

def get_loader(language: str):
    if language not in loaders:
        loaders[language] = GobeloGrammarLoader(GrammarConfig(language=language))
    return loaders[language]

@app.get("/languages")
def list_languages():
    loader = get_loader("chitonga")
    return {"languages": loader.list_supported_languages()}

@app.post("/analyze")
def analyze_word(language: str, word: str):
    loader = get_loader(language)
    if language not in analyzers:
        analyzers[language] = MorphologicalAnalyzer(loader)
    result = analyzers[language].analyze(word)
    return {"analysis": result}

@app.get("/concords/{language}")
def get_concords(language: str):
    loader = get_loader(language)
    return {
        "subject": loader.get_subject_concords().entries,
        "object": loader.get_object_concords().entries,
    }
```

2. **PyInstaller Build Configuration**:

```python
# python/build.spec
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['service/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../gobelo_grammar_toolkit/languages/*.yaml', 'gobelo_grammar_toolkit/languages'),
    ],
    hiddenimports=[
        'gobelo_grammar_toolkit',
        'gobelo_grammar_toolkit.core',
        'gobelo_grammar_toolkit.apps',
        'fastapi',
        'uvicorn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ggt-service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

3. **Build Command**:
```bash
cd python
pip install pyinstaller fastapi uvicorn
pyinstaller build.spec
```

### Phase 2: Electron Desktop App

1. **Install Electron**:
```bash
cd desktop
npm init -y
npm install electron electron-builder --save-dev
npm install react react-dom
```

2. **Electron Main Process** (`desktop/src/main.ts`):

```typescript
import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

function startPythonBackend() {
  const exePath = path.join(
    process.resourcesPath,
    'python-backend',
    'ggt-service.exe'
  );
  
  pythonProcess = spawn(exePath, ['--port', '50051'], {
    stdio: 'inherit',
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  // Load the built React app
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(() => {
  startPythonBackend();
  setTimeout(createWindow, 1000); // Wait for Python to start
});

app.on('window-all-closed', () => {
  if (pythonProcess) pythonProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});
```

3. **Preload Script** (`desktop/src/preload.ts`):

```typescript
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('ggtAPI', {
  analyze: async (language: string, word: string) => {
    return await fetch(`http://localhost:50051/analyze?language=${language}&word=${word}`)
      .then(res => res.json());
  },
  getLanguages: async () => {
    return await fetch('http://localhost:50051/languages')
      .then(res => res.json());
  },
});
```

4. **Electron Builder Config** (`desktop/electron-builder.yml`):

```yaml
appId: com.gobelo.ggt
productName: Gobelo Grammar Toolkit
directories:
  output: dist

win:
  target:
    - nsis
    - portable
  icon: assets/icon.ico

nsis:
  oneClick: false
  allowToChangeInstallationDirectory: true
  installerIcon: assets/icon.ico
  uninstallerIcon: assets/icon.ico

extraResources:
  - from: "../python/dist/ggt-service.exe"
    to: "python-backend/ggt-service.exe"
  - from: "../gobelo_grammar_toolkit/languages"
    to: "python-backend/languages"

files:
  - "src/renderer/**/*"
  - "src/main.js"
  - "src/preload.js"
```

5. **Build Commands**:
```bash
cd desktop
npm run build        # Build React app
npm run electron:build  # Package with electron-builder
```

### Phase 3: Web Application (Next.js)

The web application is already implemented. Key enhancements:

1. **Add PWA Support** (`next.config.ts`):

```typescript
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // ... existing config
};

// For PWA, install: npm install next-pwa
// Then add PWA configuration

export default nextConfig;
```

2. **API Routes** connect to Python backend in production:
   - Development: Use mock data or local Python service
   - Production: Connect to deployed Python backend

### Phase 4: Alternative Tauri Approach (Lightweight)

Tauri provides a smaller bundle size by using the OS webview instead of Chromium:

1. **Install Tauri**:
```bash
npm create tauri-app@latest ggt-desktop
cd ggt-desktop
npm install
```

2. **Tauri Config** (`src-tauri/tauri.conf.json`):

```json
{
  "build": {
    "beforeBuildCommand": "npm run build",
    "beforeDevCommand": "npm run dev",
    "devPath": "http://localhost:3000",
    "distDir": "../dist"
  },
  "tauri": {
    "bundle": {
      "active": true,
      "targets": ["msi", "nsis"],
      "identifier": "com.gobelo.ggt",
      "resources": ["../python/dist/*"]
    },
    "allowlist": {
      "all": true
    }
  }
}
```

## Deployment Checklist

### Web Application
- [ ] Configure production API endpoint
- [ ] Set up HTTPS/SSL certificate
- [ ] Enable PWA caching
- [ ] Configure CDN for static assets
- [ ] Set up monitoring and error tracking
- [ ] Create deployment CI/CD pipeline

### Desktop Application
- [ ] Build Python service executable
- [ ] Bundle grammar YAML files
- [ ] Build Electron/Tauri app
- [ ] Code sign the executable (Windows)
- [ ] Create installer (NSIS/MSI)
- [ ] Test on clean Windows machine
- [ ] Create update mechanism

### Documentation
- [ ] User installation guide
- [ ] Feature walkthrough
- [ ] Troubleshooting guide
- [ ] Update instructions

## Update Distribution Strategy

### For Online Users
- Web app: Automatic updates on page reload
- Desktop: Check for updates on launch, prompt to download

### For Offline Users
1. **USB Distribution**: Periodic visits to connected locations for USB updates
2. **Offline Update Package**: Downloadable zip file that can be extracted
3. **Version Check**: Local version comparison when visiting connected location

## File Size Estimates

| Component | Size |
|-----------|------|
| Next.js Web Build | ~15-25 MB |
| Electron Framework | ~150 MB |
| Tauri Framework | ~10-15 MB |
| Python + GGT | ~50-80 MB |
| Grammar YAML files | ~1-2 MB |
| **Total (Electron)** | ~200-250 MB |
| **Total (Tauri)** | ~60-100 MB |

## Support and Maintenance

- **Version Management**: Semantic versioning for all components
- **Bug Tracking**: GitHub Issues
- **Feature Requests**: Community feedback portal
- **Documentation Updates**: Per-release updates
