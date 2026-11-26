import os
import shutil
import asyncio
import tempfile
from collections import deque
from typing import List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telethon import TelegramClient, errors

import uploader

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
SESSION_NAME = os.path.join(BASE_DIR, "telegram_uploader_session")
ENV_PATH = os.path.join(BASE_DIR, ".env")

app = FastAPI(title="Telegram Bulk Uploader UI")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class UploadState:
    """In-memory state for the background upload worker."""

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.pending_phone: Optional[str] = None
        self.pending_phone_hash: Optional[str] = None
        self.task: Optional[asyncio.Task] = None
        self.running: bool = False
        self.total_files: int = 0
        self.completed_files: int = 0
        self.skipped_files: int = 0
        self.current_file: str = ""
        self.current_bytes: int = 0
        self.current_total_bytes: int = 0
        self.status_message: str = "Idle"
        self.logs: deque = deque(maxlen=150)

    def log(self, message: str):
        self.logs.append(message)


state = UploadState()


class SendCodeRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str
    save_env: bool = True


class VerifyCodeRequest(BaseModel):
    code: str
    password: Optional[str] = None


class BrowseRequest(BaseModel):
    source: str
    ext: Optional[List[str]] = None
    include_folders: Optional[List[str]] = None
    exclude_folders: Optional[List[str]] = None
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None


class UploadStartRequest(BaseModel):
    source: str
    selected_files: Optional[List[str]] = None
    target: str = "me"
    compress: bool = False
    premium: bool = False
    split_large: bool = False
    delay: float = 1.5


def _save_env_credentials(api_id: int, api_hash: str, phone: str):
    """Persist credentials to .env so sessions reconnect automatically on restart."""
    content = f"API_ID={api_id}\nAPI_HASH={api_hash}\nPHONE_NUMBER={phone}\n"
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    os.environ["API_ID"] = str(api_id)
    os.environ["API_HASH"] = api_hash
    os.environ["PHONE_NUMBER"] = phone


async def _get_or_create_client(api_id: Optional[int] = None, api_hash: Optional[str] = None):
    """Return a connected TelegramClient if credentials are available."""
    aid = api_id or os.getenv("API_ID")
    ahash = api_hash or os.getenv("API_HASH")
    if not aid or not ahash:
        return None
    if state.client is None or (api_id and api_hash):
        if state.client and state.client.is_connected():
            await state.client.disconnect()
        state.client = TelegramClient(SESSION_NAME, int(aid), str(ahash))
    if not state.client.is_connected():
        await state.client.connect()
    return state.client


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/auth/status")
async def auth_status():
    api_id = os.getenv("API_ID", "")
    phone = os.getenv("PHONE_NUMBER", "")
    client = await _get_or_create_client()
    if client is None:
        return {"authorized": False, "has_env": False, "api_id": "", "phone": ""}
    try:
        authorized = await client.is_user_authorized()
        user_info = None
        if authorized:
            me = await client.get_me()
            user_info = {
                "id": me.id,
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "username": me.username or "",
                "phone": me.phone or phone,
            }
        return {
            "authorized": authorized,
            "has_env": True,
            "api_id": api_id,
            "phone": phone,
            "user": user_info,
        }
    except Exception as e:
        return {"authorized": False, "has_env": True, "error": str(e)}


