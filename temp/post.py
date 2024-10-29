import plotly.graph_objects as go
# import numpy as np
# from scipy.spatial import ConvexHull, Delaunay
# from scipy.interpolate import griddata

def create_3d_scatter_plot(df, html_filename, title="Temperature", max_val="", min_val="", unit="[℃]", degree_opp=True):
    """
    3D散布図を作成し、HTMLファイルとしてエクスポートします。
    
    Args:
        df (pandas.DataFrame): 'node_id'と3D座標('X','Y','Z')と時間ごとの温度データを持つデータフレーム
        html_filename (str): 出力するHTMLファイルの名前
    
    Returns:
        None: HTMLファイルを指定された名前で出力します。
    """
    
    if degree_opp:
        plus = -273.15
    else:
        plus = 0
        
    # 時間点を列名から取得
    time_points = [col for col in df.columns if col not in ['X', 'Y', 'Z', 'node_id']]
    
    # スライダーの定義（時間用）
    steps = []
    for t, t_time in enumerate(time_points):
        step = dict(
            args=[{"visible": [False] * len(time_points)},  # 初期状態では全トレースを非表示
                  {"title": ""}],
            label=f"{t_time}"
        )
        step["args"][0]["visible"][t] = True  # 該当する時間のトレースのみ表示
        steps.append(step)
    
    time_slider = dict(
        active=0,
        steps=steps,
        currentvalue={"prefix": "Time: "},
        pad={"t": 50}
    )

    # ポイントサイズ用のスライダー
    size_steps = []
    for size in range(1, 11):
        size_step = dict(
            args=[{"marker.size": size}],
            label=str(size),
            method="restyle"
        )
        size_steps.append(size_step)

    size_slider = dict(
        active=2,
        steps=size_steps,
        currentvalue={"prefix": "Point size: "},
        pad={"r": 20},
        yanchor="top",
        y=1,  # 上部に配置
        x=0.95,  # 右端に配置
        xanchor="right",  # 右端を基準に配置
        len=0.2  # スライダーの長さを短めに設定
    )

    # 最大・最小値の計算
    max_val_title = df.drop(['X', 'Y', 'Z', 'node_id'], axis=1).values.max()+plus
    if max_val == "":
        max_val = max_val_title
    min_val = df.drop(['X', 'Y', 'Z', 'node_id'], axis=1).values.min()+plus
    
    # 図の作成
    fig = go.Figure()
    
    for t, t_time in enumerate(time_points):
        df_temp = df[t_time]+plus
        fig.add_trace(
            go.Scatter3d(
                x=df['X'], y=df['Y'], z=df['Z'],
                mode='markers',
                marker=dict(
                    size=3,
                    color=df_temp,
                    colorscale='jet',
                    cmin=min_val,
                    cmax=max_val,
                    opacity=0.8,
                    colorbar=dict(title=title + f" {unit}")
                ),
                text=[
                    f"Node ID: {node_id}<br>" +
                    f"X: {x:.3f}<br>" +
                    f"Y: {y:.3f}<br>" +
                    f"Z: {z:.3f}<br>" +
                    f"{title}: {temp:.3f}{unit}"
                    for node_id, x, y, z, temp in zip(df['node_id'], df['X'], df['Y'], df['Z'], df_temp)
                ],
                hovertemplate="%{text}<extra></extra>",
                visible=False,
                showlegend=False
            )
        )
        
    # 0番目のトレースを表示
    fig.data[0].visible = True
    fig.update_layout(
        title=f"3D Plot of {title} (Max: {max_val_title:.2f}[unit])",  # 最大温度でタイトルを設定
        sliders=[time_slider, size_slider],  # 両方のスライダーを追加
        showlegend=False,  # レイアウトの凡例を表示しない
        height=800,  # スライダー用に高さを調整
        margin=dict(r=80, t=100)  # 右側と上部のマージンを確保
    )
    # HTMLファイルとして保存
    fig.write_html(html_filename)