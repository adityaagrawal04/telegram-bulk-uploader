# Telegram Bulk Uploader

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Powered by Telethon](https://img.shields.io/badge/Telethon-1.36%2B-2CA5E0.svg)](https://github.com/LonamiWebs/Telethon)

A fault-tolerant, resumable Python CLI tool built on [Telethon](https://github.com/LonamiWebs/Telethon) to recursively archive large local photo, video, and document libraries (100GB–500GB+) to Telegram without compression.

---

## Features

- **Original Quality Archiving:** Uploads files as uncompressed documents (`force_document=True`) by default to preserve original 4K video bitrates, RAW photos, and metadata.
- **Automatic Resume:** Tracks every completed file in `uploaded_state.json`. If your connection drops or you stop the script (`Ctrl+C`), re-running skips already-uploaded files.
- **Lossless FFmpeg Splitting (`--split-large`):** Automatically splits oversized videos (>2GB, or >4GB with `--premium`) into lossless chunks using FFmpeg stream copy (`-c copy`) before uploading, then cleans up temporary parts.
- **Flood-Limit Protection:** Detects Telegram's `FloodWaitError`, pauses for the exact required cooldown (+5s buffer), and resumes automatically.
- **Searchable Folder Context:** Captions each upload with its immediate parent folder and filename (`📁 <folder>\n📄 <file>`) so you can search events or albums directly inside Telegram.
- **Flexible Filtering & Guardrails:** Filter by file extensions (`--ext`), customize upload delays (`--delay`), toggle media compression (`--compress`), and log any unuploadable oversized files to `skipped_large_files.txt`.

---

## Prerequisites

1. **Python 3.8+**
2. **Telegram API Credentials** (`API_ID` and `API_HASH`) from [my.telegram.org](https://my.telegram.org) -> *API development tools*.
3. *(Optional)* **[FFmpeg](https://ffmpeg.org/download.html)** (`ffmpeg` and `ffprobe` on your system `PATH`) — required only if you use `--split-large`.

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/adityaagrawal04/telegram-bulk-uploader.git
   cd telegram-bulk-uploader
   ```

2. Create and activate a virtual environment:
   - **Windows (PowerShell):**
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure your credentials:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your Telegram credentials:
   ```env
   API_ID=12345678
   API_HASH=your_api_hash_here
   PHONE_NUMBER=+1234567890
   ```
   > On first run, Telethon will prompt you for the login verification code sent to your Telegram app (and your 2FA password, if enabled) and save a local `telegram_uploader_session.session` file.

---

## Usage

### Upload a folder to Saved Messages (uncompressed)
```bash
python uploader.py "/path/to/your/folder"
```

### Upload to a private Telegram Channel or Group
```bash
python uploader.py "/path/to/your/folder" --target -1001234567890
```

### Upload with Telegram Premium (4GB limit) and extension filtering
```bash
python uploader.py "/path/to/your/folder" --target -1001234567890 --premium --ext .jpg .mp4 .mov
```

### Auto-split oversized videos losslessly with FFmpeg
```bash
python uploader.py "/path/to/your/folder" --target -1001234567890 --split-large
```

### Upload as compressed, streamable Telegram media with a custom delay
```bash
python uploader.py "/path/to/your/folder" --compress --delay 2.5
```

---

## CLI Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `source` | Path to the local directory to upload | *(Required)* |
| `-t`, `--target` | Target chat: `'me'`, `@username`, or numeric chat/channel ID | `me` |
| `--premium` | Raise per-file size limit from 2GB to 4GB (Telegram Premium) | `False` |
| `--compress` | Send media as compressed streamable photos/videos | `False` |
| `--ext` | Space-separated list of file extensions to include (e.g. `.jpg .mp4`) | All files |
| `--delay` | Seconds to wait between consecutive uploads | `1.5` |
| `--split-large` | Losslessly split oversized video files into chunks via FFmpeg | `False` |

---

## How It Works

1. **Discovery:** Recursively walks `source` in sorted order, skipping hidden files (`.DS_Store`, dotfiles) and Windows system metadata (`Thumbs.db`, `desktop.ini`).
2. **Resume State:** Relative file paths are saved to `uploaded_state.json` after each successful upload.
3. **Oversized Files:**
   - Without `--split-large`: Files larger than 2GB (or 4GB with `--premium`) are skipped and recorded in `skipped_large_files.txt`.
   - With `--split-large`: Supported video formats (`.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`, `.flv`, `.wmv`, `.m4v`, `.ts`, `.mts`, `.m2ts`) are probed with `ffprobe`, split losslessly into temporary chunks targeting 90% of the size limit, uploaded sequentially with `(Part X/Y)` captions, and cleaned up automatically.
4. **Rate-Limit & Error Recovery:** Automatically waits on `FloodWaitError` and retries transient network errors every 10 seconds.

---

## Running Tests

Run the unit test suite (includes an FFmpeg splitting test if `ffmpeg` and `ffprobe` are installed):

```bash
python -m unittest discover -s tests -v
```

---

## Security Note

Never commit or share your `.env` file or `*.session` / `*.session-journal` files — they contain your Telegram API credentials and active login session. Both are excluded in [.gitignore](.gitignore) by default.

---

## Author

**Aditya Sanjay Agrawal**
- GitHub: [@adityaagrawal04](https://github.com/adityaagrawal04)

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
