"""
Obsidian 連携機能のテスト
"""
import pytest
from app import app
import os
from unittest.mock import patch

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_open_obsidian_api(client):
    """
    /open-obsidian エンドポイントにパスを送信した際、正しい Obsidian URI が構築されることをテストする
    """
    # テスト対象のパス
    # Vault名が "obsidian-dagnetz" となり、ファイル名が "01_data/test.md" となるようなパス
    test_path = "/Users/sudoupousei/000_work/obsidian-dagnetz/01_data/test.md"
    
    with patch('subprocess.Popen') as mock_popen:
        response = client.post('/open-obsidian', json={'path': test_path})
        
        assert response.status_code == 200
        assert response.get_json()['success'] is True
        
        # モックされた subprocess.Popen が呼ばれたことを確認
        # 期待される URI: obsidian://open?vault=obsidian-dagnetz&file=01_data/test.md
        mock_popen.assert_called_once()
        args, _ = mock_popen.call_args
        command = args[0]
        
        # macOS の場合は ['open', 'uri']
        # Windows の場合は ['cmd', '/c', 'start', 'uri'] のような形式を想定
        uri = next(arg for arg in command if "obsidian://" in arg)
        assert "vault=obsidian-dagnetz" in uri
        assert "file=01_data/test.md" in uri

def test_open_obsidian_no_obsidian_in_path(client):
    """
    パスに "obsidian" が含まれない場合のエラー処理をテストする
    """
    test_path = "/Users/sudoupousei/000_work/some_random_folder/test.md"
    
    response = client.post('/open-obsidian', json={'path': test_path})
    assert response.status_code == 400
    assert response.get_json()['success'] is False
    assert "obsidian" in response.get_json()['error']
