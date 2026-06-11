"""
Модуль базы данных для Telegram-бота TSP Route Optimizer
Поддерживает SQLite с автоматической миграцией схемы
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, ForeignKey, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import config

# Базовый класс для моделей
Base = declarative_base()


class User(Base):
    """Модель пользователя Telegram"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    routes = relationship("Route", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Route(Base):
    """Модель маршрута (результат решения задачи коммивояжёра)"""
    __tablename__ = 'routes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    points = Column(JSON, nullable=False)
    coordinates = Column(JSON, nullable=True)
    order = Column(JSON, nullable=False)
    total_distance = Column(Float, nullable=False)
    
    algorithm = Column(String, default="exact")
    computation_time = Column(Float, nullable=True)
    points_count = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=datetime.now, index=True)
    
    user = relationship("User", back_populates="routes")
    
    def __repr__(self):
        return f"<Route(id={self.id}, user_id={self.user_id}, points={len(self.points)}, distance={self.total_distance:.1f}km)>"


# ============================================================
# ФУНКЦИИ ДЛЯ РАБОТЫ С БАЗОЙ ДАННЫХ (ДО СОЗДАНИЯ engine)
# ============================================================

def get_session():
    """Возвращает новую сессию для работы с БД"""
    return Session()


def get_or_create_user(session, telegram_id, username=None, first_name=None, last_name=None):
    """Находит пользователя по telegram_id или создаёт нового"""
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        session.add(user)
        session.commit()
        print(f"📝 Создан новый пользователь: {telegram_id} ({username or first_name})")
    
    return user


def save_route(session, user_id, points, coordinates, order, total_distance, 
               algorithm="exact", computation_time=None):
    """Сохраняет маршрут в базу данных"""
    route = Route(
        user_id=user_id,
        points=points,
        coordinates=coordinates,
        order=order,
        total_distance=total_distance,
        algorithm=algorithm,
        computation_time=computation_time,
        points_count=len(points)
    )
    session.add(route)
    session.commit()
    print(f"💾 Маршрут сохранён: {len(points)} точек, {total_distance:.1f} км, алгоритм: {algorithm}")
    return route


def get_user_routes(session, user_id, limit=10, offset=0):
    """Возвращает последние N маршрутов пользователя"""
    return session.query(Route).filter_by(user_id=user_id)\
        .order_by(Route.created_at.desc())\
        .limit(limit)\
        .offset(offset)\
        .all()


def get_user_stats(session, user_id):
    """Возвращает статистику пользователя"""
    routes = session.query(Route).filter_by(user_id=user_id).all()
    
    total_routes = len(routes)
    
    if total_routes == 0:
        return {
            "total_routes": 0,
            "total_distance": 0,
            "avg_distance": 0,
            "last_route_date": None,
            "routes_by_algorithm": {}
        }
    
    total_distance = sum(r.total_distance for r in routes)
    avg_distance = total_distance / total_routes
    last_route_date = max(r.created_at for r in routes)
    
    routes_by_algorithm = {}
    for route in routes:
        algo = route.algorithm or "unknown"
        routes_by_algorithm[algo] = routes_by_algorithm.get(algo, 0) + 1
    
    return {
        "total_routes": total_routes,
        "total_distance": round(total_distance, 1),
        "avg_distance": round(avg_distance, 1),
        "last_route_date": last_route_date,
        "routes_by_algorithm": routes_by_algorithm
    }


# ============================================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ (ВСЁ В ОДНОМ МЕСТЕ)
# ============================================================

print("🔌 Подключение к базе данных...")
print(f"   URL: {config.DATABASE_URL}")

# Создаём движок
engine = create_engine(config.DATABASE_URL, echo=False)

# ПРОВЕРКА СУЩЕСТВУЮЩИХ КОЛОНОК ПЕРЕД СОЗДАНИЕМ ТАБЛИЦ
from sqlalchemy import inspect
inspector = inspect(engine)

# Сначала добавляем недостающие колонки (если таблица уже существует)
if 'routes' in inspector.get_table_names():
    existing_columns = [col['name'] for col in inspector.get_columns('routes')]
    
    # Добавляем points_count если нет
    if 'points_count' not in existing_columns:
        print("⚠️ Добавляю колонку points_count в таблицу routes...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE routes ADD COLUMN points_count INTEGER"))
            conn.commit()
        print("✅ Колонка points_count добавлена!")
    
    # Добавляем computation_time если нет
    if 'computation_time' not in existing_columns:
        print("⚠️ Добавляю колонку computation_time в таблицу routes...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE routes ADD COLUMN computation_time FLOAT"))
            conn.commit()
        print("✅ Колонка computation_time добавлена!")
    
    # Добавляем algorithm если нет
    if 'algorithm' not in existing_columns:
        print("⚠️ Добавляю колонку algorithm в таблицу routes...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE routes ADD COLUMN algorithm VARCHAR DEFAULT 'exact'"))
            conn.commit()
        print("✅ Колонка algorithm добавлена!")
    
    # Добавляем coordinates если нет
    if 'coordinates' not in existing_columns:
        print("⚠️ Добавляю колонку coordinates в таблицу routes...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE routes ADD COLUMN coordinates JSON"))
            conn.commit()
        print("✅ Колонка coordinates добавлена!")

# ТЕПЕРЬ создаём таблицы (если их нет, создадутся; если есть — не тронет)
Base.metadata.create_all(engine)

# Обновляем points_count для старых записей (только если колонка существует)
def update_points_count():
    """Обновляет поле points_count для существующих маршрутов"""
    from sqlalchemy import inspect
    inspector = inspect(engine)
    
    if 'routes' in inspector.get_table_names():
        columns = [col['name'] for col in inspector.get_columns('routes')]
        if 'points_count' in columns:
            with engine.connect() as conn:
                # Обновляем записи, где points_count IS NULL
                conn.execute(text("UPDATE routes SET points_count = json_array_length(points) WHERE points_count IS NULL"))
                conn.commit()
                print("✅ points_count обновлён для существующих маршрутов")

update_points_count()

# Создаём фабрику сессий
Session = sessionmaker(bind=engine)

print("✅ База данных готова к работе!")