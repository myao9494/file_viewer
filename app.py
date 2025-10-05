import os,re
import logging
import threading
import signal
# import fnmatch
import platform
from flask import Flask, render_template, request, send_file, abort, url_for, Response, send_from_directory, jsonify, redirect, flash, session
# from flask_cors import CORS  # オフライン環境では使用不可のためコメントアウト
# import re
import csv
from utils.file_handler import get_file_content, get_file_list
from utils.search import search_files
from utils.file_utils import filter_files, should_ignore, load_view_ignore
from utils.markdown_renderer import render_markdown
from utils.csv_renderer import render_csv
import mimetypes
import subprocess
from markdown import markdown
import json
import html
# import os.path
import webbrowser
import pathlib
import urllib.parse
import zipfile
import io
import shutil
from itertools import zip_longest  # この行を追加
from typing import List, Dict, Any, Tuple, Optional
# import pyperclip
from PIL import Image
from datetime import datetime
import time
import glob
from werkzeug.utils import secure_filename  # この行を追加
import pyperclip  # 追加
if platform.system() == "Windows":
    import win32clipboard
    import PySimpleGUI as sg
    import win32com.client


app = Flask(__name__, static_folder='static')

# Server control defaults
DEFAULT_HOST = os.environ.get('FILE_VIEWER_HOST', '0.0.0.0')
DEFAULT_PORT = int(os.environ.get('FILE_VIEWER_PORT', '5001'))
app.config['SERVER_HOST'] = DEFAULT_HOST
app.config['SERVER_PORT'] = DEFAULT_PORT

# CORS設定を手動で実装
# セキュリティを考慮しない個人利用のため、すべてのオリジンからのアクセスを許可
@app.after_request
def after_request(response):
    # すべてのオリジンからのアクセスを許可
    response.headers.add('Access-Control-Allow-Origin', '*')
    
    # 許可するHTTPメソッドを指定
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    
    # 許可するヘッダーを指定
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    # プリフライトリクエストの結果をキャッシュする時間（秒）
    response.headers.add('Access-Control-Max-Age', '3600')
    
    return response

# OPTIONSリクエストとセッション管理を統合した関数
@app.before_request
def before_request():
    if request.method == 'OPTIONS':
        # OPTIONSリクエストの場合、after_requestでCORSヘッダーが設定されるため
        # ここではヘッダーを設定せずに空のレスポンスを返す
        response = jsonify({'message': 'OK'})
        return response
    
    global BASE_DIR
    # セッションからBASE_DIRを取得（存在しない場合はデフォルト値を使用）
    BASE_DIR = session.get('BASE_DIR', BASE_DIR)

# 以下を追加
app.config['STATIC_URL_PATH'] = '/static'

# OSの種類を判別
IS_WINDOWS = platform.system() == 'Windows'
CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WINDOWS and hasattr(subprocess, 'CREATE_NO_WINDOW') else 0

WINDOWS_LEGACY_ROOT = pathlib.PureWindowsPath(r"F:\000_work")


def _get_windows_base_dir() -> pathlib.Path:
    """Get the current working root for Windows environments."""
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return pathlib.Path(user_profile) / "000_work"
    return pathlib.Path.home() / "000_work"


WINDOWS_BASE_DIR_PATH = _get_windows_base_dir()


def _translate_legacy_windows_path(path_str: str) -> str:
    """Translate legacy F:\\ paths to the new user profile based location."""
    normalized = path_str.replace("/", "\\")
    legacy_prefix = str(WINDOWS_LEGACY_ROOT)

    if normalized.lower().startswith(legacy_prefix.lower()):
        suffix = normalized[len(legacy_prefix):].lstrip("\\/")
        translated = WINDOWS_BASE_DIR_PATH / pathlib.Path(suffix)
        return str(translated)

    return path_str


# パスの区切り文字を統一する関数を追加
def normalize_path(path):
    if path is None:
        return None

    path_str = str(path)
    if IS_WINDOWS:
        path_str = _translate_legacy_windows_path(path_str)

    return pathlib.Path(path_str).as_posix()


def get_pids_for_port(port: int) -> List[int]:
    """Return a sorted list of PIDs listening on or connected to the given TCP port."""
    try:
        if IS_WINDOWS:
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW if IS_WINDOWS else 0
            )
            if result.returncode not in (0, 1):
                server_control_logger.warning('netstat returned non-zero exit code %s: %s', result.returncode, result.stderr.strip())
            pids = set()
            for line in result.stdout.splitlines():
                if f":{port}" not in line:
                    continue
                tokens = line.split()
                if len(tokens) < 5:
                    continue
                pid_token = tokens[-1]
                if pid_token.isdigit():
                    pids.add(int(pid_token))
            return sorted(pids)
        result = subprocess.run(
            ['lsof', '-ti', f'tcp:{port}'],
            capture_output=True,
            text=True
        )
        pids = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                pids.add(int(line))
        return sorted(pids)
    except FileNotFoundError:
        server_control_logger.error('Required command not found while checking port %s', port)
        return []
    except Exception as exc:
        server_control_logger.error('Failed to gather PIDs for port %s: %s', port, exc)
        return []


def is_port_in_use(port: int) -> bool:
    return bool(get_pids_for_port(port))


def terminate_pid(pid: int, force: bool = True) -> Tuple[bool, str]:
    """Terminate a process by PID. Returns (success, message)."""
    try:
        if IS_WINDOWS:
            cmd = ['taskkill', '/PID', str(pid)]
            if force:
                cmd.append('/F')
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW if IS_WINDOWS else 0
            )
            if result.returncode == 0:
                return True, result.stdout.strip() or 'Terminated'
            message = (result.stderr or result.stdout).strip()
            if 'not found' in message.lower():
                return True, message
            return False, message
        signal_to_use = signal.SIGKILL if force and hasattr(signal, 'SIGKILL') else signal.SIGTERM
        os.kill(pid, signal_to_use)
        return True, f'Sent signal {signal_to_use}'
    except ProcessLookupError:
        return True, 'Process already exited'
    except PermissionError as exc:
        return False, f'Permission denied: {exc}'
    except Exception as exc:
        return False, str(exc)


def stop_processes_by_port(port: int) -> Dict[str, Any]:
    """Stop all processes using the specified port and report the outcome."""
    result: Dict[str, Any] = {
        'requested_port': port,
        'matched_pids': [],
        'killed_pids': [],
        'errors': [],
        'self_shutdown': False,
    }

    pids = get_pids_for_port(port)
    result['matched_pids'] = pids
    if not pids:
        return result

    for pid in pids:
        if pid == os.getpid():
            result['self_shutdown'] = True
            result['killed_pids'].append(pid)
            continue

        success, message = terminate_pid(pid)
        if success:
            result['killed_pids'].append(pid)
            server_control_logger.info('Terminated PID %s on port %s: %s', pid, port, message)
        else:
            error_info = {'pid': pid, 'message': message}
            result['errors'].append(error_info)
            server_control_logger.error('Failed to terminate PID %s on port %s: %s', pid, port, message)

    if not result['self_shutdown']:
        time.sleep(0.2)
        result['port_active_after_stop'] = is_port_in_use(port)
    else:
        # Current process will handle shutdown separately; port remains active until exit
        result['port_active_after_stop'] = True

    return result


def schedule_application_shutdown(environ: dict, delay: float = 1.0) -> None:
    def _shutdown():
        time.sleep(delay)
        shutdown_func = environ.get('werkzeug.server.shutdown')
        server_control_logger.info('Invoking werkzeug shutdown callback: %s', bool(shutdown_func))
        if shutdown_func:
            shutdown_func()
        else:
            os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()


# グローバル変数としてBASE_DIRを定義
global BASE_DIR

# ベースディレクトリの設定

mac_BASE_DIR = r"/Users/sudoupousei/000_work"  # Windowsの場合
win_BASE_DIR = r"C:\Users\kabu_server\000_work"
net_work_drive = "network"
BASE_DIR = normalize_path(mac_BASE_DIR if not IS_WINDOWS else win_BASE_DIR)

# テンプレートフォルダの設定
mac_TEMPLATE_FOLDER = r"/Users/sudoupousei/000_work/template_folder"
win_TEMPLATE_FOLDER = r"F:\000_work\template_folder"
TEMPLATE_FOLDER = normalize_path(mac_TEMPLATE_FOLDER if not IS_WINDOWS else win_TEMPLATE_FOLDER)

app.jinja_env.globals['BASE_DIR'] = BASE_DIR
app.jinja_env.globals['SERVER_PORT'] = DEFAULT_PORT

SERVER_CONTROL_LOG_PATH = os.path.join(BASE_DIR, 'logs', 'server_control.log')
os.makedirs(os.path.dirname(SERVER_CONTROL_LOG_PATH), exist_ok=True)
server_control_logger = logging.getLogger('server_control')
if not server_control_logger.handlers:
    file_handler = logging.FileHandler(SERVER_CONTROL_LOG_PATH)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    server_control_logger.addHandler(file_handler)
    server_control_logger.setLevel(logging.INFO)
    server_control_logger.propagate = False

# JupyterのベースURLを設定
JUPYTER_BASE_URL =  'http://localhost:8888/lab/tree' 

