# 床暖房の適切な設定温度を求めるプログラム
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from functools import partial
from matplotlib import pyplot as plt
plt.rcParams['font.family'] = "Yu Gothic"

HOME_PARAM_EXCEL = pd.ExcelFile("home_parameter.xlsx")
ROOM_PARAM = HOME_PARAM_EXCEL.parse("room_param", index_col=0)
HEAT_TRANSFER_COEF = HOME_PARAM_EXCEL.parse("heat_transfer_coef", index_col=0)
HOME_PARAM_EXCEL.close()
SENSIBLE_HEAT_EX_EFFICIENCY = 0.9

# 室の熱損失と床暖からの熱取得の差を計算
def calc_heat_diff(room, outdoor_temp, heating_setpoint, room_temp):
    # 壁、窓、天井、玄関から室外への熱損失(床は床暖房で温められるため考慮しない)
    heat_loss_envelope = (ROOM_PARAM[room]["窓・ドア除く壁面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["壁"] + 
                         ROOM_PARAM[room]["開き窓面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["開き窓"] + 
                         ROOM_PARAM[room]["引き違い窓面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["引き違い窓"] + 
                         ROOM_PARAM[room]["天井面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["天井"] +
                         ROOM_PARAM[room]["玄関ドア面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["玄関ドア"] +
                         ROOM_PARAM[room]["玄関土間外周長さ[m]"] * HEAT_TRANSFER_COEF["熱貫流率"]["玄関土間"] + 
                         ROOM_PARAM[room]["浴槽面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["浴槽"] * 0.6) * (room_temp - outdoor_temp)

    # 換気による熱損失
    heat_loss_ventilation = 0.33 * (ROOM_PARAM[room]["換気量[㎥/h]"]) * (room_temp - outdoor_temp) * SENSIBLE_HEAT_EX_EFFICIENCY

    # 内部熱負荷
    heat_supply_internal = ROOM_PARAM[room]["内部熱負荷[W]"]

    # 床暖房からの熱取得（室温のほうが床暖設定より高い場合は0）
    heat_supply_floor_heating = ROOM_PARAM[room]["床暖房面積[㎡]"] * HEAT_TRANSFER_COEF["熱貫流率"]["床暖房"] * np.maximum((heating_setpoint - room_temp),0)
    
    # 室の熱損失と熱取得の差の絶対値
    heat_diff = abs(heat_supply_floor_heating - heat_loss_envelope - heat_loss_ventilation + heat_supply_internal)

    return heat_diff

# ある外気温、床暖設定のときの室温を計算する
def calc_room_temperature(room, outdoor_temp, heating_setpoint):
    objective_func = partial(calc_heat_diff, room=room, outdoor_temp=outdoor_temp, heating_setpoint=heating_setpoint)
    initial_guess = [outdoor_temp] # 室温の初期値
    result = minimize(lambda x: objective_func(room_temp=x), initial_guess, method="Nelder-Mead")
    return result.x[0]

# 目標室温にするための床暖設定温度を求める
def calc_heating_setpoint(room, room_setpoint, outdoor_temp):
    objective_func = partial(calc_heat_diff, room=room, outdoor_temp=outdoor_temp, room_temp=room_setpoint)
    initial_guess = [room_setpoint] # 床暖設定の初期値
    result = minimize(lambda x: objective_func(heating_setpoint=x), initial_guess, method="Nelder-Mead")
    return np.ceil(result.x[0])

# 外気温別の床暖設定をグラフ化
outdoor_temp = np.round(np.arange(-5.0, 15.0, 1), 1)
for room in ROOM_PARAM.columns:
    room_setpoint = ROOM_PARAM[room]["目標温度[℃]"]
    heating_setpoint = [calc_heating_setpoint(room, room_setpoint, x) for x in outdoor_temp]
    heating_setpoint_list = pd.DataFrame(heating_setpoint, index=outdoor_temp, columns=["床暖設定温度[℃]"])
    heating_setpoint_list.index.name="外気温[℃]"
    print(heating_setpoint_list)

    # グラフ描画
    plt.plot(heating_setpoint_list)
    plt.grid()
    plt.xlabel("外気温[℃]")
    plt.ylabel("床暖房設定温度目安[℃]")
plt.legend(ROOM_PARAM.columns)

# 2022年の気温から、夜間最低温度と昼平均温度を計算
# 夜間は18:00～9:00とする
hour_start_night = 18
hour_end_night = 9
# 横浜の2022年の気温データ読み込み(https://www.data.jma.go.jp/gmd/risk/obsdl/index.php)
temp_act = pd.read_csv("data.csv", header=2, index_col=0, encoding="shift-jis")
temp_act.index = pd.to_datetime(temp_act.index)
# 10月～4月を対象に計算
month = [10, 11, 12, 1, 2, 3, 4]
temp_min_avg = pd.DataFrame(columns=["夜間最低気温", "昼間平均気温"])
for m in month:
    # 月別の昼・夜間データを抽出
    temp_month = temp_act[temp_act.index.month==m]
    temp_night = temp_month[(temp_month.index.hour >= hour_start_night) | (temp_month.index.hour < hour_end_night)]
    temp_day = temp_month[(temp_month.index.hour < hour_start_night) & (temp_month.index.hour >= hour_end_night)]
    # 夜間最低温度、昼間平均気温を格納
    temp_min_avg.loc[m] = [temp_night.min()[0], round(temp_day.mean()[0],1)]
print(temp_min_avg)

# 各部屋の推奨設定を計算
setpoint_total = []
for m in month:
    setpoint = pd.DataFrame(columns=["通常温度", "セーブ温度"])
    for room in ROOM_PARAM.columns:
        # 目標室温を保つ設定温度を計算して格納
        room_setpoint = ROOM_PARAM[room]["目標温度[℃]"]
        setpoint_night = calc_heating_setpoint(room, room_setpoint, temp_min_avg["夜間最低気温"][m])
        setpoint_day = calc_heating_setpoint(room, room_setpoint, temp_min_avg["昼間平均気温"][m])
        setpoint.loc[room] = [setpoint_night, setpoint_day]
    setpoint_total.append(setpoint)

for m, setpoint in zip(month, setpoint_total):
    print(str(m)+"月", setpoint)

# 実際の計測温度との比較----------------------------------------------------
outdoor_temp = np.round(np.arange(-5.0, 15.0, 0.1), 1)
heating_setpoint_list = np.arange(26, 31)
room_temp_total = []
for heating_setpoint in heating_setpoint_list:
    room_temp = [calc_room_temperature("リビング", x, heating_setpoint) for x in outdoor_temp]
    room_temp_total.append(room_temp)
actual = pd.read_csv("actual.csv", encoding="shift-jis")

for i in range(len(heating_setpoint_list)):
    plt.plot(outdoor_temp, room_temp_total[i])
for heating_setpoint in heating_setpoint_list:
    picup = actual[actual["設定温度"]==heating_setpoint]
    plt.plot(picup["最低気温"], picup["室温"], "*")
plt.grid()
str_list_predict = ["設定"+str(i)+"℃(予想)" for i in heating_setpoint_list]
str_list_actual = ["設定"+str(i)+"℃(実績)" for i in heating_setpoint_list]
plt.title("設定温度別の予想室温と実績")
plt.legend(str_list_predict+str_list_actual)
plt.ylim([19.8, 27.5])
plt.xlabel("外気温[℃]")
plt.ylabel("室温[℃]")