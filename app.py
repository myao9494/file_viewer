import os,re
# import fnmatch
import platform
from flask import Flask, render_template, request, send_file, abort, url_for, Response, send_from_directory, jsonify, redirect, flash, session
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
# import json
import html
# import os.path
import webbrowser
import pathlib
import urllib.parse
import zipfile
import io
import shutil
from itertools import zip_longest  # この行を追加
# import pyperclip
from PIL import Image
from datetime import datetime
if platform.system() == "Windows":
    import win32clipboard
    import PySimpleGUI as sg
    import win32com.client


app = Flask(__name__, static_folder='static')

# OSの種類を判別
IS_WINDOWS = platform.system() == 'Windows'

# パスの区切り文字を統一する関数を追加import urllib.parse

def normalize_path(path):
    # n_path = path.replace('\\', '/')
    # n_path = os.path.normpath(path)
    # n_path = path.replace("%5C","/")
    n_path = pathlib.Path(path).as_posix()
    return n_path

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
# JupyterのベースURLを設定
JUPYTER_BASE_URL =  'http://localhost:8888/lab/tree' 

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
    app.logger.info(f"view_file関数が呼び出されました。file_path: {repr(file_path)}")

    depth = int(request.args.get('depth', 0))

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

    # ディレクトリの場合
    if os.path.isdir(full_path):
        app.logger.info(f"ディレクトリを表示します: {full_path}")
        folders, files = get_items_with_depth(full_path, depth, file_path)
        parent_path = os.path.dirname(file_path) if file_path != '' else None
        return render_template('directory_view.html', folders=folders, files=files, current_path=file_path, parent_path=parent_path, full_path=full_path, depth=depth, current_item=current_item)

    # ファイルの場合
    file_extension = os.path.splitext(full_path)[1].lower()
    
    # MIMEタイプを取得
    mime_type, _ = mimetypes.guess_type(full_path)

    # .xdwファイルの場合
    if file_extension == '.xdw':
        return send_file(full_path, as_attachment=True)

    # SVGファイルの場合
    if file_extension == '.svg':
        with open(full_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_content = svg_content.replace('<svg', '<svg id="svg-content"', 1)
        return render_template('svg_view.html', svg_content=svg_content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)

    # 画像ファイルの場合
    if mime_type and mime_type.startswith('image/'):
        app.logger.info(f"Rendering image: {file_path}")
        return render_template('image_view.html', file_path=file_path, full_path=full_path, current_item=current_item)

    # PDFファイル場合
    if file_extension == '.pdf':
        return send_file(full_path, mimetype='application/pdf')

    # Markdownファイルの場合
    if file_extension == '.md':
        content = render_markdown(full_path)
        folder_path = os.path.dirname(full_path)
        return render_template('markdown_view.html', content=content, file_path=file_path, full_path=full_path, folder_path=folder_path, BASE_DIR=BASE_DIR, current_item=current_item)

    # CSVファイルの場合
    # CSVファイルの場合
    # if file_extension == '.csv':
    #     content = render_csv(full_path)
    #     return render_template('data_table_view_tabulator.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
    # if file_extension == '.csv':
    #     content = render_csv(full_path)
    #     return render_template('data_table_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
    
    # if file_extension == '.csv':
    #     content = render_csv(full_path)
    #     return render_template('ag_grid_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)
    if file_extension == '.csv':
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
    if file_extension in ['.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt']:
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
            vscode_path = '/Applications/Cursor.app/Contents/MacOS/Cursor'

        if os.path.exists(vscode_path):
            # URLデコードを行う
            decoded_path = urllib.parse.unquote(file_path)
            normalized_path = normalize_path(file_path)
            target_path = os.path.dirname(normalized_path) if os.path.isfile(normalized_path) else normalized_path
            
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
            
            target_path = os.path.join(BASE_DIR, cleaned_path)
            target_path = os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
            
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
    data = request.json
    file_path = data.get('path')
    app.logger.info(f"受信したfile_path: {repr(file_path)}")
    
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        # file_pathがファイルの場合は親ディレクトリを、ディレクトリの場合はそのまま使用
        if os.path.isfile(file_path):
            # .lnkファイルの場合、リンク先を取得
            if file_path.lower().endswith('.lnk') and platform.system() == "Windows":
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(file_path)
                target_path = shortcut.Targetpath
                folder_path = os.path.dirname(target_path) if os.path.isfile(target_path) else target_path
            else:
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

@app.before_request
def before_request():
    global BASE_DIR
    # セッションからBASE_DIRを取得（存在しない場合はデフォルト値を使用）
    BASE_DIR = session.get('BASE_DIR', BASE_DIR)

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

# @app.route('/check-path-type', methods=['POST'])
# def check_path_type():
#     data = request.json
#     path = data.get('path')
#     if os.path.isfile(path):
#         return jsonify({'type': 'file'})
#     elif os.path.isdir(path):
#         return jsonify({'type': 'folder'})
#     else:
#         return jsonify({'type': 'invalid'})

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
            return jsonify({'success': False, 'error': 'テンプレートフォルダが見つかりません。'})
        
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

# @app.route('/raw/<path:file_path>')
# def raw_file(file_path):
#     full_path = os.path.join(BASE_DIR, file_path)
#     return send_file(full_path)

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

if __name__ == '__main__':
    app.secret_key = 'your_secret_key_here'  # セッション用の秘密鍵
    # デバッグモードでアプリケーションを実行
    app.run(debug=True, host='0.0.0.0', port=5001)