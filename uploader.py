import os
import json
import math
import shutil
import asyncio
import argparse
import subprocess
import tempfile
from dotenv import load_dotenv
from tqdm import tqdm
from telethon import TelegramClient, errors

load_dotenv()

STATE_FILE = "uploaded_state.json"
SKIPPED_LOG = "skipped_large_files.txt"
VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".ts", ".mts", ".m2ts"
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fault-tolerant CLI tool to bulk upload large local folders to Telegram."
    )
    parser.add_argument(
        "source",
        help="Path to the local directory containing files to upload",
    )
    parser.add_argument(
        "-t",
        "--target",
        default="me",
        help="Target chat: 'me' (Saved Messages), @username, or numeric channel/group ID (default: me)",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Allow Telegram media compression instead of uploading as original uncompressed documents",
    )
    parser.add_argument(
        "--premium",
        action="store_true",
        help="Set max file size limit to 4GB (for Telegram Premium accounts) instead of 2GB",
    )
    parser.add_argument(
        "--ext",
        nargs="+",
        default=None,
        help="Filter by specific file extensions (e.g., --ext .jpg .mp4 .mov)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Delay in seconds between uploads to avoid rate limits (default: 1.5)",
    )
    parser.add_argument(
        "--split-large",
        action="store_true",
        help="Losslessly split video files exceeding the size limit into chunks using FFmpeg before uploading",
    )
    return parser.parse_args()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_state(uploaded_set):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(uploaded_set), f, indent=2)


def get_all_files(root_dir, allowed_exts=None):
    file_list = []
    normalized_exts = (
        {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_exts}
        if allowed_exts
        else None
    )

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.startswith(".") or file.lower() in {"thumbs.db", "desktop.ini"}:
                continue
            if normalized_exts:
                _, ext = os.path.splitext(file)
                if ext.lower() not in normalized_exts:
                    continue
            file_list.append(os.path.join(root, file))

    file_list.sort()
    return file_list


def log_skipped_file(rel_path, file_size, limit_gb, reason=None):
    """Log a skipped oversized file to stdout and SKIPPED_LOG."""
    suffix = f" ({reason})" if reason else ""
    print(f"[SKIPPED > {limit_gb}GB] {rel_path} ({file_size / (1024**3):.2f} GB){suffix}")
    with open(SKIPPED_LOG, "a", encoding="utf-8") as log:
        log.write(f"{rel_path} - {file_size / (1024**3):.2f} GB{suffix}\n")


