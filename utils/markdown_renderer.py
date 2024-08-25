import re
import markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

class TaskListPreprocessor(Preprocessor):
    def run(self, lines):
        new_lines = []
        list_stack = []
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip())
            
            if stripped.startswith('- [ ]') or stripped.startswith('- [x]'):
                while list_stack and indent <= list_stack[-1][0]:
                    new_lines.append('</ul>' * (list_stack[-1][1] + 1))
                    list_stack.pop()
                
                if not list_stack or indent > list_stack[-1][0]:
                    new_lines.append('<ul class="task-list">')
                    list_stack.append((indent, 0))
                
                if stripped.startswith('- [ ]'):
                    new_lines.append(f'<li class="task-list-item"><input type="checkbox" disabled>{{{{ITEM_CONTENT}}}}</li>')
                else:
                    new_lines.append(f'<li class="task-list-item"><input type="checkbox" checked disabled>{{{{ITEM_CONTENT}}}}</li>')
                new_lines[-1] = new_lines[-1].replace('{{ITEM_CONTENT}}', line[indent+5:].strip())
            elif stripped.startswith('-'):
                while list_stack and indent <= list_stack[-1][0]:
                    new_lines.append('</ul>' * (list_stack[-1][1] + 1))
                    list_stack.pop()
                
                if not list_stack or indent > list_stack[-1][0]:
                    new_lines.append('<ul>')
                    list_stack.append((indent, 0))
                
                new_lines.append(f'<li>{{{{ITEM_CONTENT}}}}</li>')
                new_lines[-1] = new_lines[-1].replace('{{ITEM_CONTENT}}', line[indent+1:].strip())
            else:
                while list_stack:
                    new_lines.append('</ul>' * (list_stack[-1][1] + 1))
                    list_stack.pop()
                new_lines.append(line)
        
        while list_stack:
            new_lines.append('</ul>' * (list_stack[-1][1] + 1))
            list_stack.pop()
        
        return new_lines

def render_markdown(file_path):
    # Markdownファイルを読み込む
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # タスクリストとリストの処理を行う
    task_list_preprocessor = TaskListPreprocessor()
    lines = content.split('\n')
    processed_lines = task_list_preprocessor.run(lines)
    processed_content = '\n'.join(processed_lines)
    
    # Markdownパーサーを設定し、拡張機能を追加
    md = markdown.Markdown(extensions=['extra', 'codehilite', 'fenced_code', 'tables'])
    
    # 処理済みの内容をHTMLに変換
    html_content = md.convert(processed_content)
    
    # リスト項目内の強調表示を処理
    html_content = re.sub(r'<li>(.*?)</li>', lambda m: f'<li>{md.convert(m.group(1))}</li>', html_content)
    
    return html_content