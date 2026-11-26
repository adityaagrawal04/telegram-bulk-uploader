import os
import sys
import json
import math
import random
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

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".dng", ".cr2", ".nef", ".arw"
}
MAX_IMAGE_COMPRESSED_SIZE = 9 * 1024 * 1024  # 9MB limit

# Conservative Telegram thresholds (2000 MiB / 4000 MiB)
STANDARD_LIMIT = 2000 * 1024 * 1024
PREMIUM_LIMIT = 4000 * 1024 * 1024


def parse_args():
    parser = argparse.ArgumentParser(
        description="The fastest, fault-tolerant CLI tool to bulk upload large local folders to Telegram."
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
        help="Set max file size limit to 4000MB (for Telegram Premium accounts) instead of 2000MB",
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
        default=3.0,
        help="Delay in seconds between uploads to avoid rate limits (default: 3.0)",
    )
    parser.add_argument(
        "--split-large",
        action="store_true",
        help="Losslessly split video files exceeding the size limit into chunks using FFmpeg before uploading",
    )
    parser.add_argument(
        "--delete-on-success",
        action="store_true",
        help="Delete local file after it has been successfully uploaded to Telegram",
    )
    parser.add_argument(
        "--no-thumb",
        action="store_true",
        help="Disable automatic thumbnail generation for uploaded video files",
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


def make_state_key(target: str, rel_path: str, size: int, mtime: float) -> str:
    """Generate a collision-resistant unique key per target, file content size & mtime."""
    posix_path = rel_path.replace("\\", "/")
    return f"{target}::{posix_path}::{size}::{int(mtime)}"


def load_state() -> set:
    """Safely load uploaded state ledger supporting atomic JSON recovery."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception:
            # Fallback for corrupted or empty state
            return set()
    return set()


def save_state(uploaded_set: set):
    """Atomically save uploaded state using temporary file replacement."""
    tmp_path = f"{STATE_FILE}.tmp.{os.getpid()}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(list(uploaded_set), f, indent=2)
        os.replace(tmp_path, STATE_FILE)
    except Exception as e:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def is_file_uploaded(uploaded_set: set, target: str, rel_path: str, size: int, mtime: float) -> bool:
    """Check if file was uploaded either with full key or backward-compatible relative path."""
    full_key = make_state_key(target, rel_path, size, mtime)
    if full_key in uploaded_set:
        return True
    posix_rel = rel_path.replace("\\", "/")
    # Backward compatibility with older single-key records
    return posix_rel in uploaded_set or rel_path in uploaded_set


def _normalize_folder_filters(folders):
    if not folders:
        return None
    return [f.replace("\\", "/").strip("/") for f in folders if f.strip("/\\")]


def _folder_matches(rel_dir, folder_filters):
    if rel_dir == ".":
        return "." in folder_filters
    parts = rel_dir.split("/")
    for target in folder_filters:
        if rel_dir == target or rel_dir.startswith(f"{target}/") or target in parts:
            return True
    return False


def _matches_any_glob(file_name, rel_file, patterns):
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
    """Recursively walk directory, pruning hidden directories (.git, .Trash) and files."""
    file_list = []
    normalized_exts = (
        {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in allowed_exts}
        if allowed_exts
        else None
    )
    inc_folders = _normalize_folder_filters(include_folders)
    exc_folders = _normalize_folder_filters(exclude_folders)

    for root, dirs, files in os.walk(root_dir):
        # Prune hidden directories (.git, .trash, dotfolders)
        dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in {"$recycle.bin", "system volume information"}]

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
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            return f"{num_bytes:.2f} {unit}" if unit != "B" else f"{num_bytes} B"
        num_bytes /= 1024


def parse_selection_indices(raw_input, max_index):
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
    while True:
        try:
            return parse_selection_indices(input(prompt_text), max_index)
        except ValueError as e:
            print(f"Invalid selection: {e}")


def interactive_select_files(root_dir, file_list):
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


def log_skipped_file(rel_path, file_size, limit_mb, reason=None):
    """Log skipped file without repeating duplicates in SKIPPED_LOG."""
    suffix = f" ({reason})" if reason else ""
    posix_path = rel_path.replace("\\", "/")
    print(f"[SKIPPED > {limit_mb}MB] {posix_path} ({file_size / (1024**2):.1f} MB){suffix}")
    line_entry = f"{posix_path} - {file_size / (1024**2):.1f} MB{suffix}\n"

    existing = set()
    if os.path.exists(SKIPPED_LOG):
        try:
            with open(SKIPPED_LOG, "r", encoding="utf-8") as f:
                existing = set(f.readlines())
        except Exception:
            pass

    if line_entry not in existing:
        with open(SKIPPED_LOG, "a", encoding="utf-8") as log:
            log.write(line_entry)


def get_video_duration(file_path):
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


def generate_video_thumbnail(video_path, out_thumb_path):
    if not shutil.which("ffmpeg"):
        return None
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "00:00:01",
                "-i",
                video_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                out_thumb_path,
            ],
            capture_output=True,
            check=True,
            timeout=10,
        )
        if os.path.exists(out_thumb_path) and os.path.getsize(out_thumb_path) > 0:
            return out_thumb_path
    except Exception:
        pass
    return None


def is_ffmpeg_available():
    return bool(shutil.which("ffmpeg"))


def compress_image_below_limit(file_path, output_dir=None, max_bytes=MAX_IMAGE_COMPRESSED_SIZE, max_dim=2560):
    """
    Compress an image to ensure:
    1. Maximum dimension does not exceed max_dim (default 2560px for Telegram Photo compliance).
    2. File size is strictly less than max_bytes (default 9MB).
    Uses Pillow with high-quality resampling and EXIF orientation preservation, with FFmpeg fallback.
    """
    if not os.path.exists(file_path):
        return None

    _, ext = os.path.splitext(file_path)
    if ext.lower() not in IMAGE_EXTENSIONS:
        return None

    file_size = os.path.getsize(file_path)

    if output_dir is None:
        output_dir = tempfile.gettempdir()
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    out_path = os.path.join(output_dir, f"{base_name}_compressed_{os.getpid()}.jpg")

    # Method 1: Try Pillow if available
    try:
        from PIL import Image, ImageOps
        with Image.open(file_path) as img:
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            needs_resize = img.width > max_dim or img.height > max_dim
            needs_compress = file_size > max_bytes

            if not needs_resize and not needs_compress:
                return None

            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")

            if needs_resize:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            # High-fidelity quality ladder: Starts at studio-grade 95% with 4:4:4 full chroma
            # (zero color degradation, lossless visual perception)
            for quality in [95, 92, 90, 88, 85, 80]:
                img.save(out_path, format="JPEG", quality=quality, subsampling=0, optimize=True)
                if os.path.getsize(out_path) <= max_bytes:
                    return out_path

            # If still > max_bytes, gently scale down while retaining high 88% quality
            w, h = img.size
            for scale in [0.90, 0.80, 0.70, 0.60]:
                new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                resized.save(out_path, format="JPEG", quality=88, subsampling=0, optimize=True)
                if os.path.getsize(out_path) <= max_bytes:
                    return out_path

            if os.path.exists(out_path):
                return out_path
    except Exception:
        pass

    # Method 2: FFmpeg fallback with pristine quality (-q:v 2 starting point)
    if is_ffmpeg_available():
        scale_filter = f"scale='min({max_dim},iw)':'min({max_dim},ih)':force_original_aspect_ratio=decrease"
        for q in [2, 3, 4, 5, 8]:
            cmd = ["ffmpeg", "-y", "-i", file_path, "-vf", scale_filter, "-q:v", str(q), "-frames:v", "1", out_path]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) <= max_bytes:
                return out_path
        if os.path.exists(out_path):
            return out_path

    return None


def split_video_file(file_path, output_dir, max_file_size, attempt=1):
    """
    Split a video into lossless chunks with clean audio/video stream selection,
    retrying with tighter segment intervals if variable bitrate exceeds limits.
    """
    file_size = os.path.getsize(file_path)
    duration = get_video_duration(file_path)
    if duration <= 0:
        raise ValueError(f"Invalid video duration ({duration}s) for {file_path}")

    # Use progressively tighter headroom on attempts (85%, 75%, 65%)
    headroom = max(0.50, 0.85 - (attempt - 1) * 0.10)
    target_chunk_size = int(max_file_size * headroom)
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
            "0:v:0",
            "-map",
            "0:a?",
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

    # If any chunk still overshoots, retry with smaller segment_time up to 3 times
    oversized = [c for c in chunks if os.path.getsize(c) > max_file_size]
    if oversized and attempt < 3:
        for c in chunks:
            try:
                os.remove(c)
            except Exception:
                pass
        return split_video_file(file_path, output_dir, max_file_size, attempt=attempt + 1)

    return chunks


async def upload_file_with_retry(
    client, target, file_path, caption, force_document, delay, desc_label, rel_path, delete_on_success=False, no_thumb=False, max_retries=5
):
    """
    Upload a single file with fast parallel chunks.
    Only retries transient network errors or FloodWait. Distinguishes upload phase from send phase.
    """
    file_size = os.path.getsize(file_path)
    _, ext = os.path.splitext(file_path)
    thumb_path = None
    temp_thumb = None

    if not no_thumb and ext.lower() in VIDEO_EXTENSIONS and shutil.which("ffmpeg"):
        temp_thumb = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        temp_thumb.close()
        thumb_path = generate_video_thumbnail(file_path, temp_thumb.name)

    try:
        # Phase 1: Upload chunks to Telegram server
        uploaded_input = None
        for attempt in range(max_retries):
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

                    uploaded_input = await fast_upload_file(
                        client,
                        file_path,
                        progress_callback=progress_callback,
                        max_workers=16
                    )
                break
            except errors.FloodWaitError as e:
                print(f"\n[RATE LIMIT] Telegram requested a {e.seconds}s pause. Waiting...")
                delay = min(delay + 1.0, 10.0)
                await asyncio.sleep(e.seconds + 5)
            except (ConnectionError, asyncio.TimeoutError, OSError, errors.RPCError) as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Gave up uploading chunks for {rel_path}: {e}")
                print(f"\n[NETWORK] Transient chunk failure on {rel_path} ({e}). Retry {attempt+1}/{max_retries} in 5s...")
                await asyncio.sleep(5)

        # Phase 2: Send file message (re-using pre-uploaded input so chunks are never re-sent!)
        for attempt in range(max_retries):
            try:
                await client.send_file(
                    target,
                    uploaded_input,
                    caption=caption,
                    force_document=force_document,
                    thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                )
                break
            except errors.FloodWaitError as e:
                print(f"\n[RATE LIMIT] Telegram requested a {e.seconds}s pause on send_file. Waiting...")
                delay = min(delay + 1.0, 10.0)
                await asyncio.sleep(e.seconds + 5)
            except Exception as e:
                if not force_document:
                    print(f"\n[AUTO-FALLBACK] Photo rejected by Telegram ({e}). Retrying as uncompressed document...")
                    force_document = True
                    continue
                if attempt == max_retries - 1:
                    raise RuntimeError(f"Gave up sending file message for {rel_path}: {e}")
                print(f"\n[NETWORK] Transient message delivery failure on {rel_path} ({e}). Retrying in 5s...")
                await asyncio.sleep(5)

        if delete_on_success:
            try:
                os.remove(file_path)
            except Exception as del_err:
                print(f"\n[WARN] Failed to delete {file_path}: {del_err}")

        # Anti-ban human jitter: random variance to prevent mechanical pulse detection
        jittered_delay = max(1.5, delay + random.uniform(0.1, 0.8))
        await asyncio.sleep(jittered_delay)

    finally:
        if temp_thumb and os.path.exists(temp_thumb.name):
            try:
                os.remove(temp_thumb.name)
            except Exception:
                pass


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

    max_file_size = PREMIUM_LIMIT if args.premium else STANDARD_LIMIT
    limit_mb = 4000 if args.premium else 2000
    force_document = not args.compress
    chat_target = int(args.target) if args.target.lstrip("-").isdigit() else args.target

    client = TelegramClient("telegram_uploader_session", int(api_id), api_hash)
    await client.start(phone=phone)
    print("Connected to Telegram successfully.")

    try:
        # Pre-warm dialog entity cache so numeric IDs (-100...) resolve reliably
        await client.get_dialogs(limit=30)
        target = await client.get_input_entity(chat_target)
        target_str = str(chat_target)

        uploaded_files = load_state()
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

        remaining_files = []
        for f in all_files:
            rel = os.path.relpath(f, args.source)
            st = os.stat(f)
            if not is_file_uploaded(uploaded_files, target_str, rel, st.st_size, st.st_mtime):
                remaining_files.append(f)

        print(f"Total matching files: {len(all_files)}")
        print(f"Already uploaded:     {len(all_files) - len(remaining_files)}")
        print(f"Remaining to upload:  {len(remaining_files)}\n")

        session_uploaded_count = 0
        for index, file_path in enumerate(all_files, start=1):
            # Anti-ban shield: Multi-tiered breathers for account longevity
            if session_uploaded_count > 0:
                if session_uploaded_count % 100 == 0:
                    print(f"\n[ANTI-BAN SHIELD] Deep breather: pausing 35s after {session_uploaded_count} files for account safety...")
                    await asyncio.sleep(35)
                elif session_uploaded_count % 25 == 0:
                    print(f"\n[ANTI-BAN SHIELD] Micro-breather: pausing 10s after {session_uploaded_count} files to keep cadence safe...")
                    await asyncio.sleep(10)

            rel_path = os.path.relpath(file_path, args.source)
            st = os.stat(file_path)
            file_size = st.st_size
            file_mtime = st.st_mtime

            if is_file_uploaded(uploaded_files, target_str, rel_path, file_size, file_mtime):
                continue

            if file_size == 0:
                continue

            folder_name = os.path.basename(os.path.dirname(file_path))
            file_name = os.path.basename(file_path)
            _, ext = os.path.splitext(file_name)

            if file_size > max_file_size:
                if not args.split_large or ext.lower() not in VIDEO_EXTENSIONS:
                    reason = "not a supported video" if args.split_large else None
                    log_skipped_file(rel_path, file_size, limit_mb, reason)
                    continue

                print(f"[SPLITTING > {limit_mb}MB] {rel_path} ({file_size / (1024**2):.1f} MB)...")
                with tempfile.TemporaryDirectory() as tmpdir:
                    try:
                        chunks = split_video_file(file_path, tmpdir, max_file_size)
                    except Exception as e:
                        log_skipped_file(rel_path, file_size, limit_mb, f"split failed: {e}")
                        continue

                    oversized_chunks = [c for c in chunks if os.path.getsize(c) > max_file_size]
                    if not chunks or oversized_chunks:
                        log_skipped_file(
                            rel_path,
                            file_size,
                            limit_mb,
                            "chunk exceeds size limit after splitting",
                        )
                        continue

                    total_parts = len(chunks)
                    for part_idx, chunk_path in enumerate(chunks, start=1):
                        part_rel_key = f"{rel_path}::part{part_idx}_of_{total_parts}"
                        chunk_size = os.path.getsize(chunk_path)
                        # Part-level state tracking: skips already sent parts on interrupted resumes!
                        if is_file_uploaded(uploaded_files, target_str, part_rel_key, chunk_size, file_mtime):
                            continue

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
                            delete_on_success=False,
                            no_thumb=args.no_thumb,
                        )
                        # Immediately record part state
                        uploaded_files.add(make_state_key(target_str, part_rel_key, chunk_size, file_mtime))
                        save_state(uploaded_files)

                if args.delete_on_success:
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

                uploaded_files.add(make_state_key(target_str, rel_path, file_size, file_mtime))
                save_state(uploaded_files)
                session_uploaded_count += 1
                continue

            caption = f"📁 {folder_name}\n📄 {file_name}"
            desc_label = f"[{index}/{len(all_files)}] {file_name[:25]}"

            compressed_temp = None
            upload_target_path = file_path
            if args.compress and ext.lower() in IMAGE_EXTENSIONS:
                comp = compress_image_below_limit(file_path)
                if comp and os.path.exists(comp):
                    compressed_temp = comp
                    upload_target_path = comp
                    print(f"[COMPRESSED] {file_name} -> {os.path.getsize(comp) / (1024*1024):.2f}MB (Telegram Photo compliant)")

            try:
                await upload_file_with_retry(
                    client,
                    target,
                    upload_target_path,
                    caption,
                    force_document,
                    args.delay,
                    desc_label,
                    rel_path,
                    delete_on_success=args.delete_on_success,
                    no_thumb=args.no_thumb,
                )
            finally:
                if compressed_temp and os.path.exists(compressed_temp):
                    try:
                        os.remove(compressed_temp)
                    except Exception:
                        pass

            uploaded_files.add(make_state_key(target_str, rel_path, file_size, file_mtime))
            save_state(uploaded_files)
            session_uploaded_count += 1

        print("\nUpload queue complete!")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
