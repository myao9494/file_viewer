import csv

def render_csv(file_path):
    """
    CSVファイルをHTMLテーブルに変換する関数

    Args:
        file_path (str): 変換するCSVファイルのパス

    Returns:
        str: HTML形式のテーブル文字列
    """
    # CSVファイルを開いて読み込む
    with open(file_path, 'r', encoding='utf-8') as file:
        # CSVリーダーオブジェクトを作成
        csv_reader = csv.reader(file)
        
        # HTMLテーブルの開始タグ
        table_html = '<table class="csv-table">'
        
        # CSVの各行を処理
        for i, row in enumerate(csv_reader):
            if i == 0:
                # 最初の行はヘッダーとして処理
                table_html += '<thead><tr>' + ''.join(f'<th>{cell}</th>' for cell in row) + '</tr></thead><tbody>'
            else:
                # 2行目以降はデータ行として処理
                table_html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
        
        # テーブルの終了タグ
        table_html += '</tbody></table>'
    
    # 完成したHTMLテーブル文字列を返す
    return table_html