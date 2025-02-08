from flask import Flask, send_from_directory
import os
import mimetypes

app = Flask(__name__)

# MIMEタイプの設定
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/json', '.webmanifest')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('font/woff2', '.woff2')
mimetypes.add_type('application/javascript', '.mjs')

# Excalidrawのビルドディレクトリの絶対パス
EXCALIDRAW_BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'excalidraw_build')

@app.route('/')
def index():
    return send_from_directory(EXCALIDRAW_BUILD_DIR, 'index.html')

@app.route('/<path:path>')
def serve_files(path):
    return send_from_directory(EXCALIDRAW_BUILD_DIR, path)

if __name__ == '__main__':
    port = 5002  # メインアプリケーションと異なるポートを使用
    print(f"Starting Excalidraw server on http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)
