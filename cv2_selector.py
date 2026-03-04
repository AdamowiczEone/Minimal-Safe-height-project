# cv2_selector.py
import cv2
import numpy as np
import json
import sys
import os

def calculate_max_height(img_gray, first_point, second_point, max_height_phys):
    """Calculate maximum height along the line between two points."""
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

def main():
    if len(sys.argv) < 5:
        print("Usage: python cv2_selector.py <image_path> <angle> <max_height_m> <output_json>")
        sys.exit(1)

    img_path = sys.argv[1]
    angle = float(sys.argv[2])
    max_height_phys = float(sys.argv[3])
    output_file = sys.argv[4]

    # Загружаем изображение
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if img is None:
        print("Ошибка: не удалось загрузить изображение")
        sys.exit(1)

    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Check for pre-defined points via environment or additional args
    # Format: first_x,first_y,second_x,second_y
    points_str = os.environ.get("RUNWAY_POINTS", "")
    
    if points_str and len(sys.argv) > 5:
        # Points passed as 5th argument
        points_str = sys.argv[5]
    
    if points_str:
        coords = list(map(int, points_str.split(",")))
        if len(coords) == 4:
            first_point = (coords[0], coords[1])
            second_point = (coords[2], coords[3])
            max_height_on_line = calculate_max_height(img_gray, first_point, second_point, max_height_phys)
            
            result = {
                "first_point": list(first_point),
                "second_point": list(second_point),
                "max_height": max_height_on_line,
                "angle_used": angle
            }
            with open(output_file, 'w') as f:
                json.dump(result, f)
            print(f"Результаты сохранены в {output_file}")
            return

    # Web mode: output image with grid for user to determine coordinates
    # Save analysis image with grid overlay
    grid_img = img.copy()
    h, w = img_gray.shape[:2]
    
    # Draw grid
    for x in range(0, w, 100):
        cv2.line(grid_img, (x, 0), (x, h), (255, 0, 0), 1)
    for y in range(0, h, 100):
        cv2.line(grid_img, (0, y), (w, y), (255, 0, 0), 1)
    
    # Save grid image
    grid_path = img_path.replace(".png", "_grid.png").replace(".jpg", "_grid.png")
    if grid_path == img_path:
        grid_path = img_path.rsplit(".", 1)[0] + "_grid.png"
    cv2.imwrite(grid_path, grid_img)
    
    # Output info for web interface
    print(f"GRID_IMAGE:{grid_path}")
    print(f"IMAGE_SIZE:{w}x{h}")
    print("Please select two points on the map (runway threshold and end point)")
    print("Set RUNWAY_POINTS environment variable or pass as 5th argument: x1,y1,x2,y2")
    
    # Create empty result for web app to fill
    result = {
        "first_point": None,
        "second_point": None,
        "max_height": None,
        "angle_used": angle,
        "image_size": [w, h],
        "grid_image": grid_path
    }
    with open(output_file, 'w') as f:
        json.dump(result, f)

if __name__ == "__main__":
    main()