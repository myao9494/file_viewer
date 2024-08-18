import os

def get_file_list(directory):
    """
    指定されたディレクトリ内のすべてのファイルのリストを取得する関数

    Args:
        directory (str): ファイルリストを取得するディレクトリのパス

    Returns:
        list: ディレクトリ内のファイルの相対パスのリスト（ソート済み）
    """
    files = []
    # ディレクトリを再帰的に走査
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            # 隠しファイル（.で始まるファイル）をスキップ
            if filename.startswith('.'):
                continue
            # ファイルの絶対パスを取得
            full_path = os.path.join(root, filename)
            # ベースディレクトリからの相対パスを取得
            relative_path = os.path.relpath(full_path, directory)
            files.append(relative_path)
    # ファイルリストをソートして返す
    return sorted(files)

def get_file_content(file_path, file_type):
    """
    指定されたファイルの内容を取得する関数

    Args:
        file_path (str): 読み込むファイルのパス
        file_type (str): ファイルタイプ（'text'または'html'）

    Returns:
        str: ファイルの内容（HTMLまたはテキスト）
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        if file_type in ['text', 'html']:
            # テキストファイルまたはHTMLファイルの場合はそのまま読み込む
            return file.read()
    # 該当するファイルタイプがない場合は空文字列を返す
    return ''