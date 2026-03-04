# cv2_selector.py
import cv2
import numpy as np
import json
import sys
import os

def main():
    if len(sys.argv) < 5:
        print("Usage: python cv2_selector.py <image_path> <angle> <max_height_m> <output_json>")
        sys.exit(1)

    img_path = sys.argv[1]
    angle = float(sys.argv[2])          # угол оси ВПП (градусы) – может пригодиться
    max_height_phys = float(sys.argv[3])  # максимальная высота на местности (м)
    output_file = sys.argv[4]

    # Загружаем изображение
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if img is None:
        print("Ошибка: не удалось загрузить изображение")
        sys.exit(1)

    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    drawing = img.copy()

    # Переменные состояния
    first_point = None      # базовая точка (порог ВПП)
    second_point = None     # точка окончания оси
    max_height_on_line = 0.0

    # Параметры отображения
    window_name = "Map Selector: left click to set points, 's' to save, 'q' to quit"

    def mouse_callback(event, x, y, flags, param):
        nonlocal first_point, second_point, max_height_on_line, drawing

        if event == cv2.EVENT_LBUTTONDOWN:
            if first_point is None:
                # Первый клик – базовая точка
                first_point = (x, y)
                cv2.circle(drawing, (x, y), 8, (0, 0, 255), -1)
                cv2.putText(drawing, "Base", (x+5, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 1)
                print(f"Базовая точка: ({x}, {y}), яркость {img_gray[y,x]}")
            else:
                # Второй клик – конечная точка оси
                second_point = (x, y)
                cv2.circle(drawing, (x, y), 8, (255, 0, 0), -1)
                cv2.putText(drawing, "End", (x+5, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,0,0), 1)

                # Рисуем линию и ищем максимум
                dx = x - first_point[0]
                dy = y - first_point[1]
                length = int(np.hypot(dx, dy))
                max_val = 0.0
                for t in np.linspace(0, 1, max(1, length)):
                    xi = int(first_point[0] + t * dx)
                    yi = int(first_point[1] + t * dy)
                    if 0 <= xi < img_gray.shape[1] and 0 <= yi < img_gray.shape[0]:
                        cv2.circle(drawing, (xi, yi), 1, (0, 255, 0), -1)
                        brightness = img_gray[yi, xi]
                        height = (brightness / 255.0) * max_height_phys
                        if height > max_val:
                            max_val = height

                max_height_on_line = max_val
                print(f"Максимальная высота на линии: {max_height_on_line:.2f} м")
                cv2.putText(drawing, f"Max: {max_height_on_line:.1f} m", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback)

    print("Инструкция:")
    print("  Левый клик – поставить базовую точку (порог ВПП)")
    print("  Второй левый клик – поставить конечную точку оси")
    print("  Нажмите 's' для сохранения результата и выхода")
    print("  Нажмите 'q' для выхода без сохранения")

    while True:
        cv2.imshow(window_name, drawing)
        key = cv2.waitKey(20) & 0xFF
        if key == ord('q'):
            print("Выход без сохранения")
            break
        if key == ord('s'):
            if first_point is not None and second_point is not None:
                # Сохраняем результат
                result = {
                    "first_point": first_point,
                    "second_point": second_point,
                    "max_height": max_height_on_line,
                    "angle_used": angle
                }
                with open(output_file, 'w') as f:
                    json.dump(result, f)
                print(f"Результаты сохранены в {output_file}")
                break
            else:
                print("Сначала выберите обе точки!")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()