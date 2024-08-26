# ファイルビューアーアプリケーション

## 概要
このプロジェクトは、FlaskベースのウェブアプリケーションでMarkdown、Jupyter Notebook、CSV、およびその他のファイルタイプを表示・処理する機能を提供します。ローカルディレクトリ内のファイルを簡単に閲覧し、検索することができます。

## 必要条件
- Python 3.9以上
- Conda (推奨) または pip

## セットアップ

### Condaを使用する場合（推奨）:

1. 環境を作成し、アクティベートする:
   ```
   conda create -n fileviewer python=3.9
   conda activate fileviewer
   ```

2. 必要なパッケージをインストールする:
   ```
   conda install flask markdown pygments nbconvert nbformat
   pip install python-markdown-math
   ```

### pipを使用する場合:

1. 仮想環境を作成し、アクティベートする:
   ```
   python -m venv fileviewer
   source fileviewer/bin/activate  # Linuxの場合
   fileviewer\Scripts\activate  # Windowsの場合
   ```

2. 必要なパッケージをインストールする:
   ```
   pip install -r requirements.txt
   ```

### JavaScriptライブラリのローカル配置:

1. 以下のディレクトリ構造を作成します:
```
static/
├── js/
│   ├── d3.min.js
│   ├── markmap-view.min.js
│   └── markmap-lib.min.js
└── css/
      └── font-awesome.min.css
```

2. 各ライブラリをダウンロードし、適切な場所に配置します:
   - D3.js: https://d3js.org/d3.v7.min.js をダウンロードし、`static/js/d3.min.js` として保存
   - Markmap View: https://unpkg.com/markmap-view@0.15.4/dist/index.min.js をダウンロードし、`static/js/markmap-view.min.js` として保存
   - Markmap Lib: https://unpkg.com/markmap-lib@0.15.4/dist/index.min.js をダウンロードし、`static/js/markmap-lib.min.js` として保存
   - Font Awesome: https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css をダウンロードし、`static/css/font-awesome.min.css` として保存

3. HTMLテンプレート内のスクリプトとCSSの参照を更新します:
   - `templates/base.html`:
     ```html
     <link rel="stylesheet" href="{{ url_for('static', filename='css/font-awesome.min.css') }}">
     ```
   - `templates/mindmap_view.html`:
     ```html
     <script src="{{ url_for('static', filename='js/d3.min.js') }}"></script>
     <script src="{{ url_for('static', filename='js/markmap-view.min.js') }}"></script>
     <script src="{{ url_for('static', filename='js/markmap-lib.min.js') }}"></script>
     ```

## 使用方法
1. アプリケーションを起動する:
   ```
   python app.py
   ```
2. ブラウザで `http://localhost:5001` にアクセスする
3. ファイルリストから閲覧したいファイルを選択する
4. 検索バーを使用してファイルを検索する

## 機能
- Flaskウェブアプリケーションフレームワーク
- Markdownファイルの表示（数式のサポート含む）
- Jupyter Notebookの表示
- CSVファイルの表示
- テキストファイルとHTMLファイルの表示
- ファイル検索機能
- .view_ignoreファイルを使用した表示除外設定
- マインドマップ表示機能（オフラインサポート）

## カスタマイズ
- `BASE_DIR`変数（app.py内）を変更して、表示するディレクトリを設定できます
- `.view_ignore`ファイルを編集して、表示から除外するファイルやディレクトリを指定できます

## 貢献
プロジェクトへの貢献は歓迎します。プルリクエストを送る前に、既存の問題をチェックするか、新しい問題を作成してください。

## ライセンス
このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 連絡先
質問や提案がある場合は、Issueを作成するか、[メールアドレス]にお問い合わせください。