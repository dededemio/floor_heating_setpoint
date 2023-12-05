# 床暖房の適切な設定温度を求めるプログラム
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from functools import partial
from matplotlib import pyplot as plt

# 室の熱損失と床暖からの熱取得の差を計算
def calc_heat_diff(outdoor_temp, heating_setpoint, room_temp):
    # 部屋毎に変更するパラメータ
    wall_area_total = 35.1 # 窓含む壁の面積[m2]
    window_area_case = 2.1  # 開き窓の面積[m2]
    window_area_slide = 5.4  # 引き違い窓の面積[m2]
    wall_area = wall_area_total - window_area_case - window_area_slide
    ceiling_area = 0 # 天井の面積[m2]
    floor_heating_area = 21.8  # 床暖房の面積[m2]

    # 建物で固定のパラメータ
    wall_heat_transfer_coeff = 0.24  # 壁の熱貫流率[W/m2K]
    window_heat_transfer_coeff_case = 0.8  # 開き窓の熱貫流率[W/m2K]
    window_heat_transfer_coeff_slide = 1.0  # 引き違い窓の熱貫流率[W/m2K]
    ceiling_heat_transfer_coeff = 0.15  # 天井の熱貫流率[W/m2K]
    floor_heating_transfer_coeff = 2.7 # 床暖房パイプからの熱貫流率[W/m2K]

    # 壁、窓、天井から室外への熱損失
    heat_loss_outside = (wall_area * wall_heat_transfer_coeff + window_area_case * window_heat_transfer_coeff_case + 
                        window_area_slide * window_heat_transfer_coeff_slide + 
                        ceiling_area * ceiling_heat_transfer_coeff) * (room_temp - outdoor_temp)

    # 床暖房からの熱供給。室温のほうが床暖設定より高い場合は0とする
    heat_supply_floor_heating = floor_heating_area * floor_heating_transfer_coeff * np.maximum((heating_setpoint - room_temp),0)
    
    # 室内の総熱量
    heat_diff = abs(heat_supply_floor_heating - heat_loss_outside)

    return heat_diff

# ある外気温、床暖設定のときの室温を計算する
def calc_room_temperature(outdoor_temp, heating_setpoint):
    objective_func = partial(calc_heat_diff, outdoor_temp, heating_setpoint)
    initial_guess = [outdoor_temp] # 室温の初期値
    result = minimize(objective_func, initial_guess, method="Nelder-Mead")
    return result.x[0]

# 目標室温にするための床暖設定温度を求める
def calc_heating_setpoint(room_setpoint, outdoor_temp):
    objective_func = partial(calc_heat_diff, outdoor_temp=outdoor_temp, room_temp=room_setpoint)
    initial_guess = [room_setpoint] # 床暖設定の初期値
    result = minimize(lambda x: objective_func(heating_setpoint=x), initial_guess, method="Nelder-Mead")
    return np.ceil(result.x[0])

# 外気温別の床暖設定をグラフ化
room_setpoint = 23 # 目標室温
outdoor_temp = np.round(np.arange(-5.0, 15.0, 1), 1)
heating_setpoint = [calc_heating_setpoint(room_setpoint, x) for x in outdoor_temp]
heating_setpoint_list = pd.DataFrame(heating_setpoint, index=outdoor_temp, columns=["床暖設定温度[℃]"])
heating_setpoint_list.index.name="外気温[℃]"
print(heating_setpoint_list)

# グラフ描画
plt.plot(heating_setpoint_list)
plt.grid()
plt.xlabel("Outdoor temperature[℃]")
plt.ylabel("Floor heating setpoint[℃]")



# 2022年の気温から、夜間最低温度と昼平均温度を計算して、推奨設定を計算
# 夜間は18:00～9:00とする
hour_start_night = 18
hour_end_night = 9
# 横浜の2022年の気温データ読み込み(https://www.data.jma.go.jp/gmd/risk/obsdl/index.php)
temp_act = pd.read_csv("data.csv", header=2, index_col=0, encoding="shift-jis")
temp_act.index = pd.to_datetime(temp_act.index)
# 10月～4月を対象に計算
month = [10, 11, 12, 1, 2, 3, 4]
setpoint = pd.DataFrame(columns=["通常温度", "セーブ温度"])
temp_min_avg = pd.DataFrame(columns=["夜間最低気温", "昼間平均気温"])
for m in month:
    # 月別の昼・夜間データを抽出
    temp_month = temp_act[temp_act.index.month==m]
    temp_night = temp_month[(temp_month.index.hour >= hour_start_night) | (temp_month.index.hour < hour_end_night)]
    temp_day = temp_month[(temp_month.index.hour < hour_start_night) & (temp_month.index.hour >= hour_end_night)]
    # 夜間最低温度、昼間平均気温を格納
    temp_min_avg.loc[m] = [temp_night.min()[0], round(temp_day.mean()[0],1)]
    # 目標室温を保つ設定温度を計算して格納
    setpoint_night = calc_heating_setpoint(room_setpoint, temp_night.min()[0])
    setpoint_day = calc_heating_setpoint(room_setpoint, temp_day.mean()[0])
    setpoint.loc[m] = [setpoint_night, setpoint_day]

# 計算結果を表示
print(temp_min_avg)
print(setpoint)
