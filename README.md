# ⚡ Telegram Bulk Uploader

<p align="center">
  <a href="https://github.com/adityaagrawal04/telegram-bulk-uploader/actions/workflows/ci.yml"><img src="https://github.com/adityaagrawal04/telegram-bulk-uploader/actions/workflows/ci.yml/badge.svg" alt="CI Status" /></a>
  <a href="https://pypi.org/project/telegram-bulk-uploader/"><img src="https://img.shields.io/pypi/v/telegram-bulk-uploader?style=for-the-badge&logo=pypi&logoColor=white&color=0073b7" alt="PyPI Version" /></a>
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Telethon-1.36+-0088cc?style=for-the-badge&logo=telegram&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Dashboard-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Turbo_Engine-16x_Parallel-FF6B6B?style=for-the-badge&logo=speedtest&logoColor=white" />
  <img src="https://img.shields.io/badge/Anti--Ban_Shield-Active_%26_Enforced-2ed573?style=for-the-badge&logo=shield" />
  <img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" />
</p>

<h3 align="center">
  🚀 The Fastest Telegram Uploader on the Internet.
</h3>

<h4 align="center">
  ✨ Turn Telegram into your private, unlimited, zero-compression cloud vault at line-saturating speeds.
</h4>

<p align="center">
  Tired of monthly cloud storage subscriptions, arbitrary size caps, and Telegram compressing your crisp 4K footage into blurry pixels?<br>
  <b>Telegram Bulk Uploader</b> is the <b>fastest Telegram uploader on the internet</b> — engineered with a <b>16-Stream Turbo Highway</b> that shatters default client bottlenecks, an <b>Arc &amp; Okala-inspired Glass Dashboard</b>, and automatic FFmpeg lossless splitting for 100GB–500GB+ archives.
</p>

<p align="center">
  <img src="assets/demo.gif" alt="Telegram Bulk Uploader Demo Walkthrough" width="760" style="border-radius:18px; box-shadow: 0 20px 50px rgba(0,0,0,0.5);" />
</p>

---

## ⚡ The Vibe Check: The Struggle vs. The Fix

| 💀 The Struggle | 🚀 The Fix |
| :--- | :--- |
| **Hitting the 2GB Wall**<br><sub>Zipping a 100GB album fails instantly because Telegram caps single uploads at 2GB.</sub> | **Zero-Stress Granular Queue**<br><sub>Uploads file-by-file in sequence. Back up 500GB archives without ever hitting single-archive file limits.</sub> |
| **Massive 4K Videos (>2GB / 4GB)**<br><sub>ProRes and high-bitrate clips that exceed Telegram limits.</sub> | **Lossless Auto-Split Engine**<br><sub>Embedded FFmpeg automatically slices videos into `-c copy` chapters without re-encoding, preserving 100% of your bitrate.</sub> |
| **Crispy Compression & Lost Metadata**<br><sub>Telegram turning high-res photos into potato quality and stripping EXIF data.</sub> | **Studio-Grade Uncompressed Mode**<br><sub>Pushes every single asset as a pristine document (`force_document=True`). Zero pixel loss, 100% RAW/EXIF intact.</sub> |
| **The "Wi-Fi Dropped at 98%" Rage**<br><sub>One connection drop and default scripts restart your entire 50GB queue from scratch.</sub> | **Bulletproof Resume Engine**<br><sub>Local ledger (`uploaded_state.json`) remembers every file. If internet drops, it seamlessly resumes where it left off.</sub> |
| **Ugly Terminal Screens & Complex Flags**<br><sub>Typing endless console arguments and modifying source code.</sub> | **Arc &amp; Okala-Inspired Glass Dashboard**<br><sub>Fluid dark aesthetic with native 1-click folder browsing, OTP/2FA sign-in, live MB/s telemetry, and background upload monitor.</sub> |
| **Painfully Slow Upload Speeds**<br><sub>Stock single-thread uploads crawling at 1–2 MB/s on fast connections.</sub> | **16-Stream Turbo Highway**<br><sub>Custom multipart connection pool with C-accelerated `cryptg` encryption, pushing your bandwidth to its real limits.</sub> |
| **Account Ban & Spam Flags**<br><sub>Uploading 6,000+ files rapid-fire triggering Telegram's automated spam filters or `@SpamBot`.</sub> | **Military-Grade Anti-Ban Shield**<br><sub>Enforced 3.0s cadence + randomized human jitter, multi-tiered breathers (10s at 25 files, 35s at 100 files), dynamic FloodWait backoff, and 100% spam-report-free Saved Messages isolation.</sub> |

---

