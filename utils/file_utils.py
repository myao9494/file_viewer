import os
import fnmatch
import re
import pandas as pd

def load_view_ignore():
    """
    .view_ignoreファイルから無視するパターンを読み込む関数

    Returns:
        list: 無視するパターンのリスト
    """
    # .view_ignoreファイルのパスを取得
    view_ignore_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.view_ignore')
    if os.path.exists(view_ignore_path):
        with open(view_ignore_path, 'r', encoding='utf-8') as f:
            # 空行とコメント行を除外してパターンを読み込む
            patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        # print("読み込まれたパターン:", patterns)  # デバッグ出力
        return compile_patterns(patterns)
    return []

def compile_patterns(patterns):
    compiled_patterns = []
    for pattern in patterns:
        if pattern.endswith('/**'):
            compiled_patterns.append(('dir_all', re.compile(re.escape(pattern[:-3]))))
        elif pattern.endswith('/'):
            compiled_patterns.append(('dir', re.compile(r'(^|/)' + re.escape(pattern[:-1]) + r'(/|$)')))
        else:
            compiled_patterns.append(('file', re.compile(fnmatch.translate(pattern))))
    return compiled_patterns

def should_ignore(path, compiled_patterns):
    """
    指定されたパスが無視すべきかどうかを判断する関数

    Args:
        path (str): チェックするファイルパス
        compiled_patterns (list): コンパイル済みのパターンのリスト

    Returns:
        bool: パスが無視すべき場合はTrue、そうでない場合はFalse
    """
    for pattern_type, pattern in compiled_patterns:
        if pattern_type == 'dir_all':
            if pattern.search(path):
                return True
        elif pattern_type == 'dir':
            if pattern.search(path):
                return True
        elif pattern.match(path):
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
    
    # DataFrameを作成
    df = pd.DataFrame({'file': files})
    
    # 相対パスを計算して新しい列に追加
    df['relative_path'] = df['file'].apply(lambda x: os.path.relpath(x, base_dir))
    
    # 無視するかどうかを判定する新しい列を追加
    df['should_ignore'] = df['relative_path'].apply(lambda x: should_ignore(x, ignored_patterns))
    
    # 無視しないファイルのみを抽出
    filtered_files = df[~df['should_ignore']]['file'].tolist()
    
    print(f"フィルタリング後のファイル数: {len(filtered_files)}")  # デバッグ出力
    return filtered_files