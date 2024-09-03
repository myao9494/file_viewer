import os
import fnmatch
import platform
from flask import Flask, render_template, request, send_file, abort, url_for, Response, send_from_directory, jsonify, redirect, flash, session
import re
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
import os.path
import webbrowser
# import urllib.parse


app = Flask(__name__, static_folder='static')

# OSの種類を判別
IS_WINDOWS = platform.system() == 'Windows'

# パスの区切り文字を統一する関数を追加import urllib.parse

def normalize_path(path):
    n_path = path.replace('\\', '/')
    n_path = os.path.normpath(path)
    # n_path = path.replace("%5C","/")
    return n_path

# グローバル変数としてBASE_DIRを定義
global BASE_DIR

# ベースディレクトリの設定

mac_BASE_DIR = r"/Users/sudoupousei/000_work"  # Windowsの場合
win_BASE_DIR = r"C:\Users\kabu_server\000_work"
BASE_DIR = normalize_path(mac_BASE_DIR if not IS_WINDOWS else win_BASE_DIR)

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
    if file_extension == '.csv':
        content = render_csv(full_path)
        return render_template('csv_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR, current_item=current_item)

    # ipynbファイルの場合
    if file_extension == '.ipynb':
        # ファイルパスをベースディレクトリからの相対パスに変換
        relative_path = os.path.relpath(full_path, BASE_DIR)
        # JupyterのURLを構築
        jupyter_url = f"{JUPYTER_BASE_URL}/{relative_path}"
        
        # ブラウザでJupyterのURLを開く
        webbrowser.open(jupyter_url)
        
        # ユーザーに通知を返す
        flash('Jupyter Notebookを開きました。', 'info')
        return redirect(url_for('index'))

    # テキストファイルまたは特定の拡張子の場合
    if mime_type and mime_type.startswith('text/') or file_extension in ['.txt', '.py', '.js', '.css', '.json', '.license', '.yml', '.yaml', '.xml', '.ini', '.cfg', '.conf']:
        content = get_file_content(full_path, 'text')
        return render_template('view_file.html', content=content, file_path=file_path, full_path=full_path, current_item=current_item)

    # その他のファイルはダウンロード
    return send_file(full_path, as_attachment=True)

@app.route('/raw/<path:file_path>')
def raw_file(file_path):
    full_path = normalize_path(os.path.join(BASE_DIR, file_path))
    if os.path.exists(full_path):
        return send_file(full_path)
    else:
        abort(404)

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
            subprocess.Popen([vscode_path, normalize_path(os.path.dirname(file_path))])
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
        folder_path = os.path.dirname(file_path)
        app.logger.info(f"開こうとしているfolder_path: {repr(folder_path)}")
        
        if os.path.exists(folder_path):
            if IS_WINDOWS:
                # Windowsの場合、バックスラッシュを使用
                folder_path = folder_path.replace('/', '\\')
                subprocess.Popen(['explorer', folder_path])
            else:
                subprocess.Popen(['open', folder_path])
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

    # パスの正規化
    normalized_path = normalize_path(invalid_path)
    
    # ネットワークパスの場合
    if normalized_path.startswith('//') or normalized_path.startswith('\\\\'):
        folder_path = os.path.dirname(normalized_path)
    else:
        # ローカルパスの場合
        if os.path.isabs(normalized_path):
            folder_path = os.path.dirname(normalized_path)
        else:
            # BASE_DIRを使用せず、ルートからのパスとして扱う
            full_path = os.path.abspath(os.path.join('/', normalized_path))
            folder_path = os.path.dirname(full_path)

    app.logger.info(f"開こうとしているfolder_path: {repr(folder_path)}")

    try:
        if os.path.exists(folder_path):
            if IS_WINDOWS:
                # Windowsの場合、バックスラッシュを使用
                folder_path = folder_path.replace('/', '\\')
                subprocess.Popen(['explorer', folder_path])
            else:
                subprocess.Popen(['open', folder_path])
            flash(f'フォルダを開きました: {folder_path}', 'success')
        else:
            flash(f'フォルダが見つかりません: {folder_path}', 'error')
    except Exception as e:
        app.logger.error(f"エラーが発生しました: {str(e)}")
        flash(f'エラーが発生しました: {str(e)}', 'error')

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
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        # ファイルパスをベースディレクトリからの相対パスに変換
        relative_path = os.path.relpath(file_path, BASE_DIR)
        # 'file_viewer'を含まない相対パスを作成
        cleaned_path = relative_path.replace('file_viewer/', '')
        
        # .ipynbの拡張子がない場合、ディレクトリパスを使用
        if not cleaned_path.endswith('.ipynb'):
            cleaned_path = os.path.dirname(cleaned_path)
        
        # JupyterのURLを構築
        jupyter_url = f"{JUPYTER_BASE_URL}/{cleaned_path}"
        
        # ブラウザでJupyterのURLを開く
        webbrowser.open(jupyter_url)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/network-image')
def network_image():
    path = request.args.get('path')
    decoded_path = urllib.parse.unquote(path)
    # ここでネットワークパスから画像を読み込み、送信する処理を実装
    # 注意: セキュリティを考慮し、アクセス可能なパスを制限することを推奨
    return send_file(decoded_path, mimetype='image/png')


if __name__ == '__main__':
    app.secret_key = 'your_secret_key_here'  # セッション用の秘密鍵
    # デバッグモードでアプリケーションを実行
    app.run(debug=True, host='0.0.0.0', port=5001)