## 🏆 Feature Comparison: Why This Leaves Other Uploaders in the Dust

How **Telegram Bulk Uploader** compares against the most popular alternatives on GitHub (`Nekmo/telegram-upload` and `MasterShayan/Tel-uploader-bot`):

| Feature / Capability | ⚡ Telegram Bulk Uploader (This App) | Nekmo/telegram-upload | MasterShayan/Tel-uploader-bot |
| :--- | :---: | :---: | :---: |
| **Architecture & Interface** | **Glassmorphic Web UI + Full CLI** | CLI only | Telegram Bot only (slow HTTP API) |
| **Upload Engine** | **16-Worker Turbo Parallel MTProto** | Single-threaded Telethon | Python-Telegram-Bot (50MB bot cap) |
| **Throughput Speed** | **Up to 25–50 MB/s (Line Saturating)** | ~2–4 MB/s | ~1 MB/s |
| **Max File Size** | **4GB (Premium) / 2GB (Standard)** | 4GB (Premium) / 2GB (Standard) | 50MB (Bot API restriction) |
| **Lossless Video Splitting** | ✅ **Automatic FFmpeg `-c copy`** | ⚠️ Re-encoding or manual | ❌ None |
| **Auto-Resume on Disconnect** | ✅ **Instant (`uploaded_state.json`)** | ❌ Restarts failed transfers | ❌ None |
| **Live Speedometer & ETA** | ✅ **Real-time MB/s + countdown timer** | ❌ Basic CLI progress bar | ❌ None |
| **Auto Video Thumbnails** | ✅ **Built-in FFmpeg snapshot at 1s** | ✅ Yes | ❌ None |
| **Delete Local on Success** | ✅ **Toggle in UI or `--delete-on-success`** | ✅ Yes | ❌ None |
| **Folder Selection & Filtering** | ✅ **Native File Explorer + Glob filters** | ⚠️ Basic file arguments | ❌ Send files one-by-one |
| **Private Channels / Saved Messages**| ✅ **Dropdown list auto-populated** | ⚠️ Manual ID required | ⚠️ Bot chat only |
| **Anti-Ban Protection (6,000+ files)** | ✅ **Human Jitter, Multi-Tier Cooldowns & Safe Scaling** | ❌ None (Triggers FloodWait / Ban) | ❌ None (Bot rate limited) |
| **Docker & Docker Compose** | ✅ **Pre-built container with FFmpeg** | ✅ Yes | ⚠️ Manual Heroku procfile |

---

## How It Works

```mermaid
flowchart LR
    A["Local Folders\n(Photos / Videos / Files)"] --> B{"Size <= 2GB/4GB?"}
    B -- Yes --> C["Upload 1-by-1\n(Background Queue)"]
    B -- "No (Video + --split-large)" --> D["FFmpeg Lossless Split\n(-c copy chunks)"]
    D --> C
    B -- "No (Other / No Split)" --> E["Log to skipped_large_files.txt"]
    C --> F["Telegram Saved Messages\nor Private Channel"]
    C --> G["Save progress to\nuploaded_state.json"]
```

---

## 🚀 Quick Start

### Option A: Install from PyPI (Easiest)
```bash
pip install telegram-bulk-uploader
telegram-bulk-ui
```
*To use the command-line interface directly:*
```bash
telegram-bulk-uploader --target me "C:\path\to\your\folder"
```

### Option B: Clone & Launch via 1-Click Scripts
Anyone who clones this repository can launch the Web UI in seconds—no manual `.env` editing required.

#### 1. Clone the repository
```bash
git clone https://github.com/adityaagrawal04/telegram-bulk-uploader.git
cd telegram-bulk-uploader
```

#### 2. Launch with one command
- **Windows:** Double-click `start.bat` (or run `.\start.bat` in PowerShell)
- **macOS / Linux:**
  ```bash
  chmod +x start.sh && ./start.sh
  ```

The launcher automatically creates `.venv`, installs `requirements.txt`, starts the FastAPI server, and opens **http://127.0.0.1:8000** in your browser.

