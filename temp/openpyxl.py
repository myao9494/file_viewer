from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font

# xlsmファイルのパス
xlsm_path = "your_file.xlsm"

# xlsmファイルを読み込む (マクロ保持)
wb = load_workbook(xlsm_path, keep_vba=True)

# アクティブなシートを取得
sheet = wb.active

# リンクを追加
sheet["A1"].hyperlink = "https://www.example.com"
sheet["A1"].value = "Example Link"

# コメントを追加
comment = Comment("This is a comment.", "Author Name", font=Font(size=8))
sheet["B2"].comment = comment

# xlsmファイルとして保存
output_path = "output_file.xlsm"
wb.save(output_path)

print(f"'{output_path}' に保存しました。")