def get_video_duration(file_path):
    """Return video duration in seconds using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def split_video_file(file_path, output_dir, max_file_size):
    """Losslessly split a video file into chunks under max_file_size using FFmpeg."""
    file_size = os.path.getsize(file_path)
    duration = get_video_duration(file_path)
    if duration <= 0:
        raise ValueError(f"Invalid video duration ({duration}s) for {file_path}")

    # Target 90% of max_file_size per chunk to leave headroom for keyframe alignment and VBR spikes
    target_chunk_size = int(max_file_size * 0.90)
    num_chunks = max(2, math.ceil(file_size / target_chunk_size))
    segment_time = max(1, int(duration / num_chunks))

    stem, ext = os.path.splitext(os.path.basename(file_path))
    output_pattern = os.path.join(output_dir, f"{stem}_part%03d{ext}")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            file_path,
            "-c",
            "copy",
            "-map",
            "0:v?",
            "-map",
            "0:a?",
            "-map",
            "0:s?",
            "-f",
            "segment",
            "-segment_time",
            str(segment_time),
            "-reset_timestamps",
            "1",
            output_pattern,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    chunks = sorted(
        os.path.join(output_dir, name)
        for name in os.listdir(output_dir)
        if os.path.isfile(os.path.join(output_dir, name))
    )
    return chunks


async def upload_file_with_retry(
    client, target, file_path, caption, force_document, delay, desc_label, rel_path
):
    """Upload a single file with tqdm progress bar and FloodWait/error retries."""
    file_size = os.path.getsize(file_path)
    while True:
        try:
            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc=desc_label,
            ) as pbar:

                def progress_callback(current, total):
                    pbar.n = current
                    pbar.refresh()

                await client.send_file(
                    target,
                    file_path,
                    caption=caption,
                    force_document=force_document,
                    part_size_kb=512,
                    progress_callback=progress_callback,
                )

            await asyncio.sleep(delay)
            return

        except errors.FloodWaitError as e:
            print(f"\n[RATE LIMIT] Telegram requested a {e.seconds}s pause. Waiting...")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            print(f"\n[ERROR] Failed uploading {rel_path}: {e}. Retrying in 10s...")
            await asyncio.sleep(10)


async def main():
    args = parse_args()

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE_NUMBER")

    if not api_id or not api_hash:
        raise EnvironmentError(
            "Missing API_ID or API_HASH. Copy .env.example to .env and add your credentials from https://my.telegram.org"
        )

    if not os.path.exists(args.source):
        raise FileNotFoundError(f"Source directory does not exist: {args.source}")

    if args.split_large and (not shutil.which("ffmpeg") or not shutil.which("ffprobe")):
        raise EnvironmentError(
            "FFmpeg and ffprobe are required for --split-large. Install FFmpeg and ensure it is on your PATH."
        )

    max_file_size = (4 if args.premium else 2) * 1024 * 1024 * 1024
    limit_gb = 4 if args.premium else 2
    force_document = not args.compress
    chat_target = int(args.target) if args.target.lstrip("-").isdigit() else args.target

    client = TelegramClient("telegram_uploader_session", int(api_id), api_hash)
    await client.start(phone=phone)
    print("Connected to Telegram successfully.")

    target = await client.get_input_entity(chat_target)
    uploaded_files = load_state()
    all_files = get_all_files(args.source, args.ext)

    print(f"Total matching files: {len(all_files)}")
    print(f"Already uploaded:     {len(uploaded_files)}")
    print(f"Remaining to upload:  {max(0, len(all_files) - len(uploaded_files))}\n")

    for index, file_path in enumerate(all_files, start=1):
        rel_path = os.path.relpath(file_path, args.source)

        if rel_path in uploaded_files:
            continue

        file_size = os.path.getsize(file_path)

        if file_size == 0:
            continue

        folder_name = os.path.basename(os.path.dirname(file_path))
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_name)

        if file_size > max_file_size:
            if not args.split_large or ext.lower() not in VIDEO_EXTENSIONS:
                reason = "not a supported video" if args.split_large else None
                log_skipped_file(rel_path, file_size, limit_gb, reason)
                continue

            print(f"[SPLITTING > {limit_gb}GB] {rel_path} ({file_size / (1024**3):.2f} GB)...")
            with tempfile.TemporaryDirectory() as tmpdir:
                try:
                    chunks = split_video_file(file_path, tmpdir, max_file_size)
                except Exception as e:
                    log_skipped_file(rel_path, file_size, limit_gb, f"split failed: {e}")
                    continue

                oversized_chunks = [c for c in chunks if os.path.getsize(c) > max_file_size]
                if not chunks or oversized_chunks:
                    log_skipped_file(
                        rel_path,
                        file_size,
                        limit_gb,
                        "chunk still exceeds size limit after splitting",
                    )
                    continue

                total_parts = len(chunks)
                for part_idx, chunk_path in enumerate(chunks, start=1):
                    chunk_caption = f"📁 {folder_name}\n📄 {file_name} (Part {part_idx}/{total_parts})"
                    desc_label = f"[{index}/{len(all_files)}] {file_name[:18]} ({part_idx}/{total_parts})"
                    await upload_file_with_retry(
                        client,
                        target,
                        chunk_path,
                        chunk_caption,
                        force_document,
                        args.delay,
                        desc_label,
                        f"{rel_path} [part {part_idx}/{total_parts}]",
                    )

            uploaded_files.add(rel_path)
            save_state(uploaded_files)
            continue

        caption = f"📁 {folder_name}\n📄 {file_name}"
        desc_label = f"[{index}/{len(all_files)}] {file_name[:25]}"
        await upload_file_with_retry(
            client,
            target,
            file_path,
            caption,
            force_document,
            args.delay,
            desc_label,
            rel_path,
        )

        uploaded_files.add(rel_path)
        save_state(uploaded_files)

    print("\nUpload queue complete!")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
