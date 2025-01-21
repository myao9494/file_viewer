import sys
import traceback
from typing import Optional

import pandas as pd
import win32com.client as win32
from win32com.client.dynamic import Dispatch


class ExcelCommentManager:
    def __init__(self):
        self.excel: Optional[Dispatch] = None
        self.workbook: Optional[Dispatch] = None
        self.sheet: Optional[Dispatch] = None

    def connect_excel(self, visible: bool = True) -> bool:
        """Connect to the Excel application."""
        try:
            self.excel = win32.gencache.EnsureDispatch('Excel.Application')
            self.excel.Visible = visible
            return True
        except Exception:
            print(f"エラー: Excelアプリケーションの起動に失敗しました。\n詳細: {traceback.format_exc()}")
            return False

    def get_workbook(self, workbook_path: Optional[str] = None) -> bool:
        """Open or get the workbook."""
        try:
            if workbook_path:
                self.workbook = self.excel.Workbooks.Open(workbook_path)
            else:
                if self.excel.Workbooks.Count == 0:
                    # No workbooks are open, create a new one
                    self.workbook = self.excel.Workbooks.Add()
                else:
                    self.workbook = self.excel.ActiveWorkbook
            return True
        except Exception:
            print(f"エラー: ワークブックの取得に失敗しました。\n詳細: {traceback.format_exc()}")
            return False

    def get_sheet(self, sheet_name: Optional[str] = None) -> bool:
        """Get the worksheet."""
        try:
            if sheet_name:
                self.sheet = self.workbook.Sheets(sheet_name)
            else:
                self.sheet = self.workbook.ActiveSheet
            return True
        except Exception:
            print(f"エラー: シート '{sheet_name}' の取得に失敗しました。\n詳細: {traceback.format_exc()}")
            return False

    def add_comments(self, df: pd.DataFrame) -> bool:
        """Add comments from the DataFrame."""
        # Check for required columns
        if not {'cell_address', 'comment_text'}.issubset(df.columns):
            print("エラー: DataFrameに必要なカラム（'cell_address', 'comment_text'）が存在しません。")
            return False

        success = True
        for index, row in df.iterrows():
            try:
                cell = self.sheet.Range(row['cell_address'])

                # Delete existing comment, if any
                if cell.Comment:
                    cell.Comment.Delete()

                # Add new comment
                cell.AddComment()
                cell.Comment.Text(row['comment_text'])

                # Auto-size the comment box
                cell.Comment.Shape.TextFrame.AutoSize = True

            except Exception:
                print(
                    f"エラー: セル {row['cell_address']} へのコメント追加に失敗しました。\n詳細: {traceback.format_exc()}"
                )
                success = False
        return success

    def save_workbook(self, save_path: Optional[str] = None) -> bool:
        """Save the workbook."""
        try:
            if save_path:
                self.workbook.SaveAs(save_path)
            else:
                self.workbook.Save()
            return True
        except Exception:
            print(f"エラー: ファイルの保存に失敗しました。\n詳細: {traceback.format_exc()}")
            return False

    def cleanup(self):
        """Clean up Excel resources."""
        try:
            if self.workbook:
                self.workbook.Close(False)
                del self.workbook
                self.workbook = None
            if self.excel:
                self.excel.Quit()
                del self.excel
                self.excel = None
            # Force garbage collection
            import gc

            gc.collect()
        except Exception:
            print(f"エラー: Excelリソース解放時のエラー。\n詳細: {traceback.format_exc()}")


def main():
    # Sample data
    data = {
        'cell_address': ['A1', 'B2', 'C3'],
        'comment_text': ['これはA1のコメントです', 'これはB2のコメントです', 'これはC3のコメントです'],
    }
    df = pd.DataFrame(data)

    # Initialize ExcelCommentManager
    manager = ExcelCommentManager()

    try:
        # Connect to Excel
        if not manager.connect_excel(visible=True):
            sys.exit(1)

        # Get workbook and sheet
        if not manager.get_workbook():
            sys.exit(1)

        if not manager.get_sheet("Sheet1"):
            sys.exit(1)

        # Add comments
        if manager.add_comments(df):
            print("コメントの追加に成功しました。")
            if not manager.save_workbook():
                print("エラー: ワークブックの保存に失敗しました。")
        else:
            print("一部のコメント追加に失敗しました。")

    finally:
        # Cleanup
        manager.cleanup()


if __name__ == "__main__":
    main()