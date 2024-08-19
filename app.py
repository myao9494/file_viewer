import os
import fnmatch
from flask import Flask, render_template, request, send_file, abort, url_for
import re
import csv
# import io
from utils.file_handler import get_file_content, get_file_list
from utils.search import search_files
from utils.file_utils import filter_files
from utils.markdown_renderer import render_markdown
from utils.ipynb_renderer import render_ipynb
from utils.csv_renderer import render_csv

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
    # すべてのファイルを取得
    all_files = get_file_list(BASE_DIR)
    # フィルタリングを適用
    files = filter_files(all_files, BASE_DIR)
    # index.htmlテンプレートをレンダリングし、ファイルリストを渡す
    return render_template('index.html', files=files)

@app.route('/view/<path:file_path>')
def view_file(file_path):
    """
    指定されたファイルを表示する関数

    Args:
        file_path (str): 表示するファイルのパス

    Returns:
        str: レンダリングされたHTMLまたはファイル内容
    """
    # フルパスを作成
    full_path = os.path.join(BASE_DIR, file_path)
    if not os.path.exists(full_path):
        abort(404)  # ファイルが存在しない場合は404エラー

    # ファイル拡張子を取得
    file_extension = os.path.splitext(full_path)[1].lower()
    
    # ファイルタイプごとのレンダリング方法を定義
    renderers = {
        '.md': ('markdown_view.html', render_markdown),
        '.csv': ('csv_view.html', render_csv),
        '.ipynb': ('ipynb_view.html', render_ipynb),
        '.html': (None, lambda path: get_file_content(path, 'html')),
    }

    # 画像やPDFファイルの場合はそのまま送信
    if file_extension in ['.svg', '.png', '.jpg', '.jpeg', '.gif', '.pdf']:
        return send_file(full_path)

    # レンダリング方法を取得
    renderer = renderers.get(file_extension)
    if renderer:
        template, render_func = renderer
        content = render_func(full_path)
        # テンプレートがある場合はレンダリング、ない場合は内容をそのまま返す
        return render_template(template, content=content, file_path=file_path) if template else content

    # その他のファイルタイプはテキストとして表示
    content = get_file_content(full_path, 'text')
    return render_template('view_file.html', content=content, file_path=file_path)

@app.route('/search')
def search():
    """
    ファイル検索を行う関数

    Returns:
        str: 検索結果を含むレンダリングされたHTMLテンプレート
    """
    # クエリパラメータから検索語を取得
    query = request.args.get('q', '')
    # ファイル検索を実行
    results = search_files(BASE_DIR, query)
    # 検索結果をフィルタリング
    filtered_results = filter_files(results, BASE_DIR)
    # 検索結果を含むindex.htmlテンプレートをレンダリング
    return render_template('index.html', files=filtered_results, search_query=query)

if __name__ == '__main__':
    # デバッグモードでアプリケーションを実行
    app.run(debug=True, host='0.0.0.0', port=5001)