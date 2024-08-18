import os
import fnmatch

def load_view_ignore():
    """
    .view_ignoreファイルから無視するパターンを読み込む関数

    Returns:
        list: 無視するパターンのリスト
    """
    # .view_ignoreファイルのパスを取得
    view_ignore_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.view_ignore')
    if os.path.exists(view_ignore_path):
        with open(view_ignore_path, 'r') as f:
            # 空行とコメント行を除外してパターンを読み込む
            patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print("読み込まれたパターン:", patterns)  # デバッグ出力
        return patterns
    return []

def should_ignore(path, patterns):
    """
    指定されたパスが無視すべきかどうかを判断する関数

    Args:
        path (str): チェックするファイルパス
        patterns (list): 無視するパターンのリスト

    Returns:
        bool: パスが無視すべき場合はTrue、そうでない場合はFalse
    """
    path_parts = path.split(os.sep)
    for pattern in patterns:
        if pattern.endswith('/**'):
            # ディレクトリとその中身すべてを無視するパターン
            base_pattern = pattern[:-3]
            if any(part.startswith(base_pattern) for part in path_parts):
                print(f"無視: {path} (パターン: {pattern})")  # デバッグ出力
                return True
        elif pattern.endswith('/'):
            # ディレクトリを無視するパターン
            if any(part == pattern[:-1] for part in path_parts):
                print(f"無視: {path} (パターン: {pattern})")  # デバッグ出力
                return True
        elif fnmatch.fnmatch(path, pattern) or any(fnmatch.fnmatch(part, pattern) for part in path_parts):
            # ファイル名やディレクトリ名にマッチするパターン
            print(f"無視: {path} (パターン: {pattern})")  # デバッグ出力
            return True
    return False

def filter_files(files, base_dir):
    """
    ファイルリストをフィルタリングする関数

    Args:
        files (list): フィルタリングするファイルのリスト
        base_dir (str): ベースディレクトリのパス

    Returns:
        list: フィルタリング後のファイルリスト
    """
    ignored_patterns = load_view_ignore()
    print("無視するパターン:", ignored_patterns)  # デバッグ出力
    filtered_files = []
    for file in files:
        # ベースディレクトリからの相対パスを取得
        relative_path = os.path.relpath(file, base_dir)
        if not should_ignore(relative_path, ignored_patterns):
            filtered_files.append(file)
        else:
            print(f"フィルタリングされたファイル: {relative_path}")  # デバッグ出力
    print(f"フィルタリング後のファイル数: {len(filtered_files)}")  # デバッグ出力
    return filtered_files