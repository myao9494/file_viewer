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

## カスタマイズ
- `BASE_DIR`変数（app.py内）を変更して、表示するディレクトリを設定できます
- `.view_ignore`ファイルを編集して、表示から除外するファイルやディレクトリを指定できます

## 貢献
プロジェクトへの貢献は歓迎します。プルリクエストを送る前に、既存の問題をチェックするか、新しい問題を作成してください。

## ライセンス
このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 連絡先
質問や提案がある場合は、Issueを作成するか、[メールアドレス]にお問い合わせください。