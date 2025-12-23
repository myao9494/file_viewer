/**
 * ファイルビューア 仕様書
 **/

# 拡張子ハンドリング仕様

本アプリケーションでは、ファイル拡張子に基づいて表示方法を切り替えます。

## Excalidraw 連携
以下の拡張子を持つファイルは、Port 3001 で動作する専用エディタへリダイレクトされます。

- `.excalidraw`
- `.excalidraw.svg`
- `.excalidraw.png`
- `.excalidraw.md` (新規追加)

### リダイレクト先 URL 形式
`http://localhost:3001/?filepath={フルパス}`

## その他の拡張子
- `.md`: Markdown レンダラーで表示
- `.csv`: Tabulator または AG-Grid で表示
- `.pdf`: ブラウザ標準の PDF ビューアで表示
- 画像: 画像プレビューで表示
- `.ipynb`: Jupyter Lab をブラウザで開く
- その他テキスト: テキストエディタで表示
