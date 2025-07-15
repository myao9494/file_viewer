from flask import Flask, request, jsonify

app = Flask(__name__)

# CORS設定を手動で実装
@app.after_request
def after_request(response):
    # すべてのオリジンからのアクセスを許可
    response.headers.add('Access-Control-Allow-Origin', '*')
    
    # 許可するHTTPメソッドを指定
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    
    # 許可するヘッダーを指定
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    # プリフライトリクエストの結果をキャッシュする時間（秒）
    response.headers.add('Access-Control-Max-Age', '3600')
    
    return response

# OPTIONSリクエストを処理（プリフライトリクエスト用）
@app.before_request
def before_request():
    if request.method == 'OPTIONS':
        response = jsonify({'message': 'OK'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        return response

# 既存のルートをここに追加
@app.route('/')
def index():
    return jsonify({'message': 'Hello World'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)