# GGT Multi-Platform Deployment - Implementation Plan

## Executive Summary

This document provides a comprehensive implementation plan for packaging the Gobelo Grammar Toolkit (GGT) for both web and desktop deployment. The solution addresses the needs of schools in Zambia with varying levels of internet connectivity.

## Project Overview

### Target Users
- **Urban Schools**: High-speed internet access → Web Application
- **Remote Schools**: No/limited internet → Desktop Application (.exe)

### Supported Languages
1. chiTonga (full grammar, 21 noun classes, 11 verb slots)
2. chiBemba (stub)
3. chiNyanja (stub)
4. Kaonde (stub)
5. Lunda (stub)
6. Luvale (stub)
7. Silozi (stub)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Access Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   Web Browser   │    │  Desktop App    │                    │
│  │   (Online)      │    │  (Offline)      │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
└───────────┼──────────────────────┼─────────────────────────────┘
            │                      │
┌───────────┼──────────────────────┼─────────────────────────────┐
│           ▼                      ▼                             │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  Next.js App    │    │  Electron App   │                    │
│  │  (React UI)     │    │  (Same UI)      │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
│           │                      │           Application Layer  │
└───────────┼──────────────────────┼─────────────────────────────┘
            │                      │
┌───────────┼──────────────────────┼─────────────────────────────┐
│           ▼                      ▼                             │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  Cloud API      │    │ Local HTTP      │                    │
│  │  (FastAPI)      │    │ (FastAPI:50051) │                    │
│  └────────┬────────┘    └────────┬────────┘   API Layer        │
└───────────┼──────────────────────┼─────────────────────────────┘
            │                      │
┌───────────┼──────────────────────┼─────────────────────────────┐
│           ▼                      ▼                             │
│  ┌──────────────────────────────────────────┐                  │
│  │      GGT Python Library                  │                  │
│  │  (GobeloGrammarLoader + Apps)            │   Core Layer     │
│  │  + YAML Grammar Files (7 languages)      │                  │
│  └──────────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Components

### 1. Web Application (Next.js)

**Status**: ✅ Implemented

**Location**: `/src/app/`

**Features**:
- Morphological Analysis interface
- Paradigm Generation tables
- Corpus Annotation (CoNLL-U output)
- Grammar Browser (noun classes, TAM markers, extensions)
- Language selector for all 7 languages
- Responsive design for desktop and mobile

**Tech Stack**:
- Next.js 16 with App Router
- React 19 + TypeScript
- Tailwind CSS 4
- shadcn/ui components

**Deployment Options**:
- Vercel (recommended)
- Docker container
- Static export + CDN

### 2. Desktop Application (Electron)

**Status**: ✅ Configuration Complete

**Location**: `/desktop/`

**Components**:
- `src/main.ts` - Electron main process
- `src/preload.ts` - IPC bridge
- `package.json` - Build configuration
- `tsconfig.json` - TypeScript config

**Build Output**:
- Windows: `.exe` installer + portable
- macOS: `.dmg` (optional)
- Linux: `.AppImage`, `.deb` (optional)

### 3. Python Backend Service (FastAPI)

**Status**: ✅ Implemented

**Location**: `/python/service/main.py`

**Endpoints**:
- `GET /languages` - List supported languages
- `GET /analyze?word=xxx&language=xxx` - Morphological analysis
- `GET /concords/{language}` - Get concords
- `GET /noun-classes/{language}` - Get noun classes
- `GET /tam/{language}` - Get TAM markers
- `POST /paradigm` - Generate paradigm table
- `POST /corpus/annotate` - Annotate corpus

### 4. Build System

**Status**: ✅ Configuration Complete

**Files**:
- `build.sh` - Main build script
- `python/build.spec` - PyInstaller configuration
- `desktop/electron-builder.yml` - Electron builder config

## File Structure

