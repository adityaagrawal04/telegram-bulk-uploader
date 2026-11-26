import os
import json
import math
import shutil
import asyncio
import fnmatch
import argparse
import subprocess
import tempfile
from dotenv import load_dotenv
from tqdm import tqdm
from telethon import TelegramClient, errors
from fast_telethon import fast_upload_file

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
    parser.add_argument(
        "--folders",
        nargs="+",
        default=None,
        help="Only upload from these subfolders (relative path or folder name)",
    )
    parser.add_argument(
        "--exclude-folders",
        nargs="+",
        default=None,
        help="Skip these subfolders (relative path or folder name)",
    )
    parser.add_argument(
        "--include",
        nargs="+",
        default=None,
        help="Only upload files matching glob patterns (e.g., --include '*.jpg' 'IMG_*')",
    )
    parser.add_argument(
        "--exclude",
        nargs="+",
        default=None,
        help="Exclude files matching glob patterns (e.g., --exclude '*.tmp' '*draft*')",
    )
    parser.add_argument(
        "-i",
        "--select",
        action="store_true",
        help="Interactively choose which folders and files to upload before starting",
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


def _normalize_folder_filters(folders):
    """Normalize folder filter strings to POSIX relative style."""
    if not folders:
        return None
    return [f.replace("\\", "/").strip("/") for f in folders if f.strip("/\\")]


def _folder_matches(rel_dir, folder_filters):
    """Return True if rel_dir matches any folder filter (exact, prefix, or segment)."""
    if rel_dir == ".":
        return "." in folder_filters
    parts = rel_dir.split("/")
    for target in folder_filters:
        if rel_dir == target or rel_dir.startswith(f"{target}/") or target in parts:
            return True
    return False


def _matches_any_glob(file_name, rel_file, patterns):
    """Return True if file_name or rel_file matches any glob pattern (case-insensitive)."""
    name_lower = file_name.lower()
    rel_lower = rel_file.lower()
    return any(
        fnmatch.fnmatch(name_lower, p.lower()) or fnmatch.fnmatch(rel_lower, p.lower())
        for p in patterns
    )


def get_all_files(
    root_dir,
    allowed_exts=None,
    include_folders=None,
    exclude_folders=None,
    include_patterns=None,
    exclude_patterns=None,
):
    """Walk root_dir and return sorted file paths matching extension, folder, and glob filters."""
    file_list = []
    normalized_exts = (
        {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_exts}
        if allowed_exts
        else None
    )
    inc_folders = _normalize_folder_filters(include_folders)
    exc_folders = _normalize_folder_filters(exclude_folders)

    for root, dirs, files in os.walk(root_dir):
        rel_dir = os.path.relpath(root, root_dir).replace("\\", "/")
        if exc_folders:
            dirs[:] = [
                d
                for d in dirs
                if not _folder_matches(
                    d if rel_dir == "." else f"{rel_dir}/{d}", exc_folders
                )
            ]
            if rel_dir != "." and _folder_matches(rel_dir, exc_folders):
                continue

        if inc_folders and not _folder_matches(rel_dir, inc_folders):
            continue

        for file in files:
            if file.startswith(".") or file.lower() in {"thumbs.db", "desktop.ini"}:
                continue
            if normalized_exts:
                _, ext = os.path.splitext(file)
                if ext.lower() not in normalized_exts:
                    continue
            rel_file = file if rel_dir == "." else f"{rel_dir}/{file}"
            if include_patterns and not _matches_any_glob(file, rel_file, include_patterns):
                continue
            if exclude_patterns and _matches_any_glob(file, rel_file, exclude_patterns):
                continue
            file_list.append(os.path.join(root, file))

    file_list.sort()
    return file_list


def format_size(num_bytes):
    """Format byte count as a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            return f"{num_bytes:.2f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024


def parse_selection_indices(raw_input, max_index):
    """Parse 1-based selection input ('all', 'none', or '1,3-5') into sorted 0-based indices."""
    text = raw_input.strip().lower()
    if text in {"", "all", "*"}:
        return list(range(max_index))
    if text in {"none", "0"}:
        return []

    selected = set()
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            parts = token.split("-", 1)
            start, end = int(parts[0]), int(parts[1])
            if start < 1 or end > max_index or start > end:
                raise ValueError(f"Range '{token}' is out of bounds (1-{max_index}).")
            selected.update(range(start - 1, end))
        else:
            idx = int(token)
            if idx < 1 or idx > max_index:
                raise ValueError(f"Index '{idx}' is out of bounds (1-{max_index}).")
            selected.add(idx - 1)
    return sorted(selected)


def _prompt_indices(prompt_text, max_index):
    """Prompt until valid selection indices are entered."""
    while True:
        try:
            return parse_selection_indices(input(prompt_text), max_index)
        except ValueError as e:
            print(f"Invalid selection: {e}")


def interactive_select_files(root_dir, file_list):
    """Interactively let the user select folders and optionally individual files."""
    if not file_list:
        return []

    folders = {}
    for path in file_list:
        rel_dir = os.path.relpath(os.path.dirname(path), root_dir).replace("\\", "/")
        label = "(root)" if rel_dir == "." else rel_dir
        folders.setdefault(label, []).append(path)

    folder_items = sorted(folders.items(), key=lambda kv: kv[0])
    print("\nAvailable folders:")
    for idx, (label, paths) in enumerate(folder_items, start=1):
        total_bytes = sum(os.path.getsize(p) for p in paths)
        print(f"  [{idx}] {label} ({len(paths)} files, {format_size(total_bytes)})")

    chosen_folder_idxs = _prompt_indices(
        "\nSelect folders (e.g. 1,3-5, 'all', or 'none') [all]: ",
        len(folder_items),
    )
    if not chosen_folder_idxs:
        return []

    selected_files = []
    for idx in chosen_folder_idxs:
        selected_files.extend(folder_items[idx][1])
    selected_files.sort()

    pick_files = input("\nSelect individual files within chosen folders? [y/N]: ").strip().lower()
    if pick_files not in {"y", "yes"}:
        return selected_files

    print("\nAvailable files:")
    for idx, path in enumerate(selected_files, start=1):
        rel_path = os.path.relpath(path, root_dir).replace("\\", "/")
        print(f"  [{idx}] {rel_path} ({format_size(os.path.getsize(path))})")

    chosen_file_idxs = _prompt_indices(
        "\nSelect files (e.g. 1,2,4-6, 'all', or 'none') [all]: ",
        len(selected_files),
    )
    return [selected_files[i] for i in chosen_file_idxs]


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
    """Upload a single file with fast parallel chunks, tqdm progress bar, and FloodWait/error retries."""
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

                # Fast parallel multipart upload
                uploaded_input = await fast_upload_file(
                    client,
                    file_path,
                    progress_callback=progress_callback,
                    max_workers=16
                )

                await client.send_file(
                    target,
                    uploaded_input,
                    caption=caption,
                    force_document=force_document,
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

    all_files = get_all_files(
        args.source,
        allowed_exts=args.ext,
        include_folders=args.folders,
        exclude_folders=args.exclude_folders,
        include_patterns=args.include,
        exclude_patterns=args.exclude,
    )
    if args.select:
        all_files = interactive_select_files(args.source, all_files)

    if not all_files:
        print("No matching files selected for upload.")
        return

    client = TelegramClient("telegram_uploader_session", int(api_id), api_hash)
    await client.start(phone=phone)
    print("Connected to Telegram successfully.")

    target = await client.get_input_entity(chat_target)
    uploaded_files = load_state()
    remaining_count = sum(
        1 for f in all_files if os.path.relpath(f, args.source) not in uploaded_files
    )

    print(f"Total matching files: {len(all_files)}")
    print(f"Already uploaded:     {len(all_files) - remaining_count}")
    print(f"Remaining to upload:  {remaining_count}\n")

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
