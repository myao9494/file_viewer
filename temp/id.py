import pandas as pd
import re

# サンプルデータの作成
data = {
    "旧ID": ["xxx___yyy___zzz_____1234", "aaa___bbb_____5678", "ccc_____9101"],
    "新ID": ["ddd___eee___fff_____9101", "ggg___hhh_____1121", "iii_____3141"]
}
df = pd.DataFrame(data)

# 新しい列を追加するための関数
def process_string(s):
    # "_____" で前半と nnnn に分割
    parts = s.rsplit("_____", 1)
    if len(parts) != 2:
        return pd.Series([None, None, None, None])
    
    front_part, nnnn = parts
    # "___" で区切ってリスト化
    split_parts = front_part.split("___")
    # "___" の数は区切った要素数から1を引く
    underscore_count = len(split_parts) - 1
    # "___" と "_____" に挟まれる文字列（最初と最後を除いた部分）
    between_underscores = "___".join(split_parts[1:])

    # "_____nnnn" を抜いた文字列
    without_nnnn = front_part

    return pd.Series([underscore_count, between_underscores, nnnn, without_nnnn])

# 旧IDと新IDの両方に対して処理を適用
for col in ["旧ID", "新ID"]:
    df[[f"{col}_の___数量", f"{col}_の挟まれる文字列", f"{col}_のnnnn", f"{col}_の_____nnnn抜き"]] = df[col].apply(process_string)

# 結果を表示
print(df)