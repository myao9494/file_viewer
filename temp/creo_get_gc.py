from creoson import creoson_post, creoson_get
import csv

# アセンブリのパスを設定
assembly_path = "path/to/your/assembly.asm" # アセンブリのパスを実際のパスに置き換えてください

# CSVファイルのパスを設定
csv_file_path = "output.csv"

# 出力する座標系を設定 (アセンブリの座標系の名前を指定)
coordinate_system_name = "ASSY_COORD_SYS"  # アセンブリの座標系の名前を実際の名前で置き換えてください

def get_component_centroid(component_path, coordinate_system_name):
  """指定された座標系での部品の重心を取得します"""
  try:
      mass_prop = creoson_post("feature", "get_massprop", {"file": component_path, "coord_sys": coordinate_system_name})
      centroid_data = mass_prop.get("centroid")

      if centroid_data and isinstance(centroid_data,dict):
         return centroid_data
      else:
         print(f"Warning: Unable to retrieve centroid data for {component_path}")
         return None

  except Exception as e:
        print(f"Error getting centroid for {component_path}: {e}")
        return None


def get_assembly_components(assembly_path):
    """アセンブリの全コンポーネントの情報を取得します。"""
    components = creoson_get("file","list_components",{"file":assembly_path})
    if components and isinstance(components.get('componentList'),list):
        return [item.get('path') for item in components.get('componentList')]
    else:
        return None


def main():
    # アセンブリのコンポーネント一覧を取得
    components = get_assembly_components(assembly_path)
    if not components:
       print("Error: No components found in assembly or an error occurred.")
       return
    
    with open(csv_file_path, mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["部品名", "X座標", "Y座標", "Z座標"])

        for component_path in components:
          centroid = get_component_centroid(component_path,coordinate_system_name)
          if centroid:
              csv_writer.writerow([component_path,centroid.get('x'),centroid.get('y'),centroid.get('z')])

    print("重心データをCSVファイルに出力しました:", csv_file_path)

if __name__ == "__main__":
    main()



# ----------chat gpt ----------------

import requests
import csv

# Creosonサーバーの設定
CREOSON_URL = "http://localhost:9056/creoson"
SESSION_ID = None

def creoson_request(command, function, data):
    """Creosonリクエストを送信する"""
    global SESSION_ID
    payload = {
        "command": command,
        "function": function,
        "sessionId": SESSION_ID,
        "data": data,
    }
    response = requests.post(CREOSON_URL, json=payload)
    response_data = response.json()

    # エラー処理
    if response_data.get("status", "") != "ok":
        raise Exception(response_data.get("message", "Unknown error"))

    return response_data.get("data", {})

def start_creoson_session():
    """Creosonセッションを開始"""
    global SESSION_ID
    data = creoson_request("connection", "connect", {"username": "creo"})
    SESSION_ID = data["sessionId"]

def get_assembly_components():
    """アセンブリ内の部品リストを取得"""
    data = creoson_request("assembly", "list_files", {})
    return data.get("filelist", [])

def get_component_mass_properties(file_name):
    """部品の質量特性を取得"""
    data = creoson_request("file", "massprops", {"file": file_name})
    return data.get("cg", [0.0, 0.0, 0.0])

def main():
    try:
        # Creosonセッションを開始
        start_creoson_session()

        # アセンブリ内の部品リストを取得
        components = get_assembly_components()

        # CSVファイルの作成
        csv_file = "centroids.csv"
        with open(csv_file, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["PartName", "X", "Y", "Z"])

            # 各部品の重心を取得してCSVに書き込む
            for component in components:
                file_name = component["name"]
                centroid = get_component_mass_properties(file_name)
                writer.writerow([file_name, *centroid])

        print(f"重心データを {csv_file} に保存しました。")

    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    main()


# ----------claude ----------------

import os
import csv
from creopyson import Client

def export_mass_properties():
    # Creosonサーバーに接続
    c = Client()
    c.connect()
    
    # 現在開いているアセンブリを取得
    c.file_open("assembly.asm")  # アセンブリ名は適宜変更してください
    
    # アセンブリ内の全コンポーネントを取得
    components = c.file_list_components()
    
    # 結果を格納するリスト
    mass_props = []
    
    # 各コンポーネントの重心を取得
    for comp in components:
        # マスプロパティを取得
        props = c.file_massproperties(comp)
        
        # 重心座標を取得
        cg = props["mass_center"]
        
        # 結果を追加
        mass_props.append({
            "component": comp,
            "cg_x": cg[0],
            "cg_y": cg[1],
            "cg_z": cg[2],
            "mass": props["mass"]
        })
    
    # CSVファイルに出力
    output_file = "mass_properties.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["component", "cg_x", "cg_y", "cg_z", "mass"])
        writer.writeheader()
        writer.writerows(mass_props)
    
    print(f"Mass properties exported to {output_file}")
    
    # 接続を閉じる
    c.disconnect()

if __name__ == "__main__":
    export_mass_properties()

# ----------chat gpt o1 pre----------------

import requests
import csv
import json

# creosonサーバーのURL
CREOSON_URL = 'http://localhost:9056/creoson'

# セッション開始
def start_session():
    payload = {
        "command": "session",
        "function": "start",
        "data": {}
    }
    response = requests.post(CREOSON_URL, json=payload)
    return response.json()

# セッション終了
def end_session():
    payload = {
        "command": "session",
        "function": "end",
        "data": {}
    }
    response = requests.post(CREOSON_URL, json=payload)
    return response.json()

# アセンブリのコンポーネントリストを取得
def get_components(asm_name):
    payload = {
        "command": "assembly",
        "function": "get_paths",
        "data": {
            "assembly": asm_name,
            "independent": False
        }
    }
    response = requests.post(CREOSON_URL, json=payload)
    return response.json()

# 各部品の重心を取得
def get_massprops(model_name):
    payload = {
        "command": "file",
        "function": "massprops",
        "data": {
            "file": model_name,
            "dirname": "",
            "csys": "",  # アセンブリの座標系を使用
            "scale": 1.0,
            "accuracy": 0.001,
            "eval_masses": True
        }
    }
    response = requests.post(CREOSON_URL, json=payload)
    return response.json()

def main():
    # アセンブリ名を指定（拡張子なし）
    assembly_name = "YourAssemblyName"

    # セッション開始
    start_session()

    # アセンブリを開く
    open_asm_payload = {
        "command": "file",
        "function": "open",
        "data": {
            "filename": assembly_name,
            "dirname": "",
            "generic": "",
            "display": True
        }
    }
    requests.post(CREOSON_URL, json=open_asm_payload)

    # コンポーネントリストを取得
    components_response = get_components(assembly_name)
    components = components_response.get('data', {}).get('paths', [])

    # CSVファイルの準備
    with open('cog_data.csv', 'w', newline='') as csvfile:
        fieldnames = ['Component Name', 'X', 'Y', 'Z']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        # 各コンポーネントの重心を取得
        for comp in components:
            model_name = comp['model']
            massprops_response = get_massprops(model_name)
            if 'data' in massprops_response and 'cog' in massprops_response['data']:
                cog = massprops_response['data']['cog']
                writer.writerow({
                    'Component Name': model_name,
                    'X': cog['x'],
                    'Y': cog['y'],
                    'Z': cog['z']
                })
                print(f"{model_name}: COG = ({cog['x']}, {cog['y']}, {cog['z']})")
            else:
                print(f"{model_name}: 重心情報を取得できませんでした。")

    # セッション終了
    end_session()
    print("重心データをcog_data.csvに出力しました。")

if __name__ == "__main__":
    main()