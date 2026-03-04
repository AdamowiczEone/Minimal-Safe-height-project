# app.py
import streamlit as st
import cv2
import numpy as np
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
from calc import MinimalSafeHeight

# Настройка страницы
st.set_page_config(page_title="Расчёт безопасных высот", layout="wide")
st.title("🛩️ Расчёт минимальных безопасных высот (QFE / QNH)")

# Боковая панель
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
if 'first_point' not in st.session_state:
    st.session_state.first_point = None
if 'second_point' not in st.session_state:
    st.session_state.second_point = None
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False
if 'obstacle_height' not in st.session_state:
    st.session_state.obstacle_height = 0
if 'max_height_result' not in st.session_state:
    st.session_state.max_height_result = 0
if 'click_key_counter' not in st.session_state:
    st.session_state.click_key_counter = 0
if 'last_coord' not in st.session_state:
    st.session_state.last_coord = None

# =============================================================================
# ЛОГИКА ИЗ cv2_selector.py (та же самая функция!)
# =============================================================================

def calculate_max_height(img_gray, first_point, second_point, max_height_phys):
    """
    Calculate maximum height along the line between two points.
    Логика полностью из cv2_selector.py
    """
    dx = second_point[0] - first_point[0]
    dy = second_point[1] - first_point[1]
    length = int(np.hypot(dx, dy))
    max_val = 0.0

    for t in np.linspace(0, 1, max(1, length)):
        xi = int(first_point[0] + t * dx)
        yi = int(first_point[1] + t * dy)
        if 0 <= xi < img_gray.shape[1] and 0 <= yi < img_gray.shape[0]:
            brightness = img_gray[yi, xi]
            height = (brightness / 255.0) * max_height_phys
            if height > max_val:
                max_val = height

    return max_val

def reset_points():
    st.session_state.first_point = None
    st.session_state.second_point = None
    st.session_state.analysis_done = False
    st.session_state.obstacle_height = 0
    st.session_state.max_height_result = 0
    st.session_state.click_key_counter = 0
    st.session_state.last_coord = None

# =============================================================================
# ОСНОВНАЯ ЧАСТЬ
# =============================================================================

st.header("Загрузка карты высот")
uploaded_file = st.file_uploader("Выберите изображение карты (PNG, JPG)", type=["png", "jpg", "jpeg"])

