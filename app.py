import os
import fnmatch
from flask import Flask, render_template, request, send_file, abort, url_for, Response, send_from_directory, jsonify, redirect, flash
import re
import csv
from utils.file_handler import get_file_content, get_file_list
from utils.search import search_files
from utils.file_utils import filter_files
from utils.markdown_renderer import render_markdown
from utils.csv_renderer import render_csv
import mimetypes
import subprocess
from markdown import markdown
import json
import html
import os.path

app = Flask(__name__, static_folder='static')

# ベースディレクトリの設定
BASE_DIR = "/Users/sudoupousei/000_work"

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
    # すべてのファ
    all_files = get_file_list(BASE_DIR)
    # フィルタリングを適用
    files = filter_files(all_files, BASE_DIR)
    # index.htmlテンプレートをレンダリングし、ファイルリストを渡す
    return render_template('index.html', files=files)

@app.route('/view', defaults={'file_path': ''})
@app.route('/view/', defaults={'file_path': ''})
@app.route('/view/<path:file_path>')
def view_file(file_path):
    # 末尾のスラッシュを削除
    if file_path.endswith('/'):
        return redirect(url_for('view_file', file_path=file_path.rstrip('/')))

    # file_pathが空の場合、ルートディレクトリを表示
    if not file_path:
        full_path = BASE_DIR
        
    else:
        # 先頭のスラッシュを除去（もし存在する場合）
        file_path = file_path.lstrip('/')
        full_path = os.path.join(BASE_DIR, file_path)
        

    if not os.path.exists(full_path):
        abort(404)  # ファイルが存在しない場合は404エラー

    # ディレクトリの場合
    if os.path.isdir(full_path):
        # ディレクトリ内のファイルとフォルダのリストを取得
        items = os.listdir(full_path)
        # ファイルとフォルダを分けてソート
        folders = sorted([item for item in items if os.path.isdir(os.path.join(full_path, item))])
        files = sorted([item for item in items if os.path.isfile(os.path.join(full_path, item))])
        parent_path = os.path.dirname(file_path) if file_path != '' else None
        # ディレクトリ表示用のテンプレートをレンダリング
        return render_template('directory_view.html', folders=folders, files=files, current_path=file_path, parent_path=parent_path)

    # ファイルの場合
    file_extension = os.path.splitext(full_path)[1].lower()
    
    # ファイルタイプごとのレンダリング方法を定義
    renderers = {
        '.md': ('markdown_view.html', render_markdown),
        '.csv': ('csv_view.html', render_csv),
        '.html': ('view_file.html', lambda path: get_file_content(path, 'html')),
    }

    # MIMEタイプを取得
    mime_type, _ = mimetypes.guess_type(full_path)

    # SVGファイルの場合
    if file_extension == '.svg':
        with open(full_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_content = svg_content.replace('<svg', '<svg id="svg-content"', 1)
        return render_template('svg_view.html', svg_content=svg_content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR)

    # 画像ファイルの場合
    if mime_type and mime_type.startswith('image/'):
        app.logger.info(f"Rendering image: {file_path}")
        return render_template('image_view.html', file_path=file_path, full_path=full_path)

    # PDFファイル場合
    if file_extension == '.pdf':
        return send_file(full_path, mimetype='application/pdf')

    # Markdownファイルの場合
    if file_extension == '.md':
        content = render_markdown(full_path)
        return render_template('markdown_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR)

    # CSVファイルの場合
    if file_extension == '.csv':
        content = render_csv(full_path)
        return render_template('csv_view.html', content=content, file_path=file_path, full_path=full_path, BASE_DIR=BASE_DIR)

    # テキストファイルまたは特定の拡張子の場合
    if mime_type and mime_type.startswith('text/') or file_extension in ['.txt', '.py', '.js', '.css', '.json', '.ipynb', '.license', '.yml', '.yaml', '.xml', '.ini', '.cfg', '.conf']:
        content = get_file_content(full_path, 'text')
        return render_template('view_file.html', content=content, file_path=file_path, full_path=full_path)

    # その他のファイルはダウンロード
    return send_file(full_path, as_attachment=True)

@app.route('/raw/<path:file_path>')
def raw_file(file_path):
    full_path = os.path.join(BASE_DIR, file_path)
    if os.path.exists(full_path):
        return send_file(full_path)
    else:
        abort(404)

@app.route('/search')
def search():
    """
    ファイル検索を行う関数

    Returns:
        str: 検索結果含むレンダリングされたHTMLンプレート
    """
    # クエリパラメータから検索語を取得
    query = request.args.get('q', '')
    # ファイル検索を実行
    results = search_files(BASE_DIR, query)
    # 検結果をフィルタリング
    filtered_results = filter_files(results, BASE_DIR)
    # 検索��含むindex.htmlテンプレートをレンダリング
    return render_template('index.html', files=filtered_results, search_query=query)

@app.route('/open-in-code', methods=['POST'])
def open_in_code():
    data = request.json
    file_path = data.get('path')
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        # macOSの場合
        vscode_path = '/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
        # Windowsの場合
        # vscode_path = 'C:\\Program Files\\Microsoft VS Code\\Code.exe'
        
        if os.path.exists(vscode_path):
            subprocess.Popen([vscode_path, os.path.dirname(file_path)])
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Visual Studio Codeがつりせん。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/open-folder', methods=['POST'])
def open_folder():
    data = request.json
    file_path = data.get('path')
    if not file_path:
        return jsonify({'success': False, 'error': 'ファイルパスが指定されていません。'})
    
    try:
        folder_path = os.path.dirname(file_path)
        if os.path.exists(folder_path):
            # macOSの場合
            subprocess.Popen(['open', folder_path])
            # Windowsの場合
            # subprocess.Popen(['explorer', folder_path])
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'フォルダが見つかりません。'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/mindmap/<path:file_path>')
def view_mindmap(file_path):
    """
    指定されたMarkdownファイルをマインドマップとして表示する関数

    Args:
        file_path (str): 処理するファイルのパス

    Returns:
        str: インドマップを表示するHTMLページ
    """
    full_path = os.path.join(BASE_DIR, file_path)
    if not os.path.exists(full_path) or not full_path.endswith('.md'):
        abort(404)

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return render_template('mindmap_view.html', content=content, file_path=file_path)

@app.route('/<path:invalid_path>')
def handle_invalid_path(invalid_path):
    """
    無効なパスへのアクセスを処理し、適切にリダイレクトまたはエラーを表示する関数

    Args:
        invalid_path (str): アクセスされたパス

    Returns:
        redirect: 適切なURLにリダイレクト、またはフォルダを開く、または404エラーページ
    """
    # ベースディレクトリのパスを正規表現でエスケープ
    escaped_base_dir = re.escape(BASE_DIR)
    
    # ベースディレクトリのパスを除去
    match = re.match(f'^{escaped_base_dir}/?(.*)$', '/' + invalid_path)
    if match:
        relative_path = match.group(1)
        # ファイルビューアのパスを構築
        viewer_path = url_for('view_file', file_path=relative_path)
        flash('無効なURLです。正しいページにリダイレクトします。', 'warning')
        return redirect(viewer_path)
    
    # ベースディレクトリのパスが含まれていない場合
    full_path = '/' + invalid_path  # パスの先頭に'/'を追加
    if os.path.exists(full_path):
        if os.path.isdir(full_path):
            folder_path = full_path
        else:
            folder_path = os.path.dirname(full_path)
        
        if os.path.exists(folder_path):
            try:
                # macOSの場合
                subprocess.Popen(['open', folder_path])
                # Windowsの場合
                # subprocess.Popen(['explorer', folder_path])
                flash(f'フォルダを開きました: {folder_path}', 'info')
                return redirect(url_for('index'))
            except Exception as e:
                flash(f'フォルダを開く際にエラーが発生しました: {str(e)}', 'error')
                return redirect(url_for('index'))
    
    # パスが存在しない場合は404エラー
    flash('指定されたページは存在しません。', 'error')
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.secret_key = 'your_secret_key_here'  # フラッシュメッセージのために必要
    # デバッグモードでアプリケーションを実行
    app.run(debug=True, host='0.0.0.0', port=5001)