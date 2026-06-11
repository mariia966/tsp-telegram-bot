"""
Решение задачи коммивояжёра (TSP) через OpenRouteService API
"""

import requests
import itertools
import config
from math import radians, sin, cos, sqrt, atan2

# Отключаем предупреждения SSL
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Сессия без прокси
session = requests.Session()
session.verify = False


# ============================================================
# ГЕОКОДИРОВАНИЕ
# ============================================================

_geocode_cache = {}

def geocode_address(address: str):
    """Преобразует адрес в координаты"""
    if address in _geocode_cache:
        print(f"📦 Кэш: {address}")
        return _geocode_cache[address]
    
    url = "https://api.openrouteservice.org/geocode/search"
    headers = {"Authorization": config.ORS_API_KEY}
    params = {"text": address, "size": 1}
    
    try:
        print(f"🌍 Геокодирую: {address}")
        resp = session.get(url, headers=headers, params=params, timeout=15)
        
        if resp.status_code == 200:
            data = resp.json()
            if data.get("features"):
                lon, lat = data["features"][0]["geometry"]["coordinates"]
                coords = (lat, lon)
                _geocode_cache[address] = coords
                print(f"✅ {address} -> {coords}")
                return coords
        else:
            print(f"⚠️ Ошибка {resp.status_code} для {address}")
            
    except Exception as e:
        print(f"⚠️ Ошибка геокодинга {address}: {e}")
    
    # Fallback
    print(f"⚠️ Использую Москву для {address}")
    return (55.7558, 37.6176)


# ============================================================
# РАССТОЯНИЯ
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2*atan2(sqrt(a), sqrt(1-a))
    return R * c


def get_distance_matrix(coords):
    """Матрица расстояний через Matrix API"""
    n = len(coords)
    matrix = [[0]*n for _ in range(n)]
    
    locations = [[lon, lat] for lat, lon in coords]
    url = "https://api.openrouteservice.org/v2/matrix/driving-car"
    headers = {"Authorization": config.ORS_API_KEY, "Content-Type": "application/json"}
    payload = {"locations": locations, "metrics": ["distance"], "units": "km"}
    
    try:
        print(f"📡 Запрашиваю матрицу {n}x{n}...")
        resp = session.post(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code == 200:
            distances = resp.json()["distances"]
            for i in range(n):
                for j in range(n):
                    if i != j:
                        matrix[i][j] = distances[i][j]
            print("✅ Матрица получена")
            return matrix
        else:
            print(f"⚠️ Matrix API ошибка: {resp.status_code}")
            
    except Exception as e:
        print(f"⚠️ Matrix API ошибка: {e}")
    
    # Fallback на прямые расстояния
    print("📡 Использую прямые расстояния (haversine)")
    for i in range(n):
        for j in range(i+1, n):
            d = haversine(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            matrix[i][j] = matrix[j][i] = d
    return matrix


# ============================================================
# TSP РЕШАТЕЛЬ
# ============================================================

class TSPSolverAuto:
    def solve(self, coordinates, fixed_start=0, closed=False, force_exact=False, force_heuristic=False):
        """
        Решает TSP
        
        Параметры:
        - coordinates: список координат
        - fixed_start: индекс стартовой точки (0 = первый город)
        - closed: игнорируется (всегда разомкнутый маршрут)
        - force_exact: принудительно точный алгоритм
        - force_heuristic: принудительно эвристический
        """
        import time
        start_time = time.time()
        n = len(coordinates)
        
        # Получаем матрицу расстояний
        matrix = get_distance_matrix(coordinates)
        
        # Выбираем алгоритм
        use_exact = force_exact or (n <= 7 and not force_heuristic)
        
        if use_exact:
            # Точный перебор с фиксацией старта
            others = [i for i in range(n) if i != fixed_start]
            best_path = None
            best_dist = float('inf')
            
            for perm in itertools.permutations(others):
                path = [fixed_start] + list(perm)
                # Разомкнутый маршрут (без возврата)
                dist = sum(matrix[path[i]][path[i+1]] for i in range(n-1))
                if dist < best_dist:
                    best_dist = dist
                    best_path = path
            
            algorithm = "exact (полный перебор)"
        else:
            # Жадный алгоритм + 2-opt
            def greedy(start):
                visited = [False]*n
                path = [start]
                visited[start] = True
                for _ in range(n-1):
                    cur = path[-1]
                    # Находим ближайший непосещённый город
                    best_next = None
                    best_dist = float('inf')
                    for i in range(n):
                        if not visited[i] and matrix[cur][i] < best_dist:
                            best_dist = matrix[cur][i]
                            best_next = i
                    if best_next is not None:
                        path.append(best_next)
                        visited[best_next] = True
                return path
            
            def two_opt(path):
                improved = True
                while improved:
                    improved = False
                    for i in range(1, n-1):
                        for j in range(i+1, n):
                            if j == n-1:
                                continue
                            # Текущая длина двух рёбер
                            cur = matrix[path[i-1]][path[i]] + matrix[path[j-1]][path[j]]
                            # Новая длина после переворота
                            new = matrix[path[i-1]][path[j-1]] + matrix[path[i]][path[j]]
                            if new < cur - 0.001:
                                path[i:j] = reversed(path[i:j])
                                improved = True
                                break
                        if improved:
                            break
                return path
            
            # Пробуем разные стартовые точки
            best_path = None
            best_dist = float('inf')
            start_cities = [fixed_start] if fixed_start is not None else range(min(n, 5))
            
            for start in start_cities:
                path = greedy(start)
                path = two_opt(path)
                dist = sum(matrix[path[i]][path[i+1]] for i in range(n-1))
                if dist < best_dist:
                    best_dist = dist
                    best_path = path.copy()
            
            algorithm = "heuristic (жадный + 2-opt)"
        
        computation_time = time.time() - start_time
        return best_path, best_dist, algorithm, computation_time


# Создаём экземпляр для удобного импорта
auto_solver = TSPSolverAuto()