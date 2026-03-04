# app.py
import streamlit as st
import cv2
import numpy as np
from calc import MinimalSafeHeight

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
    # Загружаем изображение в numpy array
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]
    
    st.image(img, caption="Загруженная карта", use_container_width=True)
    
    # Инструкция по выбору точек
    st.info(f"""
    **Размер изображения: {w}x{h} пикселей**
    
    Кликните по карте, чтобы выбрать:
    1. **Первую точку** – порог ВПП
    2. **Вторую точку** – конец оси ВПП
    """)
    
    # Интерактивный выбор точек через streamlit-drawable-canvas или координатами
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Координаты точек")
        x1 = st.number_input("X1 (порог ВПП)", min_value=0, max_value=w-1, value=w//4)
        y1 = st.number_input("Y1 (порог ВПП)", min_value=0, max_value=h-1, value=h//2)
        x2 = st.number_input("X2 (конец оси)", min_value=0, max_value=w-1, value=3*w//4)
        y2 = st.number_input("Y2 (конец оси)", min_value=0, max_value=h-1, value=h//2)
    
    with col2:
        if st.button("🚀 Рассчитать высоту"):
            first_point = (x1, y1)
            second_point = (x2, y2)
            
            # Расчёт максимальной высоты вдоль линии
            dx = x2 - x1
            dy = y2 - y1
            length = int(np.hypot(dx, dy))
            max_val = 0.0
            
            for t in np.linspace(0, 1, max(1, length)):
                xi = int(x1 + t * dx)
                yi = int(y1 + t * dy)
                if 0 <= xi < w and 0 <= yi < h:
                    brightness = img_gray[yi, xi]
                    height = (brightness / 255.0) * MAX_HEIGHT_PHYS
                    if height > max_val:
                        max_val = height
            
            st.session_state['obstacle_height'] = max_val
            st.session_state['analysis_done'] = True
            st.session_state['first_point'] = first_point
            st.session_state['second_point'] = second_point
            
            st.success(f"Максимальная высота препятствия: **{max_val:.2f} м**")
    
    # Визуализация линии
    if st.session_state.get('analysis_done'):
        vis_img = img.copy()
        cv2.line(vis_img, st.session_state['first_point'], st.session_state['second_point'], (0, 255, 0), 2)
        cv2.circle(vis_img, st.session_state['first_point'], 8, (0, 0, 255), -1)
        cv2.circle(vis_img, st.session_state['second_point'], 8, (255, 0, 0), -1)
        st.image(vis_img, caption="Выбранная ось ВПП", use_container_width=True)

# Если есть данные анализа, выполняем расчёт
if st.session_state.get('analysis_done'):
    st.header("📊 Результат расчёта")

    H_obstcl = st.session_state['obstacle_height']

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

    rounded_m = calc.round_to_100ft(result_m)

    st.metric(label, f"{result_m:.1f} м", delta=None)
    st.caption(f"Округлено до 100 футов: {rounded_m:.1f} м ({(rounded_m/0.3048):.0f} футов)")

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
    st.info("Загрузите карту и выберите точки для расчёта.")

# Инструкция внизу
st.markdown("---")
st.markdown("""
**Инструкция:**
1. Задайте параметры аэродрома и карты в боковой панели.
2. Загрузите изображение карты высот (градиент от чёрного (0) до белого (макс. высота)).
3. Введите координаты точек ВПП (или используйте значения по умолчанию).
4. Нажмите "Рассчитать высоту".
5. Получите результат расчёта минимальной безопасной высоты.
""")