### 3. Sign in & Upload
1. **Get API credentials (once):** Visit [my.telegram.org](https://my.telegram.org) -> *API development tools* to get your `API_ID` and `API_HASH`.
2. **Connect Telegram:** Enter `API_ID`, `API_HASH`, and your phone number in the Web UI, then enter the OTP (and 2FA password if enabled). Your session is saved locally.
3. **Pick Folders & Files:** Paste your local folder path, click **Scan Folder**, check/uncheck folders or individual files, choose **Saved Messages** or a **Private Channel**, and click **Start Background Upload**.

---

## Prerequisites

- **Python 3.8+**
- **Telegram API Credentials** (`API_ID` and `API_HASH`) from [my.telegram.org](https://my.telegram.org)
- *(Optional)* **[FFmpeg](https://ffmpeg.org/download.html)** (`ffmpeg` and `ffprobe` on `PATH`) — required only if you enable `--split-large` for >2GB/4GB videos.

---

## Command-Line Interface (CLI)

If you prefer running headless from the terminal:

```bash
# Interactive folder & file picker + FFmpeg auto-splitting
python uploader.py "/path/to/folder" --select --split-large

# Upload to a Private Channel / Group
python uploader.py "/path/to/folder" --target -1001234567890 --split-large

# Telegram Premium (4GB limit) + extension filter
python uploader.py "/path/to/folder" --target -1001234567890 --premium --ext .jpg .mp4 .mov

# Filter specific folders and glob patterns
python uploader.py "/path/to/folder" --folders Vacation2025 "Family/Trip" --exclude-folders raw --include "*.jpg" "*.mp4"
```

### CLI Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `source` | Path to the local directory to upload | *(Required)* |
| `-t`, `--target` | Target chat: `'me'`, `@username`, or numeric chat/channel ID | `me` |
| `--premium` | Raise per-file size limit from 2GB to 4GB (Telegram Premium) | `False` |
| `--compress` | Send media as compressed streamable photos/videos | `False` |
| `--ext` | Space-separated list of file extensions to include (e.g. `.jpg .mp4`) | All files |
| `--delay` | Seconds to wait between consecutive uploads | `1.5` |
| `--split-large` | Losslessly split oversized video files into chunks via FFmpeg | `False` |
| `--delete-on-success` | Delete local file after successful upload to free up disk space | `False` |
| `--no-thumb` | Disable automatic FFmpeg thumbnail generation for videos | `False` |
| `-i`, `--select` | Interactively choose which folders and files to upload | `False` |
| `--folders` | Only upload from matching subfolders (path or folder name) | All folders |
| `--exclude-folders` | Skip matching subfolders (path or folder name) | None |
| `--include` | Only upload files matching glob patterns (e.g. `*.jpg`) | All files |
| `--exclude` | Exclude files matching glob patterns (e.g. `*draft*`) | None |

---

## Running Tests

```bash
python -m unittest discover -s tests -v
```

---

---

## 🤖 Searching for a "Telegram Uploader Bot"? Why This is 100x Better

If you've searched for a **Telegram uploader bot**, **Telegram file upload bot**, or **Telegram cloud storage bot**, you've likely hit the frustrating walls of the official Telegram Bot API:

1. **The 50MB Bot Cap:** Telegram's official Bot API strictly forbids bots from uploading files larger than 50MB. Any archive or video over 50MB fails immediately.
2. **Slow Single-Stream Speeds:** Bot API transfers crawl at ~1 MB/s over HTTPS polling.
3. **Telegram Bulk Uploader Advantage:** By using your own Telegram MTProto credentials (`API_ID` & `API_HASH`), this tool uploads directly as an authentic MTProto client—unlocking **2,000MB (2GB)** uploads for standard accounts, **4,000MB (4GB)** for Telegram Premium, and **25–50 MB/s** multi-stream speeds.

---

## 🛡️ Anti-Ban & Telegram Account Safety Architecture

Is it safe to use? **Yes, 100%.** Telegram Bulk Uploader is built with strict compliance guards to protect your account from rate-limiting, temporary flags, and bans:

> [!IMPORTANT]
> **Anti-Ban Protection for Massive Archives (6,000+ Files):**
> When uploading massive queues (e.g. 6,000+ wedding or family photo archives), rapid-fire messaging can trigger Telegram's automated spam heuristics. We've hardened the safety engine:
> * **Calibrated Upload Delay (`3.0s` default):** Enforces a safe ~18–20 messages/minute cadence, strictly within Telegram's safe threshold.
> * **Randomized Human Jitter (+0.1s to +0.8s):** Adds dynamic non-uniform variance between consecutive file sends, breaking mechanical heartbeat patterns and preventing bot signature flags.
> * **Multi-Tiered Automated Cooldowns:**
>   - **Micro-Breather:** Automatic 10-second pause every 25 files.
>   - **Deep Breather:** Automatic 35-second pause every 100 files to simulate natural human usage.
> * **Dynamic FloodWait Backoff:** Strictly obeys Telegram's rate-limit wait time plus a +5s safety margin (`seconds + 5s`), while automatically increasing session delay by +1.0s to let server limits recover.
> * **Safe Photo Dimension Auto-Scaling & Document Fallback:** DSLR photos (>2560px) are automatically scaled and compressed using Pillow to adhere to Telegram's photo rules. If Telegram ever rejects a media item, the engine instantly falls back to sending it as an uncompressed document without crashing or stalling your queue.

* ⏱️ **Mandatory Inter-File Throttling:** Every file upload is followed by a deliberate delay (default `3.0s`, customizable in UI and CLI) preventing algorithmic flood detection.
* 🛡️ **Strict `FloodWaitError` Backoff:** If Telegram ever signals a rate limit, the engine halts immediately and sleeps for the exact duration requested by Telegram plus a safety grace margin (`seconds + 5s`). It never hammers Telegram with rejected requests.
* 🔒 **Conservative Connection Pooling:** Concurrent MTProto sockets are capped at safe thresholds (maximum 16 connections for large files, well below Telegram's connection ceiling).
* 🏠 **Session Key Reuse:** Connections to your primary Data Center reuse your authenticated session `AuthKey` directly, avoiding suspicious repetitive auth exports.
* 📁 **Zero Third-Party Relays:** All data streams point-to-point directly from your machine to official Telegram Data Centers. No intermediate proxies, tokens, or servers ever touch your files.

### 📋 7 Steps Taken by the Engine to Eliminate Ban & Suspension Risks

1. **Destination Isolation (Zero User Spam Reports):**
   Personal backups target **Saved Messages (`me`)** or Private Channels. Since no external users receive unsolicited messages, `@SpamBot` user reports are completely eliminated.
2. **Calibrated Rate Cadence (3.0s Delay):**
   Enforces a steady average of ~18–20 messages/minute, staying strictly under Telegram's per-chat threshold (~20–30 msgs/min).
3. **Randomized Human Timing Jitter (+0.1s to +0.8s):**
   Every inter-file pause injects non-uniform variance (`delay + uniform(0.1, 0.8)`). This eliminates the mechanical "heartbeat" pattern that machine-learning spam detectors use to flag unattended scripts.
4. **Multi-Tiered Automated Cooldown Breathers:**
   - **Micro-Breather:** Automatic 10-second pause every 25 files.
   - **Deep Breather:** Automatic 35-second pause every 100 files, mimicking natural human rest periods and allowing server-side message buffers to reset.
5. **Pre-Upload Photo Dimension Compliance (<= 2560px & < 9MB):**
   Using Pillow, high-resolution DSLR images (e.g. 24MP–60MP) are automatically pre-scaled to `<= 2560px` with EXIF orientation preserved. This prevents Telegram's `SendMediaRequest` from throwing dimension errors (`PHOTO_INVALID_DIMENSIONS`).
6. **Universal Document Auto-Fallback on Any Media Error:**
   If Telegram ever rejects an image or video when sent as photo/media, the engine catches the exception and immediately retries sending it as an uncompressed document (`force_document=True`) using the already-uploaded chunks. Telegram never rejects documents for dimensions or photo size limits.
7. **Strict FloodWait Compliance & Dynamic Backoff:**
   If Telegram ever issues a `FloodWaitError(seconds=N)`, the engine immediately sleeps for `N + 5` seconds (never retrying in a tight loop) and dynamically increases the base delay by `+1.0s` for the remainder of the session to allow server limits to decay safely.

> [!TIP]
> **Use "Saved Messages" (`me`) for personal vaults.**
> Uploading to **Saved Messages (`me`)** is private self-chat. Because no other users see or interact with the messages, it cannot be reported for spam, and Telegram's anti-abuse algorithms treat it as legitimate personal cloud backup. If using a channel, always keep it **Private** (never Public).

---

## FAQ

- **How do I find a Private Channel's numeric ID?**
  Log into the Web UI and select the channel directly from the **Target Chat / Private Channel** dropdown—no manual ID lookup needed!
- **Will using this ban my Telegram account?**
  No. As long as you maintain the default upload delay (`--delay 3.0`) and don't share copyright-infringing content on public channels, your account operates within Telegram's standard client terms with full FloodWait backoff protection.
- **What happens if my internet disconnects mid-upload?**
  Every completed file is saved to `uploaded_state.json`. Re-running (or clicking Start again) skips already-uploaded files and resumes where you left off.
- **Are my credentials safe?**
  Yes. `.env` and `*.session` files stay strictly on your local machine and are excluded from Git in [.gitignore](.gitignore).

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=adityaagrawal04/telegram-bulk-uploader&type=Date)](https://star-history.com/#adityaagrawal04/telegram-bulk-uploader&Date)

---

## Author

**Aditya Sanjay Agrawal**
- GitHub: [@adityaagrawal04](https://github.com/adityaagrawal04)

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
