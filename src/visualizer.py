"""
Модуль визуализации маршрутов
Генерирует PNG-изображение карты для отправки в Telegram
"""

import os
import tempfile
from datetime import datetime
from playwright.sync_api import sync_playwright


def create_route_png(coordinates, points_names, path, filename=None):
    """
    Создаёт PNG-изображение карты маршрута
    """
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"route_map_{timestamp}.png"
    
    # Генерируем HTML
    html_content = generate_html_map(coordinates, points_names, path)
    
    # Сохраняем HTML во временный файл
    html_path = os.path.join(tempfile.gettempdir(), f"temp_map_{timestamp}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Конвертируем HTML в PNG через Playwright
    png_path = os.path.join(tempfile.gettempdir(), filename)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1200, 'height': 800})
        page.goto(f'file://{html_path}')
        page.wait_for_timeout(2000)  # Ждём загрузки карты
        page.screenshot(path=png_path, full_page=True)
        browser.close()
    
    # Удаляем временный HTML
    os.unlink(html_path)
    
    return png_path


def generate_html_map(coordinates, points_names, path):
    """
    Генерирует HTML-код карты (без сохранения в файл)
    """
    
    ordered_coords = [coordinates[idx] for idx in path]
    ordered_names = [points_names[idx] for idx in path]
    
    center_lat = sum(c[0] for c in coordinates) / len(coordinates)
    center_lon = sum(c[1] for c in coordinates) / len(coordinates)
    
    # Формируем список точек для JavaScript
    points_js = []
    for i, (coord, name) in enumerate(zip(ordered_coords, ordered_names)):
        number = i + 1
        if i == 0:
            color = 'green'
            icon = '🚩'
        elif i == len(ordered_coords) - 1:
            color = 'red'
            icon = '🏁'
        else:
            color = 'blue'
            icon = '📍'
        
        points_js.append(f"""
            L.marker([{coord[0]}, {coord[1]}], {{
                icon: L.divIcon({{
                    html: '<div style="background-color: {color}; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; border: 2px solid white;">{number}</div>',
                    className: 'custom-div-icon',
                    iconSize: [24, 24]
                }})
            }}).bindPopup('<b>{number}. {name}</b><br>{icon} {name}<br>Координаты: {coord[0]:.4f}, {coord[1]:.4f}').addTo(map);
        """)
    
    # Координаты для линии маршрута
    line_coords = "], [".join([f"[{coord[0]}, {coord[1]}]" for coord in ordered_coords])
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Маршрут</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ width: 100%; height: 800px; }}
        .custom-div-icon {{ background: transparent; border: none; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], 5);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CartoDB'
        }}).addTo(map);
        
        {"".join(points_js)}
        
        L.polyline([[{line_coords}]], {{ color: '#3388ff', weight: 4, opacity: 0.8 }}).addTo(map);
    </script>
</body>
</html>"""
    
    return html


# Старая функция (оставляем для совместимости)
def create_route_html(coordinates, points_names, path, filename=None):
    """Генерирует HTML-карту (без конвертации в PNG)"""
    html_content = generate_html_map(coordinates, points_names, path)
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"route_map_{timestamp}.html"
    
    filepath = os.path.join(tempfile.gettempdir(), filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filepath