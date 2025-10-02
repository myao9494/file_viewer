"""
FastAPIを使用したファイルビューアアプリケーション
"""
from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import platform
import mimetypes
from typing import List, Optional
import json
import shutil
from pathlib import Path
import urllib.parse
from datetime import datetime

# FastAPIアプリケーションの作成
app = FastAPI(title="File Viewer API", version="1.0.0")

# CORSミドルウェアの設定（個人利用のため全てのオリジンからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのヘッダーを許可
)

# テンプレートとスタティックファイルの設定
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# OSの判定
IS_WINDOWS = platform.system() == 'Windows'

# ベースディレクトリの設定
mac_BASE_DIR = Path("/Users/sudoupousei/000_work")


def _get_windows_base_dir() -> Path:
    """Resolve the working root on Windows from the current user profile."""
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / "000_work"
    # Fallback to the home directory when USERPROFILE is unavailable
    return Path.home() / "000_work"


BASE_DIR = mac_BASE_DIR if not IS_WINDOWS else _get_windows_base_dir()
WINDOWS_LEGACY_ROOT = Path(r"F:\000_work")


def convert_legacy_windows_path(raw_path: Optional[str]) -> Optional[str]:
    """Translate legacy F:\\ paths to the current user profile based root."""
    if not raw_path or not IS_WINDOWS:
        return raw_path

    normalized = raw_path.replace("/", "\\")
    legacy_prefix = str(WINDOWS_LEGACY_ROOT)

    if normalized.lower().startswith(legacy_prefix.lower()):
        suffix = normalized[len(legacy_prefix):].lstrip("\\/")
        return str(BASE_DIR / Path(suffix))

    return raw_path


def normalize_request_path(raw_path: Optional[str]) -> Path:
    """Return a path relative to BASE_DIR with legacy Windows paths handled."""
    if not raw_path:
        return Path()

    translated = convert_legacy_windows_path(raw_path)
    sanitized = translated.replace("\\", "/") if translated else ""
    candidate = Path(sanitized)

    if candidate.is_absolute():
        try:
            candidate = candidate.relative_to(BASE_DIR)
        except ValueError:
            raise HTTPException(status_code=400, detail="許可されていないパスです")

    return candidate

def normalize_path(path):
    """パスを正規化する関数"""
    return Path(path).as_posix()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """ホームページを表示"""
    return templates.TemplateResponse("home.html", {"request": request, "base_dir": BASE_DIR})

@app.get("/api/files")
async def get_files(path: str = ""):
    """ファイル一覧を取得"""
    try:
        relative_path = normalize_request_path(path)
        target_path = BASE_DIR / relative_path
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="パスが見つかりません")
        
        if target_path.is_file():
            return {"type": "file", "path": str(target_path)}
        
        items = []
        for item in target_path.iterdir():
            if item.is_dir():
                items.append({
                    "name": item.name,
                    "type": "directory",
                    "path": str(item.relative_to(BASE_DIR))
                })
            else:
                items.append({
                    "name": item.name,
                    "type": "file",
                    "path": str(item.relative_to(BASE_DIR)),
                    "size": item.stat().st_size,
                    "modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                })
        
        return {"type": "directory", "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/file/{file_path:path}")
async def get_file(file_path: str):
    """ファイルの内容を取得"""
    try:
        relative_path = normalize_request_path(file_path)
        full_path = BASE_DIR / relative_path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="ファイルが見つかりません")
        
        # ファイルの種類を判定
        mime_type, _ = mimetypes.guess_type(full_path)
        
        if mime_type and mime_type.startswith('text/'):
            # テキストファイルの場合
            content = full_path.read_text(encoding='utf-8')
            return {"type": "text", "content": content}
        else:
            # バイナリファイルの場合はファイルを直接返す
            return FileResponse(full_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_file(
    request: Request,
    files: List[UploadFile] = File(...),
    current_path: str = Form("")
):
    """ファイルをアップロード"""
    try:
        uploaded_files = []
        current_relative_path = normalize_request_path(current_path)
        upload_dir = BASE_DIR / current_relative_path / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        for file in files:
            if file.filename:
                # ファイル名を安全にする
                safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
                file_path = upload_dir / safe_filename
                
                # ファイルを保存
                with open(file_path, "wb") as buffer:
                    content = await file.read()
                    buffer.write(content)
                
                uploaded_files.append({
                    "name": safe_filename,
                    "path": str(file_path.relative_to(BASE_DIR))
                })
        
        return {"success": True, "files": uploaded_files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create-folder")
async def create_folder(data: dict):
    """フォルダを作成"""
    try:
        parent_relative = normalize_request_path(data.get("path", ""))
        folder_path = BASE_DIR / parent_relative / data["name"]
        folder_path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(folder_path.relative_to(BASE_DIR))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/delete")
async def delete_item(data: dict):
    """ファイルまたはフォルダを削除"""
    try:
        item_relative = normalize_request_path(data.get("path", ""))
        item_path = BASE_DIR / item_relative
        if item_path.is_file():
            item_path.unlink()
        elif item_path.is_dir():
            shutil.rmtree(item_path)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/view/{file_path:path}")
async def view_file(request: Request, file_path: str):
    """ファイルを表示"""
    try:
        relative_path = normalize_request_path(file_path)
        full_path = BASE_DIR / relative_path
        display_path = str(relative_path)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="ファイルが見つかりません")
        
        # ファイルの種類に応じて適切なテンプレートを選択
        if full_path.is_dir():
            return templates.TemplateResponse("directory_view.html", {
                "request": request,
                "path": display_path,
                "full_path": full_path
            })
        else:
            mime_type, _ = mimetypes.guess_type(full_path)
            
            if mime_type and mime_type.startswith('text/'):
                content = full_path.read_text(encoding='utf-8')
                return templates.TemplateResponse("view_file.html", {
                    "request": request,
                    "content": content,
                    "file_path": display_path,
                    "full_path": full_path
                })
            elif mime_type and mime_type.startswith('image/'):
                return templates.TemplateResponse("image_view.html", {
                    "request": request,
                    "file_path": display_path,
                    "full_path": full_path
                })
            else:
                return FileResponse(full_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
