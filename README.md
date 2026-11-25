# Telegram Bulk Uploader

A fault-tolerant command-line tool built with Python and [Telethon](https://github.com/LonamiWebs/Telethon) to recursively archive large local directories (100GB–500GB+) to Telegram without compression.

## Why Use This?
- **Original Quality Archiving:** Uploads files as uncompressed documents (`force_document=True`) by default to preserve original 4K video bitrates and RAW/high-resolution photo metadata.
- **Automatic Resume:** Tracks uploaded files in `uploaded_state.json`. If your internet drops or you stop the script, re-running skips already-uploaded files.
- **Flood-Limit Protection:** Automatically detects Telegram's `FloodWaitError` and pauses for the exact required cooldown before resuming.
- **Searchable Folder Context:** Automatically captions every file with its immediate parent directory name so you can filter events or folders inside Telegram search.
- **Size Guardrails:** Skips files exceeding Telegram's 2GB (or 4GB Premium) limit and logs them to `skipped_large_files.txt`.

## Prerequisites
1. Python 3.8 or higher.
2. Telegram API credentials (`API_ID` and `API_HASH`) from [my.telegram.org](https://my.telegram.org).
3. *(Optional)* [FFmpeg](https://ffmpeg.org/) (`ffmpeg` and `ffprobe` on `PATH`) if using `--split-large`.

## Installation

```bash
git clone https://github.com/adityaagrawal04/telegram-bulk-uploader.git
cd telegram-bulk-uploader
pip install -r requirements.txt
```

Configure your environment variables:

```bash
cp .env.example .env
```

Open `.env` and add your `API_ID`, `API_HASH`, and `PHONE_NUMBER`.

## Usage

Upload a folder to your Saved Messages (uncompressed):

```bash
python uploader.py "/path/to/your/folder"
```

Upload to a private Telegram Channel or Group:

```bash
python uploader.py "/path/to/your/folder" --target -1001234567890
```

Upload with Telegram Premium (4GB file limit) and filter specific extensions:

```bash
python uploader.py "/path/to/your/folder" --target -1001234567890 --premium --ext .jpg .mp4 .mov
```

## CLI Options

| Flag | Description | Default |
| :--- | :--- | :--- |
| `source` | Path to the local directory to upload | (Required) |
| `-t`, `--target` | `'me'`, `@username`, or numeric chat/channel ID | `me` |
| `--premium` | Raise per-file size limit from 2GB to 4GB | `False` |
| `--compress` | Send media as compressed streamable photos/videos | `False` |
| `--ext` | Space-separated list of file extensions to include | All files |
| `--delay` | Seconds to wait between consecutive uploads | `1.5` |
| `--split-large` | Losslessly split oversized videos into chunks via FFmpeg | `False` |

## Security Note
Never share or commit your `.env` or `*.session` files. Both are excluded in `.gitignore` by default.

## License
MIT