```
/home/z/my-project/
├── src/                          # Next.js web app
│   ├── app/
│   │   ├── api/ggt/route.ts     # API endpoints
│   │   ├── page.tsx             # Main UI
│   │   ├── layout.tsx           # Root layout
│   │   └── globals.css          # Global styles
│   ├── lib/
│   │   └── ggt-data.ts          # Type definitions & data
│   └── components/ui/           # shadcn/ui components
│
├── desktop/                      # Electron desktop app
│   ├── src/
│   │   ├── main.ts              # Electron main process
│   │   └── preload.ts           # IPC bridge
│   ├── package.json             # Dependencies & build config
│   └── tsconfig.json            # TypeScript config
│
├── python/                       # Python backend
│   ├── service/
│   │   ├── main.py              # FastAPI service
│   │   └── requirements.txt     # Python dependencies
│   └── build.spec               # PyInstaller config
│
├── download/                     # Generated documents
│   ├── GGT_Multi_Platform_Deployment_Prompt.docx
│   └── GGT_Deployment_Guide.md
│
└── build.sh                      # Main build script
```

## Build Instructions

### Prerequisites

1. **Node.js**: v18+ (for Electron build)
2. **Python**: v3.9+ (for GGT backend)
3. **pip**: For Python package management

### Quick Build

```bash
# Build everything
./build.sh --all

# Build only Python backend
./build.sh --python-only

# Build only Electron app (requires Python backend first)
./build.sh --electron-only

# Clean and rebuild
./build.sh --clean --all
```

### Manual Build Steps

#### 1. Build Python Backend

```bash
cd python
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r service/requirements.txt
pip install pyinstaller
pyinstaller build.spec --noconfirm
```

#### 2. Build Desktop App

```bash
cd desktop
npm install
npm run build
npm run electron:build
```

## Deployment Guide

### Web Application

1. **Development**:
   ```bash
   cd /home/z/my-project
   bun run dev
   # Access at http://localhost:3000
   ```

2. **Production (Vercel)**:
   - Connect GitHub repository to Vercel
   - Deploy automatically on push

3. **Production (Docker)**:
   ```dockerfile
   FROM node:20-alpine
   COPY . /app
   WORKDIR /app
   RUN npm ci && npm run build
   CMD ["npm", "start"]
   ```

### Desktop Application

1. **Development Testing**:
   ```bash
   cd desktop
   npm run dev
   ```

2. **Build Installer**:
   ```bash
   npm run electron:build:win
   # Output: desktop/release/GGT Setup 1.0.0.exe
   ```

3. **Distribution**:
   - Upload installer to download server
   - Distribute via USB for offline schools
   - Include in teacher training kits

## Update Strategy

### For Online Users
- **Web**: Automatic updates on page refresh
- **Desktop**: Check for updates on launch, prompt to download new version

### For Offline Users
1. **USB Distribution**: Periodic visits to connected locations
2. **Update Package**: Self-extracting zip with new executable
3. **Version Check**: Display current version, compare when online

## File Size Estimates

| Component | Size |
|-----------|------|
| Web Build | ~15-25 MB |
| Electron Framework | ~150 MB |
| Python + Dependencies | ~50-80 MB |
| Grammar YAML Files | ~1-2 MB |
| **Total Desktop App** | ~200-250 MB |

## Testing Checklist

### Web Application
- [ ] All 7 languages load correctly
- [ ] Morphological analysis returns results
- [ ] Paradigm generation works for all TAM markers
- [ ] Corpus annotation produces valid CoNLL-U
- [ ] Responsive design on mobile/tablet/desktop
- [ ] PWA caching works offline

### Desktop Application
- [ ] Python backend starts correctly
- [ ] IPC communication works
- [ ] All API endpoints accessible
- [ ] File dialogs work correctly
- [ ] Installer creates correct shortcuts
- [ ] App works without internet connection
- [ ] Grammar files are bundled correctly

## Support & Maintenance

### Version Management
- Use semantic versioning (MAJOR.MINOR.PATCH)
- Synchronized versions across web, desktop, and Python

### Bug Tracking
- GitHub Issues for bug reports
- Feature request template for new functionality

### Documentation
- User guide for teachers
- Technical documentation for developers
- Update this document with each release

## Next Steps

1. **Testing**: Test the web application in the preview panel
2. **Python Integration**: Connect to actual GGT Python library
3. **Production Build**: Create signed Windows installer
4. **Distribution**: Set up download page for schools
5. **Training**: Create teacher training materials

## Contact

- **Project**: Gobelo Grammar Toolkit
- **Repository**: github.com/gobelo/grammar-toolkit
- **Languages**: chiTonga, chiBemba, chiNyanja, Kaonde, Lunda, Luvale, Silozi
