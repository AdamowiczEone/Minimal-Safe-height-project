# app.py
import streamlit as st
import cv2
import numpy as np
import json
from PIL import Image
from io import BytesIO
from calc import MinimalSafeHeight
from streamlit_drawable_canvas import st_canvas

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

# Инициализация session_state
if 'points' not in st.session_state:
    st.session_state.points = []
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'obstacle_height' not in st.session_state:
    st.session_state.obstacle_height = 0

# Основная область – загрузка карты и вызов анализа
st.header("Загрузка карты высот")
uploaded_file = st.file_uploader("Выберите изображение карты (PNG, JPG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # Загружаем изображение в numpy array для OpenCV
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]
    
    # Создаём PIL Image для canvas
    pil_img = Image.open(BytesIO(uploaded_file.getvalue()))
    
    st.write(f"**Размер изображения: {w}x{h} пикселей**")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Выберите точки на карте")
        st.info("""
        **Инструкция:**
        1. Кликните **первой точкой** на порог ВПП (красный маркер появится автоматически)
        2. Кликните **второй точкой** на конец оси ВПП (синий маркер)
        3. Нажмите '🚀 Рассчитать высоту'
        
        *Для исправления: нажмите 'Сбросить точки' и выберите заново*
        """)
        
        # Canvas для интерактивного выбора точек
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.5)",
            stroke_width=3,
            stroke_color="#00FF00",
            background_image=pil_img,
            height=h,
            width=w,
            drawing_mode="point",
            key="canvas",
            display_toolbar=True
        )
    
    with col2:
        st.subheader("Управление")
        
        # Обработка точек с canvas
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data.get("objects", [])
            points = []
            for obj in objects:
                if obj.get("type") == "circle":
                    x = int(obj.get("left", 0))
                    y = int(obj.get("top", 0))
                    points.append((x, y))
            
            st.session_state.points = points
        
        if len(st.session_state.points) >= 1:
            st.success(f"✅ Точка 1 (порог ВПП): {st.session_state.points[0]}")
        if len(st.session_state.points) >= 2:
            st.success(f"✅ Точка 2 (конец оси): {st.session_state.points[1]}")
        
        if st.button("🚀 Рассчитать высоту"):
            if len(st.session_state.points) >= 2:
                first_point = st.session_state.points[0]
                second_point = st.session_state.points[1]
                
                # Расчёт максимальной высоты вдоль линии
                dx = second_point[0] - first_point[0]
                dy = second_point[1] - first_point[1]
                length = int(np.hypot(dx, dy))
                max_val = 0.0
                
                for t in np.linspace(0, 1, max(1, length)):
                    xi = int(first_point[0] + t * dx)
                    yi = int(first_point[1] + t * dy)
                    if 0 <= xi < w and 0 <= yi < h:
                        brightness = img_gray[yi, xi]
                        height = (brightness / 255.0) * MAX_HEIGHT_PHYS
                        if height > max_val:
                            max_val = height
                
                st.session_state.obstacle_height = max_val
                st.session_state.analysis_done = True
                st.session_state.first_point = first_point
                st.session_state.second_point = second_point
                st.session_state.max_height = max_val
                
                st.success(f"Максимальная высота препятствия: **{max_val:.2f} м**")
            else:
                st.error("❌ Выберите обе точки на карте!")
        
        if st.button("🔄 Сбросить точки"):
            st.session_state.points = []
            st.session_state.analysis_done = False
            st.rerun()
    
    # Визуализация выбранной оси
    if st.session_state.get('analysis_done') and len(st.session_state.points) >= 2:
        st.subheader("📍 Выбранная ось ВПП")
        vis_img = img_rgb.copy()
        p1 = st.session_state.first_point
        p2 = st.session_state.second_point
        
        # Рисуем линию
        cv2.line(vis_img, p1, p2, (0, 255, 0), 3)
        cv2.circle(vis_img, p1, 10, (255, 0, 0), -1)  # Красная (BGR)
        cv2.circle(vis_img, p2, 10, (0, 0, 255), -1)  # Синяя (BGR)
        
        st.image(vis_img, caption="Ось ВПП (красная = порог, синяя = конец, зелёная = ось)", use_container_width=True)
        st.write(f"**Длина оси:** {int(np.hypot(p2[0]-p1[0], p2[1]-p1[1]))} пикселей")

# Если есть данные анализа, выполняем расчёт
if st.session_state.get('analysis_done') and st.session_state.get('obstacle_height', 0) > 0:
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
    if uploaded_file is not None:
        st.info("👆 Выберите точки на карте и нажмите 'Рассчитать высоту'")

# Инструкция внизу
st.markdown("---")
st.markdown("""
**Инструкция:**
1. Задайте параметры аэродрома и карты в боковой панели.
2. Загрузите изображение карты высот (градиент от чёрного (0) до белого (макс. высота)).
3. Кликните по карте: первая точка – порог ВПП, вторая точка – конец оси ВПП.
4. Нажмите "🚀 Рассчитать высоту".
5. Получите результат расчёта минимальной безопасной высоты.
""")