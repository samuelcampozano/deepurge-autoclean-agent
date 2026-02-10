# 🤖 Deepurge AutoClean Agent

<div align="center">

![Deepurge Banner](https://img.shields.io/badge/x%20OpenClaw-Agent%20Hackathon-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-green?style=for-the-badge&logo=python)
![Walrus](https://img.shields.io/badge/Walrus-Enabled-purple?style=for-the-badge)
![Windows](https://img.shields.io/badge/Windows-11-0078D6?style=for-the-badge&logo=windows)

**An autonomous file organization agent that monitors your Downloads folder, automatically classifies and organizes files, and logs all actions to Walrus decentralized storage on the Sui blockchain.**

[Demo Video](#-demo-video) • [Screenshots](#-screenshots) • [Installation](#-quick-start) • [Features](#-features) • [Architecture](#-architecture)

</div>

---

## 📸 Screenshots

### 🎮 Control Panel – Start/Stop Agent & Generate Demo Files
<p align="center">
  <img src="img/in progress running agent.png" alt="Control Panel - Agent Running" width="90%">
</p>

### 📊 Dashboard – Live Stats & Category Breakdown
<p align="center">
  <img src="img/in progress agent done.png" alt="Dashboard with stats" width="90%">
</p>

### 📂 Before – Messy Downloads Folder
<p align="center">
  <img src="img/downloads folder with information.png" alt="Downloads before agent" width="90%">
</p>

### ✅ After – Agent Organized Everything
<p align="center">
  <img src="img/after agent download folder.png" alt="Downloads after agent" width="90%">
</p>

### 🖥️ Agent Processing Files in Real-Time
<p align="center">
  <img src="img/in progress agent.png" alt="Agent processing" width="90%">
</p>

---

## 👤 Author

**Samuel Campozano Lopez**

- GitHub: [@samuelcampozano](https://github.com/samuelcampozano)
- Email: samuelco860@gmail.com
- Project: x OpenClaw Agent Hackathon

---

## 🎯 Features

| Feature | Description |
|---------|-------------|
| 📁 **Real-time Monitoring** | Watches Downloads folder using Watchdog library |
| 🏷️ **Smart Classification** | Categorizes files by extension (Images, Documents, Videos, etc.) |
| 📦 **Auto-Organization** | Moves files to organized folders with timestamps |
| 🔍 **Duplicate Detection** | SHA256 hash comparison to skip duplicates |
| 💾 **SQLite Logging** | Local database for action history |
| 🦭 **Walrus Integration** | Logs all actions to Sui blockchain storage |
| 📊 **Daily Reports** | Automatic daily summaries uploaded to Walrus |
| 🎮 **Control Panel** | Web UI to start/stop the agent, generate demo files, and stream live console output |
| 📊 **Web Dashboard** | Modern dark-themed UI with stat cards, category charts, Walrus blob explorer & live feed |
| 🐳 **Docker Full-Stack** | One container runs both the agent and dashboard — fully portable |
| �🔄 **Error Recovery** | Retry logic with configurable attempts |
| ⚙️ **Configurable** | JSON-based settings for all parameters |
| 🖥️ **Windows Service Ready** | Can run as scheduled task or service |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DEEPURGE AUTOCLEAN AGENT                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│   │   Watchdog   │───▶│  Classifier  │───▶│  Organizer   │         │
│   │  (Monitor)   │    │  (Analyze)   │    │   (Move)     │         │
│   └──────────────┘    └──────────────┘    └──────────────┘         │
│          │                   │                    │                 │
│          │                   │                    │                 │
│          ▼                   ▼                    ▼                 │
│   ┌──────────────────────────────────────────────────────┐         │
│   │                    DATABASE (SQLite)                  │         │
│   │     actions.db - Local logging & duplicate check     │         │
│   └──────────────────────────────────────────────────────┘         │
│                              │                                      │
│                              ▼                                      │
│   ┌──────────────────────────────────────────────────────┐         │
│   │                  WALRUS LOGGER                        │         │
│   │     Batch uploads every 100 actions                  │         │
│   │     Daily report generation                          │         │
│   └──────────────────────────────────────────────────────┘         │
│                              │                                      │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │      WALRUS STORAGE           │
               │   (Sui Blockchain)            │
               │                               │
               │  • Decentralized storage      │
               │  • Immutable action logs      │
               │  • Daily reports              │
               │  • Session summaries          │
               │                               │
               │  Testnet:                     │
               │  publisher.walrus-testnet.    │
               │  walrus.space                 │
               └───────────────┬───────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │    🖥️  DEEPURGE DASHBOARD      │
               │   (Flask + Docker)            │
               │                               │
               │  • 🎮 Control Panel           │
               │    Start/Stop Agent from UI   │
               │    Generate Demo Files        │
               │    Live Console Streaming     │
               │                               │
               │  • 📊 Dashboard & Stats       │
               │  • 🔍 Blob Explorer           │
               │  • 📜 Upload History          │
               │  • ⚡ Live Activity Feed       │
               │                               │
               │  http://localhost:5050        │
               └───────────────────────────────┘
```

---

## 📋 File Categories

| Category | Extensions | Emoji |
|----------|-----------|-------|
| 📸 **Images** | .jpg, .jpeg, .png, .gif, .webp, .svg, .bmp | 📸 |
| 📄 **Documents** | .pdf, .docx, .doc, .txt, .md, .xlsx, .xls | 📄 |
| 🎬 **Videos** | .mp4, .avi, .mov, .mkv, .wmv, .flv, .webm | 🎬 |
| 🎵 **Audio** | .mp3, .wav, .flac, .aac, .ogg, .wma | 🎵 |
| 💻 **Code** | .py, .js, .ts, .html, .css, .java, .json, .sol, .move | 💻 |
| 📦 **Archives** | .zip, .rar, .tar, .gz, .7z | 📦 |
| ⚙️ **Executables** | .exe, .msi, .bat, .cmd, .ps1, .sh | ⚙️ |
| 📁 **Other** | Everything else | 📁 |

---

## 🚀 Quick Start

### Prerequisites

- **Windows 11** (Windows 10 also supported)
- **Python 3.10+** ([Download](https://www.python.org/downloads/))
- **Internet connection** (for Walrus uploads)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/samuelcampozano/deepurge-autoclean-agent.git
   cd deepurge-autoclean-agent
   ```

2. **Run the installer**
   ```bash
   # Double-click or run:
   install.bat
   ```

3. **Configure settings** (optional)
   ```bash
   # Edit config.json to customize folders and settings
   notepad config.json
   ```

4. **Start the agent**
   ```bash
   run.bat
   ```

### Manual Installation

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the agent
python agent.py
```

---

## ⚙️ Configuration

Edit `config.json` to customize the agent:

```json
{
    "folders": {
        "watch_folder": "~/Downloads",
        "organized_folder": "~/Downloads/Organized"
    },
    "scan_interval_seconds": 60,
    "walrus": {
        "enabled": true,
        "network": "testnet",
        "upload_batch_size": 100
    },
    "rename_pattern": "YYYYMMDD_HHMMSS",
    "check_duplicates": true
}
```

### Key Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `watch_folder` | Folder to monitor | `~/Downloads` |
| `organized_folder` | Destination for organized files | `~/Downloads/Organized` |
| `scan_interval_seconds` | How often to check for new files | `60` |
| `upload_batch_size` | Actions before Walrus upload | `100` |
| `check_duplicates` | Enable SHA256 duplicate detection | `true` |
| `rename_pattern` | Timestamp pattern for new filenames | `YYYYMMDD_HHMMSS` |

---

## 🦭 Walrus Integration

### Why Walrus Decentralized Storage?

Unlike traditional cloud storage (Google Drive, Dropbox, S3), Walrus on the Sui blockchain provides unique guarantees that make it ideal for file organization audit trails:

| Feature | Traditional Cloud | Walrus on Sui |
|---------|------------------|---------------|
| **Immutability** | Files can be modified or deleted by the provider | ✅ Once stored, data can never be altered or deleted |
| **Censorship Resistance** | Single company controls access | ✅ No single entity can remove your records |
| **Cryptographic Verification** | Trust the provider's word | ✅ Anyone can verify any record at any time |
| **Transparency** | Opaque internal systems | ✅ Every blob is publicly auditable on-chain |
| **Cost Model** | Recurring monthly fees | ✅ Pay once, stored permanently on Sui |
| **Vendor Lock-in** | Tied to one provider | ✅ Open protocol, accessible from anywhere |

**Real-world value:** Your file organization history becomes a permanent, tamper-proof record — perfect for compliance auditing, digital asset management, or simply proving that a specific file existed and was organized at a specific time.

### Data Format

Every file operation is logged to Walrus decentralized storage:

```json
{
    "batch_type": "action_log",
    "timestamp": "2026-02-09T15:30:00Z",
    "action_count": 100,
    "actions": [
        {
            "action": "MOVED",
            "file_name": "vacation_photo.jpg",
            "category": "Images",
            "file_size": 2048576,
            "file_hash": "a1b2c3d4..."
        }
    ],
    "agent": "Deepurge-AutoClean-Agent-v1.0",
    "author": "Samuel Campozano Lopez"
}
```

### Walrus Endpoints (Testnet)

- **Publisher:** `https://publisher.walrus-testnet.walrus.space`
- **Aggregator:** `https://aggregator.walrus-testnet.walrus.space`

Retrieve any log using:
```
https://aggregator.walrus-testnet.walrus.space/v1/{blob_id}
```

---

## 🖥️ Web Dashboard & Control Panel

Deepurge includes a **modern dark-themed web dashboard** with a built-in **Control Panel** to manage the agent directly from your browser.

<p align="center">
  <img src="img/in progress agent done.png" alt="Dashboard" width="80%">
</p>

### Views

| View | Description |
|------|-------------|
| 🎮 **Control Panel** | Start/stop the agent, generate demo files, live console output streaming |
| 📊 **Dashboard** | Stat cards (files processed, uploads, data size), category chart, recent activity |
| 🔍 **Blob Explorer** | Paste any Walrus blob ID or URL to view the data in a friendly table |
| 📜 **Upload History** | Browse every batch, report & session the agent has uploaded |
| ⚡ **Live Feed** | Auto-refreshing activity feed straight from the local database |

### Quick Start (no Docker)

```bash
# Double-click:
dashboard.bat

# Or manually:
pip install flask flask-cors requests
cd dashboard
python app.py
```

Then open **http://localhost:5050** in your browser.

### 🐳 Docker (Recommended – Full Stack)

One command gives you the **agent + dashboard** in a portable container that mounts your real Downloads folder:

```bash
# Build and run (uses your Downloads folder by default)
docker-compose up --build -d

# Or specify a custom watch folder:
DEEPURGE_WATCH_FOLDER=/path/to/folder docker-compose up --build -d

# Dashboard + Control Panel at http://localhost:5050
```

The Docker container:
- Mounts your **real Downloads folder** so the agent organizes actual files
- Persists the database between restarts via a Docker volume
- Lets you start/stop the agent and generate demo files from the browser
- Works on any machine with Docker installed — **fully portable**

### Try it now with an existing blob

Open the **Blob Explorer** tab and paste:
```
gtkNTOBjo-LeesDwyPfj_KIsRv-uFII0XyIBwpPjp70
```

The dashboard will fetch the data from Walrus and display all 100 file actions in a clean, readable table with stats.

---

## 🎬 Demo Video

> 🎥 Video demonstration coming soon! In the meantime, check out the [Screenshots](#-screenshots) above.

### Generate Demo Files

```bash
# Create 50 test files in Downloads
demo.bat

# Or manually:
python demo_generator.py ~/Downloads 50
```

---

## 📊 Usage Example

```
╔════════════════════════════════════════════════════════════════════╗
║   DEEPURGE AUTOCLEAN AGENT                                         ║
║   🤖 Sui Hackathon 2026                                            ║
║   👤 Author: Samuel Campozano Lopez                                ║
║   🦭 Powered by Walrus Decentralized Storage                       ║
╚════════════════════════════════════════════════════════════════════╝

🚀 Starting Deepurge AutoClean Agent...
   Watch Folder: C:\Users\Samuel\Downloads
   Organized Folder: C:\Users\Samuel\Downloads\Organized
   Walrus Network: testnet

📁 Setting up folders...
   ✓ C:\Users\Samuel\Downloads\Organized\Images
   ✓ C:\Users\Samuel\Downloads\Organized\Documents
   ✓ C:\Users\Samuel\Downloads\Organized\Videos
   ✅ Folders ready!

🔍 Scanning existing files...

✅ Moved: vacation_photo.jpg
   Category: Images
   Size: 2.5 MB
   New name: 20260209_153045_vacation_photo.jpg

✅ Moved: report.pdf
   Category: Documents
   Size: 156.2 KB
   New name: 20260209_153046_report.pdf

📤 Uploaded 100 actions to Walrus
   Blob ID: 7Xk9...abc123

👁️  Watching for new files...
   Press Ctrl+C to stop
```

---

## 🛠️ Project Structure

```
deepurge-autoclean-agent/
├── 📄 agent.py              # Main agent – file monitoring, organizing & Walrus uploads
├── 📄 classifier.py         # File classification by extension
├── 📄 database.py           # SQLite operations & statistics
├── 📄 walrus_logger.py      # Walrus decentralized storage integration
├── 📄 demo_generator.py     # Generate test files across categories
├── 📄 config.json           # Local configuration (watch ~/Downloads)
├── 📄 config.docker.json    # Docker configuration (watch /data/Downloads)
├── 📄 requirements.txt      # Agent Python dependencies
├── 📄 install.bat           # Windows installer
├── 📄 run.bat               # Start agent script
├── 📄 demo.bat              # Demo file generator script
├── 📄 dashboard.bat         # Dashboard launcher (local)
├── 📄 Dockerfile.dashboard  # Full-stack Docker image (agent + dashboard)
├── 📄 docker-compose.yml    # Docker Compose – mounts real Downloads folder
├── 📄 .dockerignore         # Docker build exclusions
├── 📁 img/                  # Screenshots for README
│   ├── 🖼️ after agent download folder.png
│   ├── 🖼️ downloads folder with information.png
│   ├── 🖼️ in progress agent done.png
│   ├── 🖼️ in progress agent.png
│   └── 🖼️ in progress running agent.png
├── 📁 dashboard/            # Web dashboard + Control Panel
│   ├── 📄 app.py            # Flask backend + ProcessManager (agent controller)
│   ├── 📄 requirements.txt  # Dashboard dependencies
│   ├── 📁 templates/
│   │   └── 📄 index.html    # Main dashboard page (5 views)
│   └── 📁 static/
│       ├── 📁 css/style.css  # Dark theme stylesheet
│       └── 📁 js/app.js      # Frontend logic + agent control
├── 📄 README.md             # This file
└── 📄 .gitignore            # Git ignore rules
```

---

## 🔧 Running as Windows Service

### Using Task Scheduler

1. Open **Task Scheduler** (taskschd.msc)
2. Create Basic Task → "Deepurge AutoClean Agent"
3. Trigger: "When the computer starts"
4. Action: Start a program
   - Program: `C:\path\to\venv\Scripts\pythonw.exe`
   - Arguments: `agent.py`
   - Start in: `C:\path\to\deepurge-autoclean-agent`
5. Finish and enable

### Using NSSM (Recommended)

```bash
# Install NSSM
choco install nssm

# Create service
nssm install DeepurgeAgent "C:\path\to\venv\Scripts\python.exe" "agent.py"
nssm set DeepurgeAgent AppDirectory "C:\path\to\deepurge-autoclean-agent"
nssm set DeepurgeAgent Start SERVICE_AUTO_START

# Start service
nssm start DeepurgeAgent
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

MIT License - feel free to use this project for any purpose.

---

## 🏆 Built for x OpenClaw Agent Hackathon

This project demonstrates integration with:

- **Walrus Storage** - Decentralized blob storage on Sui
- **Sui Network** - Layer 1 blockchain foundation
- **Python Ecosystem** - Modern file monitoring and processing
- **Web Dashboard** - Containerized Walrus blob viewer

### Hackathon Requirements Met

✅ Monitor Downloads folder (real filesystem via Docker volumes)  
✅ Classify files automatically into 7 categories  
✅ Move & rename to organized folders with timestamps  
✅ Log all actions to Walrus decentralized storage  
✅ Web dashboard with stat cards, charts & Walrus blob explorer  
✅ Control Panel UI to start/stop agent & generate demo files  
✅ Full-stack Docker containerization (agent + dashboard)  
✅ README with author name, screenshots & documentation  
✅ Clean, documented code  
✅ Demo file generator  
✅ Windows 11 compatible  

---

<div align="center">

**Made with ❤️ by Samuel Campozano Lopez**

[⭐ Star this repo](https://github.com/samuelcampozano/deepurge-autoclean-agent) | [🐛 Report Bug](https://github.com/samuelcampozano/deepurge-autoclean-agent/issues) | [✨ Request Feature](https://github.com/samuelcampozano/deepurge-autoclean-agent/issues)

**🦭 Powered by Walrus Decentralized Storage on Sui**

</div>
