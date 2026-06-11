"""
Модуль визуализации маршрутов
Генерирует интерактивные HTML-карты с помощью Folium
"""

import folium
import os
import tempfile
from datetime import datetime


def create_route_html(coordinates, points_names, path, filename=None):
    """
    Создаёт HTML-карту маршрута
    
    Аргументы:
    - coordinates: список кортежей [(lat, lon), ...]
    - points_names: список названий точек
    - path: порядок обхода (список индексов)
    - filename: имя файла (если None, создаётся автоматически)
    
    Возвращает:
    - путь к созданному HTML-файлу
    """
    
    # Если имя файла не указано, создаём с timestamp
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"route_map_{timestamp}.html"
    
    # Получаем координаты точек в правильном порядке
    ordered_coords = [coordinates[idx] for idx in path]
    ordered_names = [points_names[idx] for idx in path]
    
    # Вычисляем центр карты
    center_lat = sum(c[0] for c in coordinates) / len(coordinates)
    center_lon = sum(c[1] for c in coordinates) / len(coordinates)
    
    # Создаём карту
    route_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=6,
        tiles='OpenStreetMap'
    )
    
    # Добавляем маркеры для каждой точки
    for i, (coord, name) in enumerate(zip(ordered_coords, ordered_names)):
        number = i + 1
        
        # Определяем цвет маркера
        if i == 0:
            icon_color = 'green'
        elif i == len(ordered_coords) - 1:
            icon_color = 'red'
        else:
            icon_color = 'blue'
        
        # Текст всплывающей подсказки
        popup_text = f"""
        <b>{number}. {name}</b><br>
        <i>Координаты:</i> {coord[0]:.4f}, {coord[1]:.4f}
        """
        
        # Добавляем маркер
        folium.Marker(
            location=[coord[0], coord[1]],
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{number}. {name}",
            icon=folium.Icon(color=icon_color, icon='info-sign', prefix='glyphicon')
        ).add_to(route_map)
        
        # Добавляем кружок с номером
        folium.map.Marker(
            [coord[0], coord[1]],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 14px; font-weight: bold; color: white; background-color: {icon_color}; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border: 2px solid white;">{number}</div>'
            )
        ).add_to(route_map)
    
    # Добавляем линию маршрута
    folium.PolyLine(
        locations=ordered_coords,
        color='blue',
        weight=4,
        opacity=0.8,
        popup='Маршрут'
    ).add_to(route_map)
    
    # Добавляем стрелки направления
    for i in range(len(ordered_coords) - 1):
        mid_lat = (ordered_coords[i][0] + ordered_coords[i+1][0]) / 2
        mid_lon = (ordered_coords[i][1] + ordered_coords[i+1][1]) / 2
        folium.RegularPolygonMarker(
            location=[mid_lat, mid_lon],
            color='blue',
            fill=True,
            fill_color='blue',
            number_of_sides=3,
            radius=6,
            rotation=0
        ).add_to(route_map)
    
    # Добавляем легенду
    legend_html = '''
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000; background-color: white; padding: 10px; border-radius: 8px; border: 2px solid grey; font-size: 12px; font-family: Arial, sans-serif;">
        <b>📖 Легенда:</b><br>
        🟢 <span style="color: green;">Старт</span><br>
        🔵 <span style="color: blue;">Промежуточная точка</span><br>
        🔴 <span style="color: red;">Финиш</span><br>
        🔵 <span style="color: blue;">—— Линия маршрута</span>
    </div>
    '''
    route_map.get_root().html.add_child(folium.Element(legend_html))
    
    # Сохраняем карту
    filepath = os.path.join(tempfile.gettempdir(), filename)
    route_map.save(filepath)
    
    print(f"🗺️ Карта сохранена: {filepath}")
    return filepath


# Упрощённый алиас
create_route_map = create_route_html