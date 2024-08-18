import nbformat
import nbconvert

def render_ipynb(file_path):
    """
    Jupyter Notebookファイル(.ipynb)をHTMLに変換する関数

    Args:
        file_path (str): 変換するipynbファイルのパス

    Returns:
        str: 変換されたHTML形式の文字列
    """
    # ipynbファイルを開いて読み込む
    with open(file_path, 'r', encoding='utf-8') as file:
        # nbformatを使用してノートブックを読み込む（バージョン4形式で）
        notebook = nbformat.read(file, as_version=4)
    
    # HTMLエクスポーターを作成
    html_exporter = nbconvert.HTMLExporter()
    # 基本的なテンプレートを使用
    html_exporter.template_name = 'basic'
    
    # ノートブックをHTMLに変換
    # bodyにはHTML内容が、_には追加のリソース情報が含まれる（今回は使用しない）
    (body, _) = html_exporter.from_notebook_node(notebook)
    
    # 変換されたHTML文字列を返す
    return body