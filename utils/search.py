from utils.file_utils import should_ignore, load_view_ignore
import os

def search_files(base_dir, query):
    """
    指定されたディレクトリ内でファイルを検索する関数

    Args:
        base_dir (str): 検索を開始するベースディレクトリのパス
        query (str): 検索クエリ（ファイル名または内容に含まれる文字列）

    Returns:
        list: 検索クエリにマッチしたファイルの相対パスのリスト
    """
    # .view_ignoreファイルから無視するパターンを読み込む
    ignored_patterns = load_view_ignore()
    results = []

    # ディレクトリを再帰的に走査
    for root, dirs, files in os.walk(base_dir):
        # 無視すべきディレクトリを除外
        dirs[:] = [d for d in dirs if not should_ignore(os.path.relpath(os.path.join(root, d), base_dir), ignored_patterns)]
        
        for file in files:
            full_path = os.path.join(root, file)
            relative_path = os.path.relpath(full_path, base_dir)
            
            # ファイルが無視リストに含まれていないかチェック
            if not should_ignore(relative_path, ignored_patterns):
                # ファイル名に検索クエリが含まれているかチェック
                if query.lower() in file.lower():
                    results.append(relative_path)
                else:
                    # ファイルの内容を検索
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if query.lower() in content.lower():
                                results.append(relative_path)
                    except Exception as e:
                        print(f"ファイル {full_path} の読み込み中にエラーが発生しました: {e}")
    
    return results