# ファイルアップロード用の設定を追加
UPLOAD_FOLDERS = {
    'images': os.path.join(BASE_DIR, 'uploads', 'images'),
    'documents': os.path.join(BASE_DIR, 'uploads', 'documents'),
    'emails': os.path.join(BASE_DIR, 'uploads', 'emails'),  # メール用フォルダを追加
    'others': os.path.join(BASE_DIR, 'uploads', 'others')
}

# 許可する拡張子を定義
ALLOWED_EXTENSIONS = {
    'images': {'png', 'jpg', 'jpeg', 'gif', 'svg'},
    'documents': {'pdf', 'doc', 'docx', 'txt', 'md'},
    'emails': {'eml', 'msg'},  # Outlook (.msg) と標準メール (.eml) の拡張子を追加
    'others': {'zip', 'rar', 'csv', 'xlsx'}
}

@app.route('/')
def index():
    """
    シンプルなホームページを表示する関数

    Returns:
        str: レンダリングされたHTMLテンプレート
    """
    return render_template('home.html', base_dir=BASE_DIR)

@app.route('/load_files')
def load_files():
    """
    ファイルリストを読み込んで表示する関数

    Returns:
        str: レンダリングされたHTMLテンプレート
    """
    # すべてのファイルを取得
    all_files = get_file_list(BASE_DIR)
    # フィルタリングを適用
    files = filter_files(all_files, BASE_DIR)
    # index.htmlテンプレートをレンダリングし、ファイルリストを渡す
    return render_template('index.html', files=files)

@app.route('/view', defaults={'file_path': ''})
@app.route('/view/', defaults={'file_path': ''})
@app.route('/view/<path:file_path>')
def view_file(file_path):
    """相対パスでファイルを表示"""
    return handle_file_view(file_path, is_absolute=False)

@app.route('/fullpath')
def view_file_fullpath():
    """
    フルパスでファイルを表示
    ルートディレクトリ内のファイルの場合は相対パスに変換して通常処理に回す
    """
    # 生のクエリ文字列から直接取得
    raw_query = request.query_string.decode('utf-8')
    app.logger.info(f"[DEBUG] Raw query string: {raw_query}")
    
    file_path = request.args.get('path', '')
    
    # URLデコード処理を明示的に実行（ダブルクォートを含む文字列に対応）
    if file_path:
        try:
            # URLエンコードされた文字列をデコード
            file_path = urllib.parse.unquote_plus(file_path)
            # HTMLエンティティもデコード（&quot; -> "）
            file_path = html.unescape(file_path)
            app.logger.info(f"[DEBUG] Original path param: {request.args.get('path', '')}")
            app.logger.info(f"[DEBUG] Decoded path: {file_path}")
        except Exception as e:
            app.logger.warning(f"Failed to decode path parameter: {e}")
            # デコードに失敗した場合は元の値を使用
    
    # 生のクエリ文字列からpathパラメータを手動で抽出してみる
    if not file_path or file_path.strip() == 'cmd':
        try:
            if 'path=' in raw_query:
                # path=以降を取得
                path_part = raw_query.split('path=', 1)[1]
                app.logger.info(f"[DEBUG] Path part before split: {path_part}")
                
                # &quot; が含まれている場合は、通常の&による分割をスキップ
                if '&quot;' in path_part:
                    # &quot; を含む場合は全体を取得（他のパラメータがないと仮定）
                    app.logger.info("[DEBUG] Found &quot; - taking entire path part")
                else:
                    # 他のパラメータがある場合は&で分割
                    if '&' in path_part and not path_part.startswith('&'):
                        path_part = path_part.split('&')[0]
                        app.logger.info(f"[DEBUG] Split by &: {path_part}")
                
                app.logger.info(f"[DEBUG] Path part before decode: {path_part}")
                # URLデコードとHTMLエンティティデコードを実行
                file_path = urllib.parse.unquote_plus(path_part)
                app.logger.info(f"[DEBUG] After URL decode: {file_path}")
                file_path = html.unescape(file_path)
                app.logger.info(f"[DEBUG] Manual extraction result: {file_path}")
        except Exception as e:
            app.logger.warning(f"Manual extraction failed: {e}")
    if not file_path:
        return render_template('view_file.html',
                             content="フルパスが指定されていません。",
                             file_path="Error",
                             full_path="",
                             current_item="Error")
    
    # パスを正規化
    normalized_full_path = normalize_path(file_path)
    normalized_base_dir = normalize_path(BASE_DIR)
    
    # フルパスがBASE_DIR内のファイルかチェック
    if normalized_full_path.startswith(normalized_base_dir):
        # BASE_DIR内のファイルの場合、相対パスに変換
        relative_path = os.path.relpath(normalized_full_path, normalized_base_dir)
        # 相対パス用の処理に回す
        return handle_file_view(relative_path, is_absolute=False)
    else:
        # BASE_DIR外のファイルの場合、フルパス処理
        return handle_file_view(file_path, is_absolute=True)

