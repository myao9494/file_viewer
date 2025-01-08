import os
from pathlib import Path
import cairosvg
from PyPDF2 import PdfReader, PdfWriter

def convert_svg_to_pdf_with_password(svg_file_path, password):
    # SVGファイルのパスを確認
    svg_path = Path(svg_file_path)
    if not svg_path.exists() or svg_path.suffix.lower() != ".svg":
        print("指定されたファイルが存在しないか、SVGファイルではありません。")
        return

    # 保存先フォルダとファイル名を設定
    output_pdf_name = f"【PW付】{svg_path.stem}.pdf"
    output_pdf_path = svg_path.parent / output_pdf_name

    # SVGをPDFに変換
    try:
        temp_pdf_path = svg_path.parent / f"{svg_path.stem}_temp.pdf"
        cairosvg.svg2pdf(url=str(svg_path), write_to=str(temp_pdf_path))
    except Exception as e:
        print(f"SVGをPDFに変換中にエラーが発生しました: {e}")
        return

    # PDFにパスワードを設定
    try:
        reader = PdfReader(str(temp_pdf_path))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # パスワードを設定
        writer.encrypt(password)

        # パスワード付きPDFを保存
        with open(output_pdf_path, "wb") as output_pdf:
            writer.write(output_pdf)

        print(f"パスワード付きPDFを作成しました: {output_pdf_path}")

    except Exception as e:
        print(f"PDFにパスワードを設定中にエラーが発生しました: {e}")

    finally:
        # 一時ファイルを削除
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()

# 使用例
svg_file = r"C:\path\to\your\file.svg"  # SVGファイルのパスを指定
pdf_password = "your_password"         # 設定したいパスワード
convert_svg_to_pdf_with_password(svg_file, pdf_password)