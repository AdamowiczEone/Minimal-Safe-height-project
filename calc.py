# calc.py
from dataclasses import dataclass
from typing import Optional, Tuple
import numpy as np

@dataclass
class MapInfo:
    """
    Информация о карте высот.
    _scale: масштаб (км/пиксель)
    _angle: угол оси ВПП (радианы)
    _max_height: максимальная высота на карте (в пиксельных значениях, 0-255)
    max_height_measure: максимальная физическая высота (м)
    """
    _scale: Optional[float] = 0.0
    _angle: Optional[float] = 0.0
    _max_height: Optional[int] = 0
    max_height_measure: float = 0.0

    @property
    def scale(self) -> float:
        return self._scale

    @scale.setter
    def scale(self, value: Tuple[np.ndarray, np.ndarray, float]):
        """
        Устанавливает масштаб по двум точкам и реальному расстоянию.
        value: (first_point, second_point, distance_km)
        """
        first_point, second_point, distance_km = value
        pixel_dist = np.linalg.norm(abs(first_point - second_point))
        self._scale = distance_km / pixel_dist if pixel_dist != 0 else 0.0

    @property
    def angle(self) -> float:
        """Угол в градусах (для пользователя)"""
        return np.rad2deg(self._angle)

    @angle.setter
    def angle(self, value_deg: float):
        """Устанавливает угол в радианах из градусов"""
        self._angle = np.radians(value_deg)


class MinimalSafeHeight:
    """
    Расчёт минимальной безопасной высоты по формулам QFE и QNH.
    """
    L_0 = 0.0065  # температурный градиент, °C/м

    def __init__(self, H_air: float, H_obstcl: float, t_air: float, MAH: int):
        """
        H_air   – абсолютная высота аэродрома (м)
        H_obstcl– абсолютная высота препятствия (м)
        t_air   – температура воздуха на аэродроме (°C)
        MAH     – тип минимального запаса высоты: 1 -> 330 футов (≈100 м), 2 -> 660 футов (≈200 м)
        """
        if MAH not in (1, 2):
            raise ValueError("MAH must be 1 or 2")
        self.MAH = 330 * MAH          # в футах, для справки
        # Более точный перевод в метры: 1 фут = 0.3048 м
        self.MAH_m = 330 * 0.3048 if MAH == 1 else 660 * 0.3048
        self.H_air = H_air
        self.H_obstcl = H_obstcl
        self.t_air = t_air

    @property
    def H(self) -> float:
        """Высота, используемая для расчёта температурной поправки (абсолютная высота препятствия + запас)"""
        return self.H_obstcl + self.MAH_m

    @property
    def t_0(self) -> float:
        """Температура на уровне моря, приведённая от аэродрома"""
        return self.t_air + self.L_0 * self.H_air

    @property
    def delta_H(self) -> float:
        """Температурная поправка (вычисляется по абсолютной высоте H)"""
        # Формула из исходных набросков:
        # delta_H = H * (15 - t0) / (273 + t0 - 0.5 * L0 * (H + H_air))
        denominator = 273 + self.t_0 - 0.5 * self.L_0 * (self.H + self.H_air)
        if denominator == 0:
            return 0.0
        return self.H * ((15 - self.t_0) / denominator)

    def QFE(self) -> float:
        """
        Относительная безопасная высота (QFE) – отсчёт от уровня порога ВПП.
        Формула: (H_obstcl - H_air) + МЗВ + ΔH_t
        """
        rel_obstacle = self.H_obstcl - self.H_air
        return rel_obstacle + self.MAH_m + self.delta_H

    def QNH(self) -> float:
        """
        Абсолютная безопасная высота (QNH) – отсчёт от уровня моря.
        Формула: H_obstcl + МЗВ + ΔH_t
        """
        return self.H_obstcl + self.MAH_m + self.delta_H

    @staticmethod
    def round_to_100ft(value_m: float) -> float:
        """Округление вверх до ближайших 100 футов (30.48 м)"""
        feet = value_m / 0.3048
        rounded_feet = np.ceil(feet / 100) * 100
        return rounded_feet * 0.3048


class MapCalc:
    """Класс для работы с картой (анализ линии и препятствий)"""
    def __init__(self, map_info: MapInfo, img_gray: np.ndarray):
        self.map = map_info
        self.img = img_gray  # одноканальное изображение (grayscale)

    def generate_line(self, start: Tuple[int, int], end: Tuple[int, int]) -> np.ndarray:
        """
        Генерирует массив точек между двумя точками (алгоритм через linspace)
        """
        x1, y1 = start
        x2, y2 = end
        length = int(np.hypot(x2 - x1, y2 - y1))
        if length == 0:
            return np.array([[x1, y1]])
        x = np.linspace(x1, x2, length).astype(int)
        y = np.linspace(y1, y2, length).astype(int)
        return np.column_stack((x, y))

    def find_highest_obstacle(self, line_points: np.ndarray) -> Tuple[Optional[Tuple[int, int]], float]:
        """
        Находит максимальную высоту (в метрах) на заданной линии,
        используя яркость пикселей и максимальную физическую высоту.
        Возвращает координаты и высоту.
        """
        max_h = 0.0
        max_coord = None
        for x, y in line_points:
            if 0 <= x < self.img.shape[1] and 0 <= y < self.img.shape[0]:
                brightness = self.img[y, x]  # 0..255
                # Предполагаем линейную зависимость: 0 -> 0, 255 -> max_height_measure
                height = (brightness / 255.0) * self.map.max_height_measure
                if height > max_h:
                    max_h = height
                    max_coord = (x, y)
        return max_coord, max_h

    def find_highest_in_direction(self, start: Tuple[int, int], angle_deg: float, length_px: int) -> Tuple[Optional[Tuple[int, int]], float]:
        """
        Строит линию от start под углом angle_deg длиной length_px и ищет максимум.
        """
        angle_rad = np.radians(angle_deg)
        dx = int(length_px * np.cos(angle_rad))
        dy = -int(length_px * np.sin(angle_rad))  # минус, т.к. y растёт вниз
        end = (start[0] + dx, start[1] + dy)
        line = self.generate_line(start, end)
        return self.find_highest_obstacle(line)