def handle_file_view(file_path, is_absolute=False):
    app.logger.info(f"handle_file_view関数が呼び出されました。file_path: {repr(file_path)}, is_absolute: {is_absolute}")

    # ダブルクォートで囲まれている場合、中身だけを取り出す
    # if file_path.startswith('"') and file_path.endswith('"'):
    #     file_path = file_path[1:-1]

    if file_path.startswith('pyenv '):
        try:
            script_path = file_path[6:]  # "cmd "の部分を除去
            app.logger.info(f"実行するコマンド: {script_path}")
            # 作業ディレクトリを指定
            work_dir = r'F:\000_work\py_env\py3123-master'
            # setenv.batを実行するためのコマンド
            setenv_command = 'setenv.bat'
            # Popenを使用してコマンドを非同期で実行
            process = subprocess.Popen(
                f'cmd /c "{setenv_command} && python {script_path}"',
                cwd=work_dir,
                shell=True
            )
            return render_template('view_file.html',
                content=f"{script_path}を実行しました",
                file_path=f"Command: {script_path}",
                full_path="",
                current_item="Command Execution")
        except Exception as e:
            return render_template('view_file.html',
                content=f"Error executing command: {str(e)}",
                file_path=f"Command: {script_path}",
                full_path="",
            current_item="Command Execution Error")

    # cmd コマンドの処理を追加
    if file_path.startswith('cmd '):
        try:
            command = file_path[4:]  # "cmd "の部分を除去
            app.logger.info(f"実行するコマンド: {command}")
            
            # Windowsの場合の特別な処理
            if platform.system() == 'Windows':
                # エクスプローラーを開くコマンドの特別処理
                if command.lower().startswith('explorer'):
                    path = command[9:].strip('"').strip()  # "explorer "の後のパスを取得
                    path = path.replace('/', '\\')  # パスの区切り文字を変換
                    subprocess.Popen(['explorer', path])
                    return render_template('view_file.html',
                                        content="エクスプローラーでフォルダを開きました。",
                                        file_path=f"Command: {command}",
                                        full_path="",
                                        current_item="Command Execution")
                
                # その他のWindowsコマンド用の設定
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='cp932',  # Windows用のエンコーディング
                    errors='replace'   # エンコーディングエラーを置換文字で対処
                )
            else:
                # Unix系OSの場合は既存の処理
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
            
            # 標準出力と標準エラー出力を結合
            output = result.stdout + result.stderr
            
            # 結果をテキストとして表示
            return render_template('view_file.html', 
                                content=output, 
                                file_path=f"Command: {command}", 
                                full_path="", 
                                current_item="Command Execution")
        except Exception as e:
            return render_template('view_file.html',
                                content=f"Error executing command: {str(e)}",
                                file_path=f"Command: {command}",
                                full_path="",
                                current_item="Command Execution Error")

    # 既存のファイル処理コード
    depth = int(request.args.get('depth', 0))

    # パス処理の分岐
    if is_absolute:
        # フルパスの場合
        full_path = normalize_path(file_path)
        
        # セキュリティチェック: 危険なパスを拒否
        if '..' in file_path or file_path.startswith('~'):
            return render_template('view_file.html',
                                 content="セキュリティ上の理由により、このパスはアクセスできません。",
                                 file_path=file_path,
                                 full_path="",
                                 current_item="Security Error")
        
        # Windowsネットワークドライブの処理を追加
        if IS_WINDOWS and ('\\\\' in file_path or '//' in file_path):
            # UNCパス（\\server\share）の場合
            full_path = file_path.replace('/', '\\')
            app.logger.info(f"Windowsネットワークパス処理: {full_path}")
        elif full_path.find(net_work_drive) != -1:
            # ネットワークドライブ名が含まれる場合
            full_path = full_path.split(net_work_drive)[1]
            full_path = f"\\\\{net_work_drive}" + full_path
            full_path = full_path.replace('/', '\\')
            app.logger.info(f"ネットワークドライブ変換: {full_path}")
        
        file_name = os.path.basename(file_path)
        folder_name = os.path.basename(os.path.dirname(file_path))
        current_item = f"{file_name} - {folder_name}" if folder_name else file_name
    else:
        # 相対パスの場合（既存の処理）
        # 末尾のスラッシュを削除
        if file_path.endswith('/'):
            return redirect(url_for('view_file', file_path=file_path.rstrip('/')))

        # file_pathが空の場合、ルートディレクトリを表示
        if not file_path:
            full_path = BASE_DIR
            current_item = 'Root'
        else:
            file_path = file_path.lstrip('/')
            full_path = normalize_path(os.path.join(BASE_DIR, file_path))
            if full_path.find(net_work_drive) != -1:
                full_path = full_path.split(net_work_drive)[1]
                full_path = f"\\\\{net_work_drive}" + full_path
                full_path = full_path.replace('/', '\\')
            file_name = os.path.basename(file_path)
            folder_name = os.path.basename(os.path.dirname(file_path))
            current_item = f"{file_name} - {folder_name}" if folder_name else file_name

    app.logger.info(f"full_path: {full_path}")

    if not os.path.exists(full_path):
        app.logger.error(f"ファイルが存在しません: {full_path}")
        abort(404)

    # .lnkファイルの場合
    if full_path.lower().endswith('.lnk') and platform.system() == "Windows":
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(full_path)
            target_path = shortcut.Targetpath
            
            # リンク先が存在するか確認
            if os.path.exists(target_path):
                if os.path.isdir(target_path):
                    # ディレクトリの場合はそのまま開く
                    subprocess.Popen(['explorer', target_path])
                else:
                    # ファイルの場合はデフォルトアプリで開く
                    os.startfile(target_path)
                return jsonify({'success': True, 'message': 'ショートカットのリンク先を開きました'})
            else:
                return jsonify({'success': False, 'error': 'リンク先が見つかりません'})
        except Exception as e:
            app.logger.error(f"ショートカットを開く際にエラーが発生しました: {str(e)}")
            return jsonify({'success': False, 'error': str(e)})

    # ディレクトリの場合
    if os.path.isdir(full_path):
        app.logger.info(f"ディレクトリを表示します: {full_path}")
        if is_absolute:
            # フルパスの場合のディレクトリ表示
            folders, files = get_items_with_depth_absolute(full_path, depth)
            parent_path = os.path.dirname(file_path) if file_path != '' else None
            return render_template('directory_view.html', 
                                 folders=folders, files=files, 
                                 current_path=file_path, parent_path=parent_path, 
                                 full_path=full_path, depth=depth, 
                                 current_item=current_item, is_absolute=True)
        else:
            # 相対パスの場合（既存の処理）
            folders, files = get_items_with_depth(full_path, depth, file_path)
            parent_path = os.path.dirname(file_path) if file_path != '' else None
            return render_template('directory_view.html', 
                                 folders=folders, files=files, 
                                 current_path=file_path, parent_path=parent_path, 
                                 full_path=full_path, depth=depth, 
                                 current_item=current_item)

    # ファイルの場合
    file_extension = os.path.splitext(full_path)[1].lower()
    base_name = os.path.basename(full_path).lower()
    
    # Excalidrawファイルの場合
    if (file_extension == '.excalidraw' or 
        base_name.endswith('.excalidraw.svg') or 
        base_name.endswith('.excalidraw.png')):
        # Excalidrawエディタにリダイレクト
        excalidraw_url = f"http://localhost:3001/?filepath={full_path}"
        return redirect(excalidraw_url)
    
    # MIMEタイプを得
    mime_type, _ = mimetypes.guess_type(full_path)

    # .xdwファイルの場合
    if file_extension == '.xdw':
        return send_file(full_path, as_attachment=True)

    # SVGファイルの場合
    if file_extension == '.svg':
        with open(full_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_content = svg_content.replace('<svg', '<svg id="svg-content"', 1)
        # Excalidraw SVGかどうかを判定
        is_excalidraw = base_name.endswith('_excalidraw.svg')
        return render_template('svg_view.html', 
                            svg_content=svg_content, 
                            file_path=file_path, 
                            full_path=full_path, 
                            BASE_DIR=BASE_DIR, 
                            current_item=current_item,
                            is_excalidraw=is_excalidraw)

    # 画像ファイルの場合
    if mime_type and mime_type.startswith('image/'):
        app.logger.info(f"Rendering image: {file_path}")
        return render_template('image_view.html', file_path=file_path, full_path=full_path, current_item=current_item)

    # PDFファイル場合
    if file_extension == '.pdf':
        return send_file(full_path, mimetype='application/pdf')

    # Markdownァイルの場合
    if file_extension == '.md':
        content = render_markdown(full_path)
        folder_path = os.path.dirname(full_path)
        return render_template('markdown_view.html', content=content, file_path=file_path, full_path=full_path, folder_path=folder_path, BASE_DIR=BASE_DIR, current_item=current_item)

    # CSVファイルの場合
    # if file_extension == '.csv':
    #     content = render_csv(full_path)
    #     return render_template('data_table_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
    
    # if file_extension == '.csv':
    #     content = render_csv(full_path)
    #     return render_template('ag_grid_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
    if file_extension == '.csv':
        if full_path.endswith('_tabulator.csv'):
            content = render_csv(full_path)
            return render_template('data_table_view_tabulator.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
        else:
            content = render_csv2(full_path)
            return render_template('csv_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
    
    # ipynbファイルの場合
    if file_extension == '.ipynb':
        # ファイルパスをベースディレクトリからの相対パスに変換
        relative_path = urllib.parse.unquote(os.path.relpath(full_path, BASE_DIR))
        # JupyterのURLを構築
        jupyter_url = f"{JUPYTER_BASE_URL}/{relative_path}"
        cleaned_path = urllib.parse.unquote(jupyter_url)
        cleaned_path = jupyter_url.replace('/viewer/', '/').replace('/viewer-main/', '/').replace('/file_viewer/', '/',1).replace('file_viewer-main/', '')
        app.logger.info(f"{jupyter_url},{cleaned_path}")
        print(cleaned_path)
        # ブラウザでJupyterのURLを開く
        webbrowser.open(cleaned_path)
        
        # ユーザーに通知を返す
        flash('Jupyter Notebookを開きました。', 'info')
        return redirect(url_for('index'))

    # テキストファイルまたは特定の拡張子の場合
    if mime_type and mime_type.startswith('text/') or file_extension in ['.txt', '.py', '.js', '.css', '.json', '.license', '.yml', '.yaml', '.xml', '.ini', '.cfg', '.conf']:
        content = get_file_content(full_path, 'text')
        return render_template('view_file.html', content=content, file_path=file_path, full_path=full_path, current_item=current_item)

    # MS Officeファイルの場合
    if file_extension in ['.docx', '.xlsx', '.xlsm', '.pptx', '.doc', '.xls', '.ppt', '.msg']:
        if open_with_default_app(full_path):
            return jsonify({'success': True, 'message': 'ファイルを開きました'})
        else:
            return jsonify({'success': False, 'error': 'ファイルを開けませんでした'})

    # BASEディレクトリにないファイルの場合
    if not full_path.startswith(BASE_DIR):
        if open_with_default_app(full_path):
            return jsonify({'success': True, 'message': 'ファイルを開きました'})
        else:
            return jsonify({'success': False, 'error': 'ファイルを開けませんでした'})

    # その他のファイルはダウンロード
    return send_file(full_path, as_attachment=True)

def open_with_default_app(file_path):
    """ファイルをOSのデフォルトアプリケーションで開く"""
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", file_path], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", file_path], check=True)
        return True
    except Exception as e:
        app.logger.error(f"ファイルを開く際にエラーが発生しました: {str(e)}")
        return False

@app.route('/search')
def search():
    """
    ファイル検索関数

    Returns:
        str: 検索結果含むレンダリングされたHTMLテンプレート
    """
    # クエリパラメータから検索語を取得
    query = request.args.get('q', '')
    # ファイル検索を実行
    results = search_files(BASE_DIR, query)
    # 検索結果をフィルタリング
    filtered_results = filter_files(results, BASE_DIR)
    # 検索むindex.htmlテンプレートをレンダリング
    return render_template('index.html', files=filtered_results, search_query=query)

@app.route('/open-in-code', methods=['POST'])
def open_in_code():
    data = request.json
    file_path = data.get('path')
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        if IS_WINDOWS:
            vscode_path = r'C:\Users\kabu_server\AppData\Local\Programs\Microsoft VS Code\Code.exe'
        else:
            # vscode_path = '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
            # vscode_path = '/Applications/Cursor.app/Contents/MacOS/Cursor'
            vscode_path = '/Applications/CodeLLM.app/Contents/MacOS/Electron'

        if os.path.exists(vscode_path):
            # URLデコードを行う
            decoded_path = urllib.parse.unquote(file_path)
            normalized_path = normalize_path(file_path)
            
            # ファイルが存在するか確認し、存在しない場合は親ディレクトリを使用
            if os.path.exists(normalized_path):
                target_path = os.path.dirname(normalized_path) if os.path.isfile(normalized_path) else normalized_path
            else:
                # ファイルが見つからない場合は親ディレクトリを使用
                target_path = os.path.dirname(normalized_path)
            
            if IS_WINDOWS:
                # Windowsの場合
                subprocess.Popen([vscode_path, target_path])
                # PowerShellを使用してウィンドウをアクティブにする
                # powershell_command = f'(New-Object -ComObject WScript.Shell).AppActivate("Visual Studio Code")'
                # subprocess.Popen(["powershell", "-Command", powershell_command])
            else:
                # macOSの場合
                subprocess.Popen([vscode_path, target_path])
                # AppleScriptを使用してウィンドウをアクティブにしてフルスクリーンにする
                apple_script = '''
                tell application "Cursor"
                    activate
                end tell
                
                tell application "System Events"
                    tell process "Cursor"
                        set frontmost to true
                        delay 1
                        keystroke "f" using {command down, control down}
                    end tell
                end tell
                '''
                subprocess.run(["osascript", "-e", apple_script])
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Visual Studio Code/Cursorが見つかりません。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/open-in-code2', methods=['POST'])
def open_in_code2():
    data = request.json
    file_path = data.get('path')
    app.logger.info(f"受信したfile_path: {repr(file_path)}")
    
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        if platform.system() == 'Darwin':  # macOS
            vscode_path = '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
        elif platform.system() == 'Windows':
            vscode_path = r'C:\Users\kabu_server\AppData\Local\Programs\Microsoft VS Code\Code.exe'
        else:
            return jsonify({'success': False, 'error': 'サポートされていないOSです。'})

        if os.path.exists(vscode_path):
            # URLデコードを行う
            decoded_path = urllib.parse.unquote(file_path)
            normalized_path = normalize_path(decoded_path)
            cleaned_path = normalized_path.replace('/viewer/', '/').replace('/viewer-main/', '/').replace('/file_viewer/', '/',1).replace('file_view-main/', '')
            
            full_path = os.path.join(BASE_DIR, cleaned_path)
            
            # ファイルが存在するか確認し、存在しない場合は親ディレクトリを使用
            if os.path.exists(normalized_path):
                target_path = os.path.dirname(normalized_path) if os.path.isfile(normalized_path) else normalized_path
            else:
                # ファイルが見つからない場合は親ディレクトリを使用
                target_path = os.path.dirname(normalized_path)
            
            app.logger.info(f"開こうとしているtarget_path: {repr(target_path)}")
            
            if IS_WINDOWS:
                # Windowsの場合
                subprocess.Popen([vscode_path, target_path])
                # PowerShellを使用してウィンドウをアクティブにする
                # powershell_command = f'(New-Object -ComObject WScript.Shell).AppActivate("Visual Studio Code")'
                # subprocess.Popen(["powershell", "-Command", powershell_command])
            else:
                # macOSの場合
                subprocess.Popen([vscode_path, target_path])
                # AppleScriptを使用してウィンドウをアクティブにしてフルスクリーンにする
                apple_script = '''
                tell application "Visual Studio Code"
                    activate
                end tell

                delay 1
                
                tell application "System Events"
                    tell process "Code"
                        set frontmost to true
                        delay 1
                        keystroke "f" using {command down, control down}
                    end tell
                end tell
                '''
                subprocess.run(["osascript", "-e", apple_script])
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Visual Studio Codeが見つかりません。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/open-folder', methods=['POST'])
def open_folder():
    def is_file_path(file_path):
        # パスがディレクトリっぽくなく、拡張子があるかどうかで判断
        return not file_path.endswith(os.path.sep) and os.path.splitext(file_path)[1] != ""

    data = request.json
    file_path = data.get('path')
    app.logger.info(f"受信したfile_path: {repr(file_path)}")
    
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        # file_pathがファイルの場合は親ディレクトリを、ディレクトリの場合はそのまま使用
        if is_file_path(file_path):
            folder_path = os.path.dirname(file_path)
        else:
            folder_path = file_path

        app.logger.info(f"開こうとしているfolder_path: {repr(folder_path)}")
        
        if os.path.exists(folder_path):
            if platform.system() == "Windows":
                # Windowsの場合、バックスラッシュを使用
                folder_path = folder_path.replace('/', '\\')
                subprocess.Popen(['explorer', folder_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", folder_path])
            else:  # Linux
                subprocess.Popen(["xdg-open", folder_path])
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': f'フォルダが見つかりません: {folder_path}'})
    except Exception as e:
        app.logger.error(f"エラーが発生しました: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


def _parse_port_value(port_value) -> Tuple[bool, Optional[int], str]:
    try:
        port_int = int(port_value)
        if not (0 < port_int < 65536):
            raise ValueError
        return True, port_int, ''
    except (TypeError, ValueError):
        return False, None, '無効なポート番号です。'


@app.route('/stop', methods=['POST'])
def stop_server_process():
    payload = request.get_json(silent=True) or {}
    port_value = payload.get('port', app.config.get('SERVER_PORT'))
    valid, port, error_message = _parse_port_value(port_value)
    if not valid:
        return jsonify({'status': 'error', 'message': error_message, 'port': port_value}), 400

    server_control_logger.info('Stop request received for port %s from %s', port, request.remote_addr)
    result = stop_processes_by_port(port)
    server_control_logger.info('Stop result: %s', result)

    if not result['matched_pids']:
        return jsonify({'status': 'not_found', 'message': '対象ポートで動作中のプロセスはありません。', 'port': port}), 404

    response_payload = {
        'status': 'stopped',
        'port': port,
        'killedPids': result['killed_pids'],
        'errors': result['errors'],
        'selfShutdown': result['self_shutdown'],
        'portActive': result.get('port_active_after_stop', False)
    }

    if result['self_shutdown']:
        response_payload['message'] = 'サーバーはまもなく停止します。'
        schedule_application_shutdown(dict(request.environ), delay=1.0)
    elif result.get('port_active_after_stop'):
        response_payload['status'] = 'partial'
        response_payload['message'] = 'ポートが引き続き使用中です。追加の手動対応が必要な可能性があります。'
    else:
        response_payload['message'] = 'ポートは解放されました。'

    status_code = 200 if not result['errors'] and (result['self_shutdown'] or not result.get('port_active_after_stop', False)) else 207
    return jsonify(response_payload), status_code


@app.route('/status')
def server_status():
    port_value = request.args.get('port', app.config.get('SERVER_PORT'))
    valid, port, error_message = _parse_port_value(port_value)
    if not valid:
        return jsonify({'status': 'error', 'message': error_message, 'port': port_value}), 400

    pids = get_pids_for_port(port)
    status_value = 'running' if pids else 'stopped'
    response_payload = {
        'status': status_value,
        'port': port,
        'pid': pids[0] if pids else None,
        'pids': pids
    }
    server_control_logger.info('Status request for port %s returned %s (PIDs: %s)', port, status_value, pids)
    return jsonify(response_payload)

@app.route('/mindmap/<path:file_path>')
def view_mindmap(file_path):
    """
    指定されたMarkdownファイルをマインドマップとして表示する関数

    Args:
        file_path (str): 処理するファイルのパス

    Returns:
        str: マインドマップを表示するHTMLページ
    """
    app.logger.info(f"view_mindmap関数が呼び出されました。元のfile_path: {repr(file_path)}")
    
    # ファイル名とディレクトリを分離
    directory, file_name = os.path.split(file_path)
    
    # ディレクトリとファイル名を結合（スラッシュを確実に挿入）
    file_path = os.path.join(directory, file_name)

    app.logger.info(f"修正後のfile_path: {repr(file_path)}")
    
    full_path = os.path.join(BASE_DIR, file_path)
    if not os.path.exists(full_path) or not full_path.endswith('.md'):
        app.logger.error(f"ファイルが見つかりません: {full_path}")
        abort(404)

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return render_template('mindmap_view.html', content=content, file_path=file_path)

@app.route('/<path:invalid_path>')
def handle_invalid_path(invalid_path):
    app.logger.info(f"handle_invalid_path関数が呼び出されました。invalid_path: {repr(invalid_path)}")

    # faviconリクエストの場合は何もしない
    if invalid_path == 'favicon.ico':
        abort(404)

    # ネットワークパスの場合
    if invalid_path.startswith('//') or invalid_path.startswith('\\\\'):
        folder_path = os.path.dirname(invalid_path)
    else:
        # ローカルパスの場合
        if os.path.isabs(invalid_path):
            folder_path = os.path.dirname(invalid_path)
        else:
            # BASE_DIRを使用せず、ルートからのパスとして扱う
            full_path = os.path.abspath(os.path.join('/', invalid_path))
            folder_path = os.path.dirname(full_path)

    app.logger.info(f"開こうとしているfolder_path: {repr(folder_path)}")

    # ここでFinderを開く処理を削除または条件付きにする
    # 例えば、特定の条件下でのみFinderを開くようにする
    if folder_path != '/' and os.path.exists(folder_path):
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', folder_path])
            elif platform.system() == 'Windows':
                subprocess.Popen(['explorer', folder_path])
            else:
                subprocess.Popen(['xdg-open', folder_path])
            flash(f'フォルダを開きました: {folder_path}', 'success')
        except Exception as e:
            app.logger.error(f"エラーが発生しました: {str(e)}")
            flash(f'エラーが発生しました: {str(e)}', 'error')
    else:
        flash(f'無効なパス: {invalid_path}', 'error')

    # 元ページにリダイレクト
    return redirect(request.referrer or url_for('index'))

@app.route('/open-path', methods=['POST'])
def open_path():
    data = request.json
    path = data.get('path')
    app.logger.info(f"受信したpath: {repr(path)}")
    
    if not path:
        app.logger.error("パスが指定されていません。")
        return jsonify({'success': False, 'error': 'パスが指定されていません。'})
    
    try:
        # ネットワークパスの場合は直接使用
        if path.startswith('\\\\') or path.startswith('//'):
            folder_path = os.path.dirname(path) if os.path.isfile(path) else path
        else:
            # ローカルパスの場合、BASE_DIRからの相対パスとして扱う
            full_path = os.path.abspath(os.path.join(BASE_DIR, path))
            folder_path = os.path.dirname(full_path) if os.path.isfile(full_path) else full_path

        app.logger.info(f"開こうとしているfolder_path: {repr(folder_path)}")
        
        if os.path.exists(folder_path):
            if platform.system() == 'Windows':
                subprocess.Popen(['explorer', folder_path])
            else:
                subprocess.Popen(['open', folder_path])
            return jsonify({'success': True, 'message': f'フォルダを開きました: {folder_path}'})
        else:
            return jsonify({'success': False, 'error': f'フォルダが見つかりません: {folder_path}'})
    except PermissionError:
        app.logger.error(f"アクセス拒否: {folder_path}")
        return jsonify({'success': False, 'error': f'アクセス拒否: {folder_path}'})
    except Exception as e:
        app.logger.error(f"エラーが発生しました: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def get_items_with_depth(root_path, depth, current_path):
    folders = []
    files = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        relative_path = os.path.relpath(dirpath, root_path)
        if relative_path == '.':
            current_depth = 0
        else:
            current_depth = len(relative_path.split(os.sep))

        if current_depth > depth:
            dirnames[:] = []  # これ以上深いディレクトリは探索しない
            continue

        if current_depth == depth:
            for dirname in dirnames:
                full_path = os.path.join(dirpath, dirname)
                relative_to_current = os.path.relpath(full_path, root_path)
                folders.append({
                    'is_dir': True,
                    'path': normalize_path(os.path.join(current_path, relative_to_current)),
                    'relative_path': normalize_path(relative_to_current)
                })
            
        if current_depth <= depth:
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                relative_to_current = os.path.relpath(full_path, root_path)
                files.append({
                    'is_dir': False,
                    'path': normalize_path(os.path.join(current_path, relative_to_current)),
                    'relative_path': normalize_path(relative_to_current)
                })

        if current_depth == 0 and depth == 0:
            break  # 現在のフォルダのみ処理

    folders.sort(key=lambda x: x['relative_path'].lower())
    files.sort(key=lambda x: x['relative_path'].lower())
    return folders, files

def get_items_with_depth_absolute(root_path, depth):
    """フルパス用のディレクトリ項目取得関数"""
    folders = []
    files = []
    
    try:
        for dirpath, dirnames, filenames in os.walk(root_path):
            relative_path = os.path.relpath(dirpath, root_path)
            if relative_path == '.':
                current_depth = 0
            else:
                current_depth = len(relative_path.split(os.sep))

            if current_depth > depth:
                dirnames[:] = []  # これ以上深いディレクトリは探索しない
                continue

            if current_depth == depth:
                for dirname in dirnames:
                    full_dir_path = os.path.join(dirpath, dirname)
                    folders.append({
                        'is_dir': True,
                        'path': normalize_path(full_dir_path),  # フルパスを使用
                        'relative_path': normalize_path(dirname),
                        'name': dirname
                    })
                
            if current_depth <= depth:
                for filename in filenames:
                    full_file_path = os.path.join(dirpath, filename)
                    files.append({
                        'is_dir': False,
                        'path': normalize_path(full_file_path),  # フルパスを使用
                        'relative_path': normalize_path(filename),
                        'name': filename
                    })

            if current_depth == 0 and depth == 0:
                break  # 現在のフォルダのみ処理

        folders.sort(key=lambda x: x['name'].lower())
        files.sort(key=lambda x: x['name'].lower())
        
    except PermissionError:
        app.logger.warning(f"Permission denied accessing directory: {root_path}")
    except Exception as e:
        app.logger.error(f"Error listing directory {root_path}: {str(e)}")
    
    return folders, files

@app.route('/get_filtered_items/<path:file_path>')
def get_filtered_items(file_path):
    full_path = normalize_path(os.path.join(BASE_DIR, file_path))
    if not os.path.exists(full_path) or not os.path.isdir(full_path):
        return jsonify({'error': '無効なパス'}), 400

    all_folders, all_files = get_items_with_depth(full_path, depth=0, current_path=file_path)
    
    # フォルダとファイルの両方に対してフィルタリングを適用
    filtered_folders = filter_files(all_folders, BASE_DIR)
    filtered_files = filter_files(all_files, BASE_DIR)

    return jsonify({
        'folders': filtered_folders,
        'files': filtered_files
    })

@app.route('/check_ignore')
def check_ignore():
    path = request.args.get('path', '')
    ignored_patterns = load_view_ignore()
    is_ignored = should_ignore(path, ignored_patterns)
    return jsonify({'ignored': is_ignored})

@app.route('/set_base_dir', methods=['POST'])
def set_base_dir():
    global BASE_DIR
    new_base_dir = request.form.get('base_dir')
    if os.path.isdir(new_base_dir):
        BASE_DIR = normalize_path(new_base_dir)
        # セッションにBASE_DIRを保存
        session['BASE_DIR'] = BASE_DIR
        return jsonify({'success': True, 'message': 'ベースディレクトリが更新されました。', 'base_dir': BASE_DIR})
    else:
        return jsonify({'success': False, 'message': '無効なディレクトリパスです。'})

# 既存のbefore_requestは上記のsetup_sessionに統合済み

@app.route('/open-jupyter', methods=['POST'])
def open_jupyter():
    data = request.json
    file_path = data.get('path')
    app.logger.info(f"Received file_path: {file_path}")
    
    if not file_path:
        app.logger.warning("No file path specified")
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        # ファイルパスをベースディレクトリからの相対パスに変換
        relative_path = os.path.relpath(file_path, BASE_DIR)
        app.logger.debug(f"Relative path: {relative_path}")

        jupyter_url = f"{JUPYTER_BASE_URL}/{relative_path}"
        jupyter_url = urllib.parse.unquote(jupyter_url)
        jupyter_url = jupyter_url.replace("\\","/")

        # 'file_viewer'を含まない相対パスを作成
        cleaned_path = jupyter_url.replace('/viewer/', '/').replace('/viewer-main/', '/').replace('/file_viewer/', '/',1).replace('file_viewer-main/', '')
        app.logger.debug(f"Cleaned path: {cleaned_path}")
        
        if cleaned_path.endswith('.ipynb'):
            app.logger.debug(f"Opening .ipynb file: {cleaned_path}")
        elif cleaned_path.startswith('http://') or cleaned_path.startswith('https://'):
            # URLの場合、拡張子があるかチェック
            parsed_url = urllib.parse.urlparse(cleaned_path)
            path = parsed_url.path
            if os.path.splitext(path)[1]:  # 拡張子がある場合
                # ファイル名を除いたディレクトリパスを取得
                cleaned_path = os.path.dirname(cleaned_path)
                app.logger.debug(f"Opening folder for URL with file: {cleaned_path}")
            else:
                # 拡張子がない場合はそのまま開く
                app.logger.debug(f"Opening URL directly: {cleaned_path}")
        # elif os.path.isfile(os.path.join(BASE_DIR, cleaned_path)):
        #     cleaned_path = os.path.dirname(cleaned_path)
        #     app.logger.debug(f"Opening folder for non-.ipynb file: {cleaned_path}")
        # else:
        #     app.logger.debug(f"Opening folder: {cleaned_path}")
        
        # JupyterのURLを構築
        # jupyter_url = f"{JUPYTER_BASE_URL}/{cleaned_path}"
        app.logger.info(f"Opening Jupyter URL: {cleaned_path}")
        
        # ブラウザでJupyterのURLを開く
        # URLをエンコード
        encoded_url = urllib.parse.quote(cleaned_path, safe=':/')  # safeに':'と'/'を指定して、これらの文字はエンコードしない
        # エンコードしたURLを開く
        webbrowser.open(encoded_url)
        # webbrowser.open(cleaned_path)
        
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error occurred while opening Jupyter: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)})

@app.route('/network-image')
def network_image():
    path = request.args.get('path')
    decoded_path = urllib.parse.unquote(path)
    
    if IS_WINDOWS:
        decoded_path = decoded_path.replace("/", "\\")
        try:
            os.startfile(decoded_path)
            return jsonify({'success': True, 'message': '画像を開きました'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    else:
        # Windowsでない場合
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(["open", decoded_path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", decoded_path], check=True)
            return jsonify({'success': True, 'message': '画像を開きました'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/open-local-file')
def open_local_file():
    path = request.args.get('path')
    decoded_path = urllib.parse.unquote(path)
    
    app.logger.info(f"Opening file: {decoded_path}")
    
    if not os.path.exists(decoded_path):
        app.logger.error(f"File not found: {decoded_path}")
        return jsonify({'success': False, 'error': 'ファイルが見つかりません'}), 404

    mime_type, _ = mimetypes.guess_type(decoded_path)
    app.logger.info(f"MIME type: {mime_type}")

    try:
        if platform.system() == 'Darwin':  # macOS
            subprocess.Popen(['open', decoded_path])
        elif platform.system() == 'Windows':
            os.startfile(decoded_path)
        else:  # Linux
            subprocess.Popen(['xdg-open', decoded_path])
        return '', 204  # 成功を示すステータスコードを返しますが、コンテンツは返しません
    except Exception as e:
        app.logger.error(f"Error opening file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/normalize-path', methods=['POST'])
def normalize_path_endpoint():
    data = request.json
    path = data.get('path')
    if not path:
        return jsonify({'success': False, 'error': 'パスが指定されていません。'})
    
    try:
        # パスの前後の引用符を削除
        path = path.strip('"')
        normalized_path = normalize_path(path)
        return jsonify({'success': True, 'normalized_path': normalized_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download/<path:file_path>')
def download_file(file_path):
    full_path = normalize_path(os.path.join(BASE_DIR, file_path))
    if os.path.isfile(full_path):
        return send_file(full_path, as_attachment=True)
    else:
        abort(404)

@app.route('/download-zip/<path:folder_path>')
def download_zip(folder_path):
    full_path = normalize_path(os.path.join(BASE_DIR, folder_path))
    if not os.path.isdir(full_path):
        abort(404)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(full_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, full_path)
                zf.write(file_path, arcname)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{os.path.basename(folder_path)}.zip'
    )

@app.route('/create-folder', methods=['POST'])
def create_folder():
    data = request.json
    target_path = data.get('path')
    folder_name = data.get('folderName')
    if not target_path or not folder_name:
        return jsonify({'success': False, 'error': 'パスまたはフォルダ名が指定されていません。'})
    
    try:
        if not os.path.exists(TEMPLATE_FOLDER):
            return jsonify({'success': False, 'error': 'テンプレートフォルが見つかりません'})
        
        new_folder_path = os.path.join(target_path, folder_name)
        counter = 1
        while os.path.exists(new_folder_path):
            new_folder_name = f'{folder_name} ({counter})'
            new_folder_path = os.path.join(target_path, new_folder_name)
            counter += 1
        
        shutil.copytree(TEMPLATE_FOLDER, new_folder_path)
        
        # フォルダ作成後のアクション
        perform_post_creation_actions(new_folder_path)
        
        return jsonify({'success': True, 'message': 'フォルダが作成されました。', 'path': new_folder_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def perform_post_creation_actions(folder_path):
    # ここに作成後のアクションを記述
    # 例: ログを記録する
    app.logger.info(f"新しいフォルダが作成されました: {folder_path}")
    
    # 例: 特定のファイルを作成する
    with open(os.path.join(folder_path, 'README.md'), 'w') as f:
        f.write(f"# {os.path.basename(folder_path)}\n\nこのフォルダは自動生成されました。")
    
    # 例: 権限を設定する
    # os.chmod(folder_path, 0o755)
    
    # その他必要なアクション...


@app.route('/image-tools', methods=['POST'])
def image_tools():
    data = request.json
    image_paths = data.get('paths', [])
    
    if not image_paths:
        return jsonify({'success': False, 'error': '画像が選択されていません。'})
    
    # セッションに画像パスを保存
    session['image_paths'] = image_paths
    
    return jsonify({'success': True, 'redirect': url_for('view_image_tools')})


@app.route('/view-image-tools')
def view_image_tools():
    image_paths = session.get('image_paths', [])
    if not image_paths:
        return redirect(url_for('index'))
    
    full_paths = [normalize_path(os.path.join(BASE_DIR, path)) for path in image_paths]
    encoded_paths = [urllib.parse.unquote(normalize_path(path.replace(BASE_DIR, '').lstrip('/'))) for path in full_paths]
    app.logger.debug(encoded_paths)
    
    # 作成日時を取得（エラーハンドリングを追加）
    file_dates = []
    for path in full_paths:
        try:
            file_date = datetime.fromtimestamp(os.path.getctime(path)).isoformat()
        except FileNotFoundError:
            file_date = "N/A"  # ファイルが見つからない場合は "N/A" を使用
        except Exception as e:
            app.logger.error(f"Error getting file date for {path}: {str(e)}")
            file_date = "Error"
        file_dates.append(file_date)
    
    # zipオブジェクトを作成して渡す
    zipped_paths = list(zip(full_paths, encoded_paths, file_dates))
    
    return render_template('image_tools.html', zipped_paths=zipped_paths, BASE_DIR=BASE_DIR)

@app.route('/raw/<path:file_path>')
def raw_file(file_path):
    full_path = normalize_path(os.path.join(BASE_DIR, file_path))
    if os.path.exists(full_path):
        return send_file(full_path)
    else:
        abort(404)


def render_csv(file_path):
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        return [row for row in reader]


def render_csv2(file_path):
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        headers = next(reader, None)  # ヘッダー行を読み込む
        
        table_html = '<table class="csv-table">\n'
        
        # ヘッダー行を追加
        if headers:
            table_html += '<thead><tr>\n'
            for header in headers:
                table_html += f'<th>{html.escape(header)}</th>\n'
            table_html += '</tr></thead>\n'
        
        # データ行を追加
        table_html += '<tbody>\n'
        for row in reader:
            table_html += '<tr>\n'
            for cell in row:
                table_html += f'<td>{html.escape(cell)}</td>\n'
            table_html += '</tr>\n'
        table_html += '</tbody>\n'
        
        table_html += '</table>'
        
        return table_html

@app.route('/copy-images-to-clipboard', methods=['POST'])
def copy_images_to_clipboard():
    data = request.json
    image_paths = data.get('paths', [])
    
    if not image_paths:
        return jsonify({'success': False, 'error': '画像が選択されていません。'})
    
    cancelled = False
    processed_images = 0

    try:
        for encoded_path in image_paths:
            if cancelled:
                break

            full_path = os.path.join(BASE_DIR, urllib.parse.unquote(encoded_path))
            file_name = os.path.basename(full_path)
            
            # 画像をクリップボードにコピー
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['osascript', '-e', f'set the clipboard to (read (POSIX file "{full_path}") as JPEG picture)'])
            elif platform.system() == 'Windows':
                app.logger.info(full_path)
                original_image = Image.open(full_path)
                output = io.BytesIO()
                original_image.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                # クリップボードを開く
                win32clipboard.OpenClipboard()
                # クリップボードに画像データを設定
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                # クリップボードを閉じる
                win32clipboard.CloseClipboard()

            else:
                return jsonify({'success': False, 'error': 'サポートされていないOSです。'})
            
            # ポップアップ表示
            if platform.system() == 'Darwin':  # macOS
                result = subprocess.run(['osascript', '-e', f'display dialog "{file_name} をクリップボードにコピーしました。続けますか？" buttons {{"キャンセル", "OK"}} default button "OK"'], capture_output=True, text=True)
                app.logger.debug(f"macOS result.stdout: {result.stdout}")
                app.logger.debug(f"macOS result.stderr: {result.stderr}")
                if 'ユーザによってキャンセルされました' in result.stderr:
                    cancelled = True
            elif platform.system() == 'Windows':
                result = sg.popup_yes_no("{file_name} をクリップボードにコピーしました。続けますか？" ,location=(None,None),keep_on_top =True)
                if result == "No":
                    cancelled = True

            processed_images += 1

        app.logger.debug(cancelled)
        if cancelled:
            return jsonify({'success': True, 'message': f'{processed_images}個の画像をコピーした後、処理を中断しました。'})
        else:
            return jsonify({'success': True, 'message': f'すべての画像（{processed_images}個）をクリップボードにコピーしました。'})
    except Exception as e:
        app.logger.exception("エラーが発生しました")
        return jsonify({'success': False, 'error': str(e)})


@app.template_filter('get_file_date')
def get_file_date(file_path):
    normalized_path = normalize_path(file_path)
    try:
        return datetime.fromtimestamp(os.path.getmtime(normalized_path)).isoformat()
    except FileNotFoundError:
        return "N/A"  # ファイルが見つからない場合は "N/A" を返す

@app.template_filter('get_folder_path')
def get_folder_path(file_path):
    return normalize_path(os.path.dirname(file_path))

@app.route('/html-to-markdown', methods=['POST'])
def html_to_markdown():
    html_content = request.json.get('html', '')
    h = html2text.HTML2Text()
    h.body_width = 0  # 行の折り返しを無効化
    markdown_content = h.handle(html_content)
    return markdown_content

@app.route('/save-markdown', methods=['POST'])
def save_markdown():
    try:
        content = request.json.get('content')
        file_path = request.json.get('path')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get-markdown-content', methods=['POST'])
def get_markdown_content():
    try:
        file_path = request.json.get('path')
        
        # ファイルの内容を読み込む
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return content
    except Exception as e:
        return str(e), 500

@app.route('/excalidraw-local')
def excalidraw_local():
    return render_template('excalidraw_local.html')

@app.route('/create-markdown', methods=['POST'])
def create_markdown():
    """
    Markdownファイルを作成するエンドポイント
    """
    try:
        data = request.json
        directory = data.get('directory', '')
        filename = data.get('filename', '')
        
        # ディレクトリパスを構築
        dir_path = os.path.join(BASE_DIR, directory)
        file_path = os.path.join(dir_path, filename)
        
        # ディレクトリが存在しない場合は作成
        os.makedirs(dir_path, exist_ok=True)
        
        # ファイルが存在しない場合のみ作成
        if not os.path.exists(file_path):
            # 初期内容を設定
            initial_content = f"""# {os.path.splitext(filename)[0]}

                Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

                ## 概要

                ここに概要を書きます。

                ## 内容

                ここに内容を書きます。
                """
            # ファイルを作成して初期内容を書き込む
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(initial_content)
                
        # 相対パスを返す
        relative_path = os.path.relpath(file_path, BASE_DIR)
        normalized_path = normalize_path(relative_path)
        
        return jsonify({
            'success': True,
            'file_path': normalized_path,
            'full_path': normalize_path(file_path)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/save_library', methods=['POST'])
def save_library():
    try:
        library_data = request.get_json()
        
        # 保存先のディレクトリが存在することを確認
        library_dir = os.path.join(app.static_folder, 'excalidraw_lib')
        os.makedirs(library_dir, exist_ok=True)
        
        # ライブラリファイルに保存
        library_path = os.path.join(library_dir, 'my_lib.excalidrawlib')
        with open(library_path, 'w', encoding='utf-8') as f:
            json.dump(library_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({'success': True, 'message': 'ライブラリを保存しました'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/save-excalidraw-data/<path:file_path>', methods=['POST'])
def save_excalidraw_data(file_path):
    """
    Excalidrawデータを保存
    """
    try:
        data = request.json
        full_path = normalize_path(os.path.join(BASE_DIR, file_path))
        excalidraw_dir = os.path.join(os.path.dirname(full_path), 'excalidraw')
        os.makedirs(excalidraw_dir, exist_ok=True)
        
        base_name = os.path.splitext(os.path.basename(full_path))[0]
        if base_name.endswith('.excalidraw'):
            base_name = base_name[:-11]
            
        # excalidrawファイルとして保存
        excalidraw_path = os.path.join(excalidraw_dir, f"{base_name}.excalidraw")
        
        app.logger.info(f"Saving to: {excalidraw_path}")
        app.logger.info(f"Saving {len(data.get('elements', []))} elements")
        
        scene_data = {
            "type": "excalidraw",
            "version": 2,
            "source": request.host_url,
            "elements": data.get("elements", []),
            "appState": data.get("appState", {
                "viewBackgroundColor": "#ffffff",
                "currentItemFontFamily": 1,
                "gridSize": None,
                "theme": "light"
            }),
            "files": data.get("files", {})
        }
        
        # excalidrawファイルを保存
        with open(excalidraw_path, 'w', encoding='utf-8') as f:
            json.dump(scene_data, f, ensure_ascii=False, indent=2)
            
        # バックアップを作成
        create_backup(excalidraw_path, scene_data)
            
        # SVGファイルを保存
        if data.get('svg'):
            svg_path = os.path.join(os.path.dirname(full_path), f"{base_name}_excalidraw.svg")
            with open(svg_path, 'w', encoding='utf-8') as f:
                f.write(data['svg'])
            app.logger.info(f"Successfully saved SVG to {svg_path}")
            
        app.logger.info("Data saved successfully")
        return jsonify({"success": True})
    except Exception as e:
        app.logger.error(f"Error saving excalidraw data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/excalidraw-server/<path:file_path>')
def excalidraw_server(file_path):
    """
    サーバー側で状態を管理するExcalidrawエディタを表示
    """
    full_path = normalize_path(os.path.join(BASE_DIR, file_path))
    if not os.path.exists(os.path.dirname(full_path)):
        abort(404)
        
    current_item = f"Excalidraw Server - {os.path.basename(file_path)}"
    return render_template('excalidraw_server.html', 
                        file_path=file_path, 
                        full_path=full_path, 
                        current_item=current_item)

@app.route('/load-excalidraw-data/<path:file_path>')
def load_excalidraw_data(file_path):
    """
    Excalidrawデータをロード
    """
    try:
        full_path = normalize_path(os.path.join(BASE_DIR, file_path))
        excalidraw_dir = os.path.join(os.path.dirname(full_path), 'excalidraw')
        base_name = os.path.splitext(os.path.basename(full_path))[0]
        if base_name.endswith('.excalidraw'):
            base_name = base_name[:-11]
            
        excalidraw_path = os.path.join(excalidraw_dir, f"{base_name}.excalidraw")
        
        app.logger.info(f"Loading from: {excalidraw_path}")
        
        initial_data = {
            "type": "excalidraw",
            "version": 2,
            "source": request.host_url,
            "elements": [],
            "appState": {
                "viewBackgroundColor": "#ffffff",
                "currentItemFontFamily": 1,
                "gridSize": None,
                "theme": "light",
                "name": "Excalidraw"
            },
            "files": {}
        }
        
        if os.path.exists(excalidraw_path):
            with open(excalidraw_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # データの整合性チェックと正規化
                if not isinstance(data.get('elements'), list):
                    data['elements'] = []
                if not isinstance(data.get('files'), dict):
                    data['files'] = {}
                if not isinstance(data.get('appState'), dict):
                    data['appState'] = initial_data['appState']
                    
                app.logger.info(f"Loaded {len(data['elements'])} elements")
                return jsonify(data)
        else:
            app.logger.info("No existing file found, returning initial data")
            return jsonify(initial_data)
            
    except Exception as e:
        app.logger.error(f"Error loading excalidraw data: {str(e)}")
        return jsonify(initial_data), 200  # エラー時も初期データを返す

def create_backup(file_path, data):
    """バックアップを作成する関数"""
    
    try:
        # 元のexcalidrawファイルと同じディレクトリにバックアップディレクトリを作成
        parent_dir = os.path.dirname(os.path.dirname(file_path))  # excalidrawフォルダの親ディレクトリ
        backup_dir = os.path.join(parent_dir, 'excalidraw_bkk')
        os.makedirs(backup_dir, exist_ok=True)
        
        # 最新のバックアップを確認
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        pattern = os.path.join(backup_dir, f"{base_name}_*.excalidraw")
        existing_backups = glob.glob(pattern)
        
        current_time = time.time()
        
        # 既存のバックアップがある場合、最新のものとの時間差をチェック
        if existing_backups:
            latest_backup = max(existing_backups, key=os.path.getctime)
            last_backup_time = os.path.getctime(latest_backup)
            
            # 最後のバックアップから1分以内の場合はスキップ
            if current_time - last_backup_time < 60:  # 60秒 = 1分
                app.logger.info("前回のバックアップから1分経過していないため、バックアップをスキップします")
                return
        
        # タイムスタンプを含むバックアップファイル名を生成
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{base_name}_{timestamp}.excalidraw"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # バックアップを保存
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 古いバックアップを削除
        cleanup_old_backups(file_path, backup_dir)
        
        app.logger.info(f"バックアップを作成しました: {backup_path}")
        
    except Exception as e:
        app.logger.error(f"バックアップの作成に失敗しました: {str(e)}")

def cleanup_old_backups(file_path, backup_dir):
    """古いバックアップを削除する関数"""
    MAX_BACKUPS = 20  # バックアップの最大保持数を定義
    
    try:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        pattern = os.path.join(backup_dir, f"{base_name}_*.excalidraw")
        backup_files = sorted(glob.glob(pattern), key=os.path.getctime, reverse=True)
        
        # MAX_BACKUPS以上のバックアップがある場合、古いものを削除
        for old_backup in backup_files[MAX_BACKUPS:]:
            os.remove(old_backup)
            app.logger.info(f"古いバックアップを削除しました: {old_backup}")
            
    except Exception as e:
        app.logger.error(f"バックアップのクリーンアップに失敗しました: {str(e)}")

@app.route('/get-excalidraw-backups/<path:file_path>')
def get_excalidraw_backups(file_path):
    try:
        full_path = normalize_path(os.path.join(BASE_DIR, file_path))
        # excalidrawフォルダの親ディレクトリを取得
        parent_dir = os.path.dirname(full_path)  # 修正: os.path.dirname(os.path.dirname(full_path))を変更
        backup_dir = os.path.join(parent_dir, 'excalidraw_bkk')
        
        app.logger.info(f"Looking for backups in: {backup_dir}")  # ログ追加
        
        if not os.path.exists(backup_dir):
            app.logger.info(f"Backup directory does not exist: {backup_dir}")  # ログ追加
            return jsonify({'backups': []})
            
        base_name = os.path.splitext(os.path.basename(full_path))[0]
        if base_name.endswith('.excalidraw'):
            base_name = base_name[:-11]
            
        pattern = os.path.join(backup_dir, f"{base_name}_*.excalidraw")
        backup_files = glob.glob(pattern)
        
        app.logger.info(f"Found {len(backup_files)} backup files")  # ログ追加
        app.logger.info(f"Pattern used: {pattern}")  # ログ追加
        
        # バックアップファイルの情報を取得
        backups = []
        for backup_file in backup_files:
            backup_name = os.path.basename(backup_file)
            backup_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
            backups.append({
                'name': backup_name,
                'time': backup_time.strftime('%Y-%m-%d %H:%M:%S'),
                'path': backup_file
            })
            
        # 時間順に並び替え（新しい順）
        backups.sort(key=lambda x: x['time'], reverse=True)
        
        app.logger.info(f"Returning {len(backups)} backups")  # ログ追加
        return jsonify({'backups': backups})
    except Exception as e:
        app.logger.error(f"Error in get_excalidraw_backups: {str(e)}")  # ログ追加
        return jsonify({'error': str(e)}), 500

@app.route('/restore-excalidraw-backup', methods=['POST'])
def restore_excalidraw_backup():
    try:
        data = request.json
        backup_path = data.get('backup_path')
        current_path = data.get('current_path')
        
        app.logger.debug(f"backup path: {backup_path}")
        app.logger.debug(f"original current path: {current_path}")
        
        # current_pathをexcalidrawフォルダ内のパスに修正
        excalidraw_dir = os.path.join(os.path.dirname(current_path), 'excalidraw')
        current_path = os.path.join(excalidraw_dir, os.path.basename(current_path))
        
        app.logger.debug(f"modified current path: {current_path}")
        
        if not backup_path or not current_path:
            return jsonify({'error': '必要なパラメータが不足しています'}), 400
            
        # バックアップファイルを読み込む
        with open(backup_path, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
            
        # 現在のファイルが存在する場合は削除
        if os.path.exists(current_path):
            os.remove(current_path)
            app.logger.info(f"既存のファイルを削除しました: {current_path}")
            
        # 新しいファイルとして保存
        with open(current_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
        app.logger.info(f"バックアップを復元しました: {current_path}")
        return jsonify({'success': True, 'message': 'バックアップを復元しました'})
    except Exception as e:
        app.logger.error(f"バックアップの復元に失敗しました: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/save-selected-svg/<path:file_path>', methods=['POST'])
def save_selected_svg(file_path):
    try:
        data = request.json
        svg_content = data.get('svg')
        filename = data.get('filename')
        
        if not svg_content or not filename:
            return jsonify({"success": False, "error": "必要なデータが不足しています"}), 400
            
        # ファイル名をUTF-8でデコード
        filename = urllib.parse.unquote(filename)
        
        # 保存先のパスを構築
        current_dir = os.path.dirname(file_path)
        save_dir = os.path.join(BASE_DIR, current_dir)
        os.makedirs(save_dir, exist_ok=True)
        
        # ファイル名を正規化（ただし日本語は保持）
        safe_filename = "".join([
            c for c in filename 
            if c.isalnum() or c.isspace() or c in "._-()[]{}あ-んア-ンー一-龯"
        ])
        safe_filename = safe_filename.strip() + '.svg'
        svg_path = os.path.join(save_dir, safe_filename)
        
        # SVGファイルを保存（UTF-8で保存）
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)
            
        app.logger.info(f"Successfully saved SVG to {svg_path}")
        
        # パスをクリップボードにコピー
        try:
            pyperclip.copy(svg_path)
            app.logger.info(f"Copied path to clipboard: {svg_path}")
        except Exception as e:
            app.logger.error(f"Failed to copy path to clipboard: {str(e)}")
        
        # 相対パスを生成
        relative_path = os.path.relpath(svg_path, BASE_DIR)
        temp_url = url_for('serve_file', file_path=relative_path)
        
        return jsonify({
            "success": True,
            "fileUrl": temp_url,
            "savedPath": relative_path
        })
        
    except Exception as e:
        app.logger.error(f"Error saving SVG: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# 新しいエンドポイントを追加
@app.route('/serve-file/<path:file_path>')
def serve_file(file_path):
    try:
        full_path = os.path.join(BASE_DIR, file_path)
        return send_file(full_path)
    except Exception as e:
        app.logger.error(f"Error serving file: {str(e)}")
        abort(404)

@app.route('/upload')
def upload_page():
    """アップロードページを表示"""
    return render_template('upload.html')

@app.route('/upload-files', methods=['POST'])
def upload_files():
    try:
        files = request.files.getlist('files[]')
        current_path = request.form.get('current_path', '')
        
        app.logger.info(f"Received upload request - current_path: {current_path}")
        app.logger.info(f"Number of files: {len(files)}")
        
        # 現在のディレクトリを取得
        current_dir = os.path.dirname(current_path)
        base_upload_dir = os.path.join(BASE_DIR, current_dir, 'uploads')
        
        # アップロードフォルダの種類を定義
        UPLOAD_CATEGORIES = {
            'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'],
            'documents': ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt', '.md'],
            'presentations': ['.ppt', '.pptx', '.key', '.odp'],
            'spreadsheets': ['.xls', '.xlsx', '.csv', '.ods'],
            'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'emails': ['.msg', '.eml', '.emlx'],
            'others': []
        }
        
        uploaded_files = []
        
        for file in files:
            if file:
                # ファイル名をデコード
                filename = file.filename
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8')
                
                # URLエンコードされている場合はデコード
                try:
                    filename = urllib.parse.unquote(filename)
                except:
                    pass

                app.logger.info(f"Original filename: {filename}")
                
                # 拡張子を取得
                extension = os.path.splitext(filename)[1].lower()
                
                # ファイルの種類に基づいてサブフォルダを決定
                category = 'others'
                for cat, exts in UPLOAD_CATEGORIES.items():
                    if extension in exts:
                        category = cat
                        break
                
                # カテゴリフォルダのパスを作成
                category_dir = os.path.join(base_upload_dir, category)
                os.makedirs(category_dir, exist_ok=True)
                
                # 禁止文字を置換（ファイルシステムで使用できない文字を除去）
                safe_filename = re.sub(r'[<>:"/\\|?*]', '', filename)
                safe_filename = safe_filename.strip()
                
                # ファイルの保存パスを構築
                file_path = os.path.join(category_dir, safe_filename)
                
                app.logger.info(f"Safe filename: {safe_filename}")
                app.logger.info(f"Saving file to: {file_path}")
                
                # ファイル名が重複する場合、連番を付加
                base, ext = os.path.splitext(safe_filename)
                counter = 1
                while os.path.exists(file_path):
                    new_filename = f"{base}_{counter}{ext}"
                    file_path = os.path.join(category_dir, new_filename)
                    counter += 1
                
                # ファイルを保存
                file.save(file_path)
                
                # 相対パスを作成（BASE_DIRからの相対パス）
                relative_path = os.path.relpath(file_path, BASE_DIR)
                
                app.logger.info(f"File saved successfully. Relative path: {relative_path}")
                
                uploaded_files.append({
                    'name': os.path.basename(file_path),
                    'path': relative_path
                })
        
        return jsonify({
            'success': True,
            'files': uploaded_files
        })
        
    except Exception as e:
        app.logger.error(f"アップロードエラー: {str(e)}")
        app.logger.error(f"詳細なエラー情報: ", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/delete-items', methods=['POST'])
def delete_items():
    try:
        items = request.json.get('items', [])
        for item in items:
            path = item['path']
            item_type = item['type']
            full_path = os.path.join(BASE_DIR, path)
            
            if item_type == 'folder':
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
                
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/create-folder-shortcut', methods=['POST'])
def create_folder_shortcut():
    try:
        folder_path = request.form.get('folder_path')
        current_path = request.form.get('current_path')
        
        # フォルダパスの処理
        # Windowsの場合はバックスラッシュに変換する必要があるかもしれません
        folder_path = os.path.normpath(folder_path)
        
        return jsonify({
            'success': True,
            'folderPath': folder_path
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/rename', methods=['POST'])
def rename_item():
    try:
        data = request.get_json()
        old_path = os.path.join(BASE_DIR, data['old_path'].lstrip('/'))
        new_name = data['new_name']
        parent_dir = os.path.dirname(old_path)
        new_path = os.path.join(parent_dir, new_name)

        # ファイルが存在するか確認
        if not os.path.exists(old_path):
            return jsonify({'error': 'ファイルが見つかりません'}), 404

        # 新しい名前のファイルが既に存在するか確認
        if os.path.exists(new_path):
            return jsonify({'error': '同じ名前のファイルが既に存在します'}), 409

        # リネーム実行
        os.rename(old_path, new_path)
        return jsonify({'success': True, 'new_path': os.path.relpath(new_path, BASE_DIR)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import argparse

    debug_env = os.environ.get('FILE_VIEWER_DEBUG', '1')
    default_debug = debug_env.lower() not in ('0', 'false', 'no')

    parser = argparse.ArgumentParser(description='File Viewer Web Application')
    parser.add_argument('--host', default=DEFAULT_HOST, help='Bind host (default: %(default)s)')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Bind port (default: %(default)s)')
    parser.add_argument('--debug', dest='debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-debug', dest='debug', action='store_false', help='Disable debug mode')
    parser.set_defaults(debug=default_debug)

    args = parser.parse_args()

    app.secret_key = 'your_secret_key_here'  # セッション用の秘密鍵
    app.config['SERVER_HOST'] = args.host
    app.config['SERVER_PORT'] = args.port
    app.jinja_env.globals['SERVER_PORT'] = args.port

    app.run(debug=args.debug, host=args.host, port=args.port)