@app.post("/api/auth/send-code")
async def send_code(req: SendCodeRequest):
    try:
        if req.save_env:
            _save_env_credentials(req.api_id, req.api_hash.strip(), req.phone.strip())
        client = await _get_or_create_client(req.api_id, req.api_hash.strip())
        if await client.is_user_authorized():
            return {"already_authorized": True}
        sent = await client.send_code_request(req.phone.strip())
        state.pending_phone = req.phone.strip()
        state.pending_phone_hash = sent.phone_code_hash
        return {"already_authorized": False, "sent": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/verify-code")
async def verify_code(req: VerifyCodeRequest):
    if not state.client or not state.pending_phone:
        raise HTTPException(status_code=400, detail="Send verification code first.")
    try:
        await state.client.sign_in(
            phone=state.pending_phone,
            code=req.code.strip(),
            phone_code_hash=state.pending_phone_hash,
        )
    except errors.SessionPasswordNeededError:
        if not req.password:
            return {"needs_password": True}
        try:
            await state.client.sign_in(password=req.password)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"2FA sign-in failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    me = await state.client.get_me()
    state.pending_phone = None
    state.pending_phone_hash = None
    return {
        "authorized": True,
        "user": {
            "first_name": me.first_name or "",
            "username": me.username or "",
            "phone": me.phone or "",
        },
    }


@app.post("/api/auth/logout")
async def logout():
    if state.running:
        raise HTTPException(status_code=400, detail="Stop the active upload before logging out.")
    if state.client:
        try:
            await state.client.log_out()
        except Exception:
            await state.client.disconnect()
        state.client = None
    return {"logged_out": True}


@app.get("/api/dialogs")
async def list_dialogs():
    client = await _get_or_create_client()
    if not client or not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Not logged in to Telegram.")
    dialogs = [{"id": "me", "name": "Saved Messages (me)", "type": "saved"}]
    async for d in client.iter_dialogs(limit=50):
        kind = "channel" if d.is_channel else ("group" if d.is_group else "user")
        dialogs.append({"id": str(d.id), "name": d.name or str(d.id), "type": kind})
    return {"dialogs": dialogs}


@app.post("/api/browse")
async def browse_folder(req: BrowseRequest):
    source = req.source.strip().strip('"')
    if not os.path.isdir(source):
        raise HTTPException(status_code=400, detail=f"Directory not found: {source}")

    all_files = uploader.get_all_files(
        source,
        allowed_exts=req.ext or None,
        include_folders=req.include_folders or None,
        exclude_folders=req.exclude_folders or None,
        include_patterns=req.include_patterns or None,
        exclude_patterns=req.exclude_patterns or None,
    )
    uploaded = uploader.load_state()

    folders_map = {}
    files_out = []
    for full_path in all_files:
        rel_path = os.path.relpath(full_path, source)
        rel_posix = rel_path.replace("\\", "/")
        folder_rel = os.path.dirname(rel_posix) or "(root)"
        size = os.path.getsize(full_path)
        is_done = rel_path in uploaded

        entry = {
            "rel_path": rel_path,
            "rel_posix": rel_posix,
            "folder": folder_rel,
            "name": os.path.basename(full_path),
            "size": size,
            "size_human": uploader.format_size(size),
            "uploaded": is_done,
        }
        files_out.append(entry)
        f_stats = folders_map.setdefault(
            folder_rel, {"folder": folder_rel, "count": 0, "size": 0, "uploaded_count": 0}
        )
        f_stats["count"] += 1
        f_stats["size"] += size
        if is_done:
            f_stats["uploaded_count"] += 1

    folders_out = []
    for item in sorted(folders_map.values(), key=lambda x: x["folder"]):
        item["size_human"] = uploader.format_size(item["size"])
        folders_out.append(item)

    return {
        "source": source,
        "total_files": len(files_out),
        "folders": folders_out,
        "files": files_out,
    }


async def _send_with_progress(client, target, file_path, caption, force_document, delay, label):
    """Upload a single file with live progress updates on UploadState."""
    file_size = os.path.getsize(file_path)
    state.current_file = label
    state.current_bytes = 0
    state.current_total_bytes = file_size

    while True:
        try:
            def progress_cb(current, total):
                state.current_bytes = current
                state.current_total_bytes = total or file_size

            await client.send_file(
                target,
                file_path,
                caption=caption,
                force_document=force_document,
                part_size_kb=512,
                progress_callback=progress_cb,
            )
            await asyncio.sleep(delay)
            return
        except errors.FloodWaitError as e:
            state.log(f"[RATE LIMIT] FloodWait {e.seconds}s — pausing...")
            state.status_message = f"Rate limited ({e.seconds}s cooldown)"
            await asyncio.sleep(e.seconds + 5)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            state.log(f"[ERROR] {label}: {e}. Retrying in 10s...")
            await asyncio.sleep(10)


async def _run_background_upload(req: UploadStartRequest):
    """Background asyncio worker for uploading selected files."""
    state.running = True
    state.completed_files = 0
    state.skipped_files = 0
    state.current_file = ""
    state.current_bytes = 0
    state.current_total_bytes = 0
    state.logs.clear()

    try:
        client = await _get_or_create_client()
        if not client or not await client.is_user_authorized():
            state.log("[ERROR] Not authorized in Telegram.")
            state.status_message = "Error: Not logged in"
            return

        source = req.source.strip().strip('"')
        all_files = uploader.get_all_files(source)
        if req.selected_files is not None:
            wanted = set(req.selected_files)
            all_files = [f for f in all_files if os.path.relpath(f, source) in wanted]

        state.total_files = len(all_files)
        state.status_message = f"Uploading {len(all_files)} files..."
        state.log(f"Started background upload: {len(all_files)} file(s) -> {req.target}")

        chat_target = int(req.target) if req.target.lstrip("-").isdigit() else req.target
        target = await client.get_input_entity(chat_target)
        uploaded_files = uploader.load_state()
        max_file_size = (4 if req.premium else 2) * 1024 * 1024 * 1024
        limit_gb = 4 if req.premium else 2
        force_document = not req.compress

        for file_path in all_files:
            rel_path = os.path.relpath(file_path, source)
            if rel_path in uploaded_files:
                state.completed_files += 1
                state.log(f"[SKIPPED - ALREADY UPLOADED] {rel_path}")
                continue

            file_size = os.path.getsize(file_path)
            if file_size == 0:
                state.skipped_files += 1
                continue

            folder_name = os.path.basename(os.path.dirname(file_path))
            file_name = os.path.basename(file_path)
            _, ext = os.path.splitext(file_name)

            if file_size > max_file_size:
                if not req.split_large or ext.lower() not in uploader.VIDEO_EXTENSIONS:
                    reason = "not a supported video" if req.split_large else None
                    uploader.log_skipped_file(rel_path, file_size, limit_gb, reason)
                    state.log(f"[SKIPPED > {limit_gb}GB] {rel_path}")
                    state.skipped_files += 1
                    continue

                state.status_message = f"Splitting {file_name} with FFmpeg..."
                state.log(f"[SPLITTING > {limit_gb}GB] {rel_path}...")
                with tempfile.TemporaryDirectory() as tmpdir:
                    try:
                        chunks = await asyncio.to_thread(
                            uploader.split_video_file, file_path, tmpdir, max_file_size
                        )
                    except Exception as e:
                        uploader.log_skipped_file(rel_path, file_size, limit_gb, f"split failed: {e}")
                        state.log(f"[SPLIT FAILED] {rel_path}: {e}")
                        state.skipped_files += 1
                        continue

                    if not chunks or any(os.path.getsize(c) > max_file_size for c in chunks):
                        state.log(f"[SKIPPED] Split chunks still exceed {limit_gb}GB: {rel_path}")
                        state.skipped_files += 1
                        continue

                    total_parts = len(chunks)
                    for idx, chunk_path in enumerate(chunks, start=1):
                        caption = f"📁 {folder_name}\n📄 {file_name} (Part {idx}/{total_parts})"
                        state.status_message = f"Uploading {file_name} (Part {idx}/{total_parts})"
                        await _send_with_progress(
                            client,
                            target,
                            chunk_path,
                            caption,
                            force_document,
                            req.delay,
                            f"{rel_path} (Part {idx}/{total_parts})",
                        )

                uploaded_files.add(rel_path)
                uploader.save_state(uploaded_files)
                state.completed_files += 1
                state.log(f"[UPLOADED SPLIT] {rel_path}")
                continue

            caption = f"📁 {folder_name}\n📄 {file_name}"
            state.status_message = f"Uploading {file_name}"
            await _send_with_progress(
                client, target, file_path, caption, force_document, req.delay, rel_path
            )
            uploaded_files.add(rel_path)
            uploader.save_state(uploaded_files)
            state.completed_files += 1
            state.log(f"[UPLOADED] {rel_path}")

        state.status_message = "Upload queue complete!"
        state.log("Upload queue complete!")
    except asyncio.CancelledError:
        state.status_message = "Stopped by user"
        state.log("[STOPPED] Background upload cancelled by user.")
    except Exception as e:
        state.status_message = f"Error: {e}"
        state.log(f"[FATAL] {e}")
    finally:
        state.running = False
        state.current_file = ""


@app.post("/api/upload/start")
async def start_upload(req: UploadStartRequest):
    if state.running:
        raise HTTPException(status_code=400, detail="An upload is already running.")
    source = req.source.strip().strip('"')
    if not os.path.isdir(source):
        raise HTTPException(status_code=400, detail=f"Directory not found: {source}")
    if req.split_large and (not shutil.which("ffmpeg") or not shutil.which("ffprobe")):
        raise HTTPException(
            status_code=400,
            detail="FFmpeg and ffprobe must be installed and on PATH to use Split Large Videos.",
        )

    state.task = asyncio.create_task(_run_background_upload(req))
    return {"started": True}


@app.post("/api/upload/stop")
async def stop_upload():
    if not state.running or not state.task:
        return {"stopped": False, "message": "No active upload."}
    state.task.cancel()
    return {"stopped": True}


@app.get("/api/upload/status")
async def upload_status():
    pct = 0.0
    if state.current_total_bytes > 0:
        pct = round((state.current_bytes / state.current_total_bytes) * 100, 1)
    return {
        "running": state.running,
        "total_files": state.total_files,
        "completed_files": state.completed_files,
        "skipped_files": state.skipped_files,
        "current_file": state.current_file,
        "current_bytes": state.current_bytes,
        "current_total_bytes": state.current_total_bytes,
        "current_progress_pct": pct,
        "status_message": state.status_message,
        "logs": list(state.logs),
    }


if __name__ == "__main__":
    print("Starting Telegram Bulk Uploader Web UI at http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
