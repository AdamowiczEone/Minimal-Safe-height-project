# app.py
import streamlit as st
import subprocess
import json
import tempfile
import os
import numpy as np
from calc import MinimalSafeHeight, MapInfo, MapCalc

# Настройка страницы
st.set_page_config(page_title="Расчёт безопасных высот", layout="wide")
st.title("🛩️ Расчёт минимальных безопасных высот (QFE / QNH)")

# Боковая панель для ввода параметров
with st.sidebar:
    st.header("Параметры расчёта")
    formula_type = st.radio("Тип высоты", ["QFE (относительная)", "QNH (абсолютная)"])
    
    st.subheader("Характеристики аэродрома")
    H_air = st.number_input("Абсолютная высота аэродрома (м)", value=100.0, step=10.0)
    t_air = st.number_input("Температура воздуха на аэродроме (°C)", value=15.0, step=1.0)
    
    st.subheader("Параметры безопасности")
    mav_choice = st.selectbox("Минимальный запас высоты (МЗВ)", ["330 футов (≈100 м)", "660 футов (≈200 м)"])
    MAH = 1 if "330" in mav_choice else 2
    
    st.subheader("Данные карты")
    MAX_HEIGHT_PHYS = st.number_input("Максимальная высота на местности (м)", value=1000.0, step=100.0)
    ANGLE = st.number_input("Угол оси ВПП (градусы)", value=90.0, step=1.0)

# Основная область – загрузка карты и вызов анализа
st.header("Загрузка карты высот")
uploaded_file = st.file_uploader("Выберите изображение карты (PNG, JPG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # Отображаем загруженное изображение
    col1, col2 = st.columns(2)
    with col1:
        st.image(uploaded_file, caption="Загруженная карта", use_container_width=True)
    
    # Кнопка запуска анализа
    if st.button("🚀 Открыть карту в интерактивном окне"):
        # Сохраняем загруженный файл во временную папку
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_img:
            tmp_img.write(uploaded_file.getvalue())
            img_path = tmp_img.name
        
        # Временный файл для результатов
        result_fd, result_path = tempfile.mkstemp(suffix=".json")
        os.close(result_fd)
        
        # Формируем команду для запуска cv2_selector.py
        cmd = [
            "python3", "cv2_selector.py",
            img_path,
            str(ANGLE),
            str(MAX_HEIGHT_PHYS),
            result_path
        ]
        
        st.info("Запускается интерактивное окно OpenCV. Выберите базовую и конечную точки оси, затем нажмите 's' для сохранения.")
        
        try:
            # Запускаем процесс и ждём завершения
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                st.error(f"Ошибка при выполнении скрипта: {result.stderr}")
            else:
                st.success("Анализ завершён!")
                
                # Читаем результаты из JSON
                if os.path.exists(result_path):
                    with open(result_path, 'r') as f:
                        data = json.load(f)
                    
                    # Отображаем полученные данные
                    with col2:
                        st.subheader("Результаты анализа")
                        st.write(f"**Базовая точка (порог ВПП):** {data['first_point']}")
                        st.write(f"**Конечная точка:** {data['second_point']}")
                        st.write(f"**Максимальная высота препятствия на оси:** {data['max_height']:.2f} м")
                    
                    # Сохраняем в session_state для расчёта
                    st.session_state['obstacle_height'] = data['max_height']
                    st.session_state['analysis_done'] = True
                    
                    # Удаляем временные файлы
                    os.unlink(img_path)
                    os.unlink(result_path)
                else:
                    st.warning("Файл с результатами не найден.")
        except Exception as e:
            st.error(f"Исключение: {e}")

# Если есть данные анализа, выполняем расчёт
if st.session_state.get('analysis_done'):
    st.header("📊 Результат расчёта")
    
    H_obstcl = st.session_state['obstacle_height']   # абсолютная высота препятствия (из карты)
    
    # Создаём экземпляр расчётчика
    calc = MinimalSafeHeight(
        H_air=H_air,
        H_obstcl=H_obstcl,
        t_air=t_air,
        MAH=MAH
    )
    
    if formula_type == "QFE (относительная)":
        result_m = calc.QFE()
        label = "QFE (относительная безопасная высота)"
    else:
        result_m = calc.QNH()
        label = "QNH (абсолютная безопасная высота)"
    
    # Округление до 100 футов (по требованию)
    rounded_m = calc.round_to_100ft(result_m)
    
    st.metric(label, f"{result_m:.1f} м", delta=None)
    st.caption(f"Округлено до 100 футов: {rounded_m:.1f} м ({(rounded_m/0.3048):.0f} футов)")
    
    # Дополнительная информация
    with st.expander("Детали расчёта"):
        st.write(f"**H (препятствие + МЗВ):** {calc.H:.2f} м")
        st.write(f"**t₀ (температура на уровне моря):** {calc.t_0:.2f} °C")
        st.write(f"**ΔH (температурная поправка):** {calc.delta_H:.2f} м")
        st.write(f"**МЗВ:** {calc.MAH_m:.1f} м")
        if formula_type == "QFE (относительная)":
            st.latex(r"H_{\text{QFE}} = (H_{\text{преп}} - H_{\text{аэр}}) + МЗВ + \Delta H_t")
        else:
            st.latex(r"H_{\text{QNH}} = H_{\text{преп}} + МЗВ + \Delta H_t")
else:
    st.info("Загрузите карту и выполните анализ для получения результата.")

# Инструкция внизу
st.markdown("---")
st.markdown("""
**Инструкция:**
1. Задайте параметры аэродрома и карты в боковой панели.
2. Загрузите изображение карты высот (градиент от чёрного (0) до белого (макс. высота)).
3. Нажмите кнопку "Открыть карту в интерактивном окне".
4. В окне OpenCV:
   - Кликните левой кнопкой в точке порога ВПП (базовая точка).
   - Кликните левой кнопкой в конечной точке оси (вдоль направления взлёта/посадки).
   - Нажмите 's' для сохранения и выхода (или 'q' для отмены).
5. Результат анализа появится в приложении, затем будет выполнен расчёт.
""")