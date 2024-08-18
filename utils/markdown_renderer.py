import re
import markdown
from markdown.extensions import Extension, codehilite, fenced_code
from markdown.preprocessors import Preprocessor

class TaskListPreprocessor(Preprocessor):
    """
    Markdownのタスクリスト記法をHTMLに変換するプリプロセッサー
    """
    def run(self, lines):
        """
        Markdownの各行を処理し、タスクリストをHTMLに変換する

        Args:
            lines (list): Markdownの行のリスト

        Returns:
            list: 変換後の行のリスト
        """
        new_lines = []
        in_list = False
        for line in lines:
            if line.strip().startswith('- [ ]') or line.strip().startswith('- [x]'):
                # タスクリストアイテムの開始
                if not in_list:
                    new_lines.append('<ul class="task-list">')
                    in_list = True
                # 未完了タスクの変換
                line = re.sub(r'^(\s*)-\s*\[ \]', r'\1<li class="task-list-item"><input type="checkbox" disabled>', line)
                # 完了タスクの変換
                line = re.sub(r'^(\s*)-\s*\[x\]', r'\1<li class="task-list-item"><input type="checkbox" checked disabled>', line)
                new_lines.append(line + '</li>')
            else:
                # タスクリスト以外の行の処理
                if in_list:
                    new_lines.append('</ul>')
                    in_list = False
                new_lines.append(line)
        # リストが閉じられていない場合の処理
        if in_list:
            new_lines.append('</ul>')
        return new_lines

class TaskListExtension(Extension):
    """
    タスクリスト機能を追加するMarkdown拡張
    """
    def extendMarkdown(self, md):
        """
        Markdownパーサーにタスクリストプリプロセッサーを登録する

        Args:
            md: Markdownパーサーインスタンス
        """
        md.preprocessors.register(TaskListPreprocessor(md), 'task_list', 50)

def render_markdown(file_path):
    """
    Markdownファイルを読み込み、HTMLに変換する関数

    Args:
        file_path (str): 変換するMarkdownファイルのパス

    Returns:
        str: 変換後のHTML文字列
    """
    # Markdownファイルを読み込む
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Markdownパーサーを設定し、拡張機能を追加
    md = markdown.Markdown(extensions=['extra', 'codehilite', 'fenced_code', TaskListExtension()])
    # MarkdownをHTMLに変換して返す
    return md.convert(content)