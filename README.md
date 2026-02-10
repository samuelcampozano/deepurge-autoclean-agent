# 🤖 Deepurge AutoClean Agent

<div align="center">

![Deepurge Banner](https://img.shields.io/badge/Sui-Hackathon%202026-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-green?style=for-the-badge&logo=python)
![Walrus](https://img.shields.io/badge/Walrus-Enabled-purple?style=for-the-badge)
![Windows](https://img.shields.io/badge/Windows-11-0078D6?style=for-the-badge&logo=windows)

**An autonomous file organization agent that monitors your Downloads folder, automatically classifies and organizes files, and logs all actions to Walrus decentralized storage on the Sui blockchain.**

[Demo Video](#-demo-video) • [Installation](#-quick-start) • [Features](#-features) • [Architecture](#-architecture)

</div>

---

## 👤 Author

**Samuel Campozano Lopez**

- GitHub: [@samuelcampozano](https://github.com/samuelcampozano)
- Email: samuelco860@gmail.com
- Project: Sui Hackathon 2026

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
| 🔄 **Error Recovery** | Retry logic with configurable attempts |
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

## 🎬 Demo Video

> Coming soon - 3-minute demonstration for Sui Hackathon

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
├── 📄 agent.py              # Main agent entry point
├── 📄 classifier.py         # File classification logic
├── 📄 database.py           # SQLite operations
├── 📄 walrus_logger.py      # Walrus storage integration
├── 📄 demo_generator.py     # Test file generator
├── 📄 config.json           # User configuration
├── 📄 requirements.txt      # Python dependencies
├── 📄 install.bat           # Windows installer
├── 📄 run.bat               # Start script
├── 📄 demo.bat              # Demo generator script
├── 📄 README.md             # This file
├── 📄 .gitignore            # Git ignore rules
└── 📁 sui-stack-claude-code-plugin/  # Sui Stack reference
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

## 🏆 Built for Sui Hackathon 2026

This project demonstrates integration with:

- **Walrus Storage** - Decentralized blob storage on Sui
- **Sui Network** - Layer 1 blockchain foundation
- **Python Ecosystem** - Modern file monitoring and processing

### Hackathon Requirements Met

✅ Monitor Downloads folder  
✅ Classify files automatically  
✅ Move to organized folders  
✅ Log actions to Walrus  
✅ README with author name  
✅ Clean, documented code  
✅ Demo file generator  
✅ Windows 11 compatible  

---

<div align="center">

**Made with ❤️ by Samuel Campozano Lopez**

[⭐ Star this repo](https://github.com/samuelcampozano/deepurge-autoclean-agent) | [🐛 Report Bug](https://github.com/samuelcampozano/deepurge-autoclean-agent/issues) | [✨ Request Feature](https://github.com/samuelcampozano/deepurge-autoclean-agent/issues)

**🦭 Powered by Walrus Decentralized Storage on Sui**

</div>
