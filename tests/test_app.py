"""
app.py の機能をテストする
"""
import pytest
from app import app
import os

@pytest.fixture
def client():
    # テスト用のベースディレクトリを作成
    test_base_dir = os.path.abspath("./test_work")
    if not os.path.exists(test_base_dir):
        os.makedirs(test_base_dir)
    
    app.config['TESTING'] = True
    # app.py の BASE_DIR を直接上書き（グローバル変数なので注意が必要）
    import app as app_mod
    app_mod.BASE_DIR = test_base_dir
    
    with app.test_client() as client:
        yield client
    
    # 後片付け（必要に応じて）
    # shutil.rmtree(test_base_dir)

def test_excalidraw_md_redirect(client):
    """
    .excalidraw.md ファイルへのリクエストが Port 3001 へリダイレクトされることをテストする
    """
    import app as app_mod
    test_file = "test_drawing.excalidraw.md"
    test_full_path = os.path.join(app_mod.BASE_DIR, test_file)
    
    # テストファイルを作成
    with open(test_full_path, 'w') as f:
        f.write("# Dummy Excalidraw Markdown")

    try:
        # 相対パスでのリクエスト
        response = client.get(f'/view/{test_file}')
        
        # リダイレクト (302) であることを確認
        assert response.status_code == 302
        
        # リダイレクト先 URL が Port 3001 かつ filepath パラメータを含んでいることを確認
        assert "http://localhost:3001/" in response.headers['Location']
        assert f"filepath=" in response.headers['Location']
        assert test_file in response.headers['Location']
        
    finally:
        # テストファイルの削除
        if os.path.exists(test_full_path):
            os.remove(test_full_path)

def test_regular_md_no_redirect(client):
    """
    普通の .md ファイルはリダイレクトされないことを確認する
    """
    import app as app_mod
    test_file = "regular.md"
    test_full_path = os.path.join(app_mod.BASE_DIR, test_file)
    
    with open(test_full_path, 'w') as f:
        f.write("# Regular Markdown")

    try:
        response = client.get(f'/view/{test_file}')
        
        # リダイレクトされず、正常に表示 (200) されることを確認
        assert response.status_code == 200
        assert b"Regular Markdown" in response.data
        
    finally:
        if os.path.exists(test_full_path):
            os.remove(test_full_path)