if uploaded_file is not None:
    # Загружаем изображение (как в cv2_selector)
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img.shape[:2]

    st.write(f"**Размер изображения: {w}x{h} пикселей**")

    # Инструкция (как в cv2_selector)
    if st.session_state.first_point is None:
        st.info("""
        **👆 Инструкция (как в cv2_selector):**
        1. **Кликните по изображению** для выбора первой точки (порог ВПП)
        2. **Кликните ещё раз** для выбора второй точки (конец оси)
        3. Расчёт выполнится автоматически
        
        *Красная сетка помогает ориентироваться*
        """)
    elif st.session_state.second_point is None:
        st.info(f"""
        ✅ **Точка 1 выбрана:** {st.session_state.first_point}
        
        **👆 Кликните по изображению** для выбора второй точки (конец оси)
        """)
    else:
        st.info("✅ **Обе точки выбраны!** Расчёт выполнен.")

    # =============================================================================
    # РИСУЕМ СЕТКУ (как в cv2_selector.py для web mode)
    # =============================================================================
    
    grid_img = img.copy()
    step = max(50, min(100, w // 10))  # Адаптивный шаг как в cv2_selector

    # Рисуем сетку (точно как в cv2_selector.py)
    for x in range(0, w, step):
        cv2.line(grid_img, (x, 0), (x, h), (255, 0, 0), 1)
    for y in range(0, h, step):
        cv2.line(grid_img, (0, y), (w, y), (255, 0, 0), 1)

    # Рисуем выбранную первую точку (как в cv2_selector)
    if st.session_state.first_point:
        x, y = st.session_state.first_point
        cv2.circle(grid_img, (x, y), 8, (0, 0, 255), -1)  # Красная (BGR)
        cv2.putText(grid_img, "Base", (x+5, y-5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    # Рисуем вторую точку и линию (как в cv2_selector)
    if st.session_state.second_point:
        x, y = st.session_state.second_point
        cv2.circle(grid_img, (x, y), 8, (255, 0, 0), -1)  # Синяя (BGR)
        cv2.putText(grid_img, "End", (x+5, y-5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # Рисуем линию между точками
        cv2.line(grid_img, st.session_state.first_point, st.session_state.second_point, (0, 255, 0), 1)

    # =============================================================================
    # ИНТЕРАКТИВНОЕ ИЗОБРАЖЕНИЕ С КЛИКАМИ (веб-аналог cv2.setMouseCallback)
    # =============================================================================

    st.subheader("Карта с сеткой")

    # Уникальный ключ для каждого "состояния" кликов — предотвращает ложные срабатывания
    click_key = f"click_selector_{st.session_state.click_key_counter}"

    # streamlit_image_coordinates — веб-аналог setMouseCallback
    coord = streamlit_image_coordinates(
        Image.fromarray(cv2.cvtColor(grid_img, cv2.COLOR_BGR2RGB)),
        key=click_key
    )

    # Обработка клика (аналог mouse_callback в cv2_selector)
    # Проверяем что координаты изменились — защита от ложных срабатываний
    if coord and coord != st.session_state.last_coord:
        x = coord['x']
        y = coord['y']
        clicked_point = (x, y)

        # Сохраняем последние координаты чтобы не обрабатывать дважды
        st.session_state.last_coord = coord

        if st.session_state.first_point is None:
            # Первый клик — базовая точка (как в cv2_selector)
            st.session_state.first_point = clicked_point
            st.session_state.click_key_counter += 1  # Меняем ключ для следующего клика
            st.success(f"✅ Базовая точка (порог ВПП): {clicked_point}")
            st.rerun()
        elif st.session_state.second_point is None:
            # Второй клик — конечная точка (как в cv2_selector)
            st.session_state.second_point = clicked_point
            st.session_state.click_key_counter += 1  # Меняем ключ
            st.success(f"✅ Конечная точка: {clicked_point}")

            # РАСЧЁТ (логика из cv2_selector.py)
            max_height = calculate_max_height(
                img_gray,
                st.session_state.first_point,
                st.session_state.second_point,
                MAX_HEIGHT_PHYS
            )
            st.session_state.max_height_result = max_height
            st.session_state.obstacle_height = max_height
            st.session_state.analysis_done = True

            st.success(f"**Максимальная высота на линии: {max_height:.2f} м**")
            st.rerun()
        else:
            # Уже есть обе точки — сбрасываем и начинаем заново
            st.info("🔄 Точки уже выбраны. Сбрасываю для нового выбора...")
            reset_points()
            st.session_state.first_point = clicked_point
            st.session_state.click_key_counter += 1
            st.rerun()

    # =============================================================================
    # ПАНЕЛЬ УПРАВЛЕНИЯ
    # =============================================================================
    
    st.subheader("Управление")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.write(f"**Точка 1 (порог):** {st.session_state.first_point}")
    with col2:
        st.write(f"**Точка 2 (конец):** {st.session_state.second_point}")
    with col3:
        if st.button("🔄 Сбросить точки"):
            reset_points()
            st.rerun()

    # =============================================================================
    # ВИЗУАЛИЗАЦИЯ (как в cv2_selector после выбора)
    # =============================================================================
    
    if st.session_state.first_point and st.session_state.second_point:
        st.subheader("📍 Выбранная ось ВПП")
        
        vis_img = img.copy()
        
        # Рисуем линию (как в cv2_selector)
        cv2.line(vis_img, st.session_state.first_point, st.session_state.second_point, (0, 255, 0), 2)
        cv2.circle(vis_img, st.session_state.first_point, 8, (0, 0, 255), -1)
        cv2.circle(vis_img, st.session_state.second_point, 8, (255, 0, 0), -1)
        
        # Длина оси
        dx = st.session_state.second_point[0] - st.session_state.first_point[0]
        dy = st.session_state.second_point[1] - st.session_state.first_point[1]
        length = int(np.hypot(dx, dy))
        
        st.image(cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB), 
                 caption="Ось ВПП (красная = порог, синяя = конец, зелёная = ось)",
                 use_container_width=True)
        st.write(f"**Длина оси:** {length} пикселей")

# =============================================================================
# РАСЧЁТ (как в оригинальном приложении)
# =============================================================================

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

# =============================================================================
# ИНСТРУКЦИЯ
# =============================================================================

st.markdown("---")
st.markdown("""
**Инструкция (аналог cv2_selector):**
1. Задайте параметры в боковой панели.
2. Загрузите изображение карты высот.
3. **Кликните по изображению** для выбора первой точки (порог ВПП).
4. **Кликните ещё раз** для выбора второй точки (конец оси).
5. Расчёт выполнится автоматически — как в cv2_selector.py!
""")
