# Инструкция по восстановлению и запуску Excursions_bot

## Что это

Excursions_bot — Telegram-бот для автоматизации экскурсионного бизнеса.
Клиентская часть, панель капитана, админ-панель, онлайн-оплата через YooKassa.

Проект написан на Python 3.11+, aiogram 3.x, SQLAlchemy 2.0, Redis.
Разработчик — Илья Гройс, iliagrois@gmail.com

## Системные требования

- Python 3.11 или новее
- Redis (любая свежая версия)
- Доступ к интернету (для Telegram API и YooKassa)

Для Linux:
- systemd или supervisor для автозапуска (опционально)
- timedatectl для настройки часового пояса

## Что лежит в папке проекта

- run.py — точка входа, запуск бота
- requirements.txt — зависимости Python
- database_ex.db — база данных SQLite с тестовыми данными (для примера, можно затем удалить и она создастся автоматически при запуске бота. Оригинальное название database.db)
- docker-compose.yml — быстрый запуск в Docker
- .env.example — пример конфигурации (переименовать в .env и заполнить)
- app/ — исходный код
- tests/ — тесты
- logs/ — логи (появятся при запуске)
- soglasie_na_obrabotku_PD.pdf — согласие на обработку персональных данных для взрослых
- soglasie_na_obrabotku_PD_nesoversh.pdf — согласие для несовершеннолетних

## Получение токенов

### Telegram Bot Token

1. Написать в Telegram боту @BotFather
2. Команда /newbot
3. Указать имя бота (например: Экскурсии Иркутск)
4. Указать username бота (например: irk_excursions_bot)
5. Полученный токен скопировать в .env в поле TG_TOKEN

### YooKassa (платежи)

1. Зарегистрироваться на yookassa.ru
2. Создать магазин
3. Получить shopId и секретный ключ в настройках магазина
4. Записать в .env: YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY

На время тестирования можно не заполнять YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY.
Бот запустится, но онлайн-оплата работать не будет.

## Способ 1: Быстрый запуск через Docker

### Предварительные требования
- Установленный Docker и Docker Compose

### Запуск

Создать файл .env в корне проекта (рядом с docker-compose.yml):

TG_TOKEN=ваш_токен_бота
PAYMENTS_TOKEN=ваш_токен_yookassa
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_секретный_ключ
LOG_LEVEL=INFO
ENABLE_CONSOLE_LOGGING=false
ENABLE_FILE_LOGGING=true
LOG_DIR=logs
ROTATION_MAX_SIZE_MB=10
ROTATION_BACKUP_COUNT=5
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REFUND_HOURS_BEFORE=4

Запустить:

docker-compose up -d

Бот запустится. Логи будут доступны через docker logs excursions_bot.

Остановить:

docker-compose down

## Способ 2: Ручной запуск (без Docker)

### Шаг 1: Установка Python и Redis

Ubuntu/Debian:

sudo apt update
sudo apt install python3.11 python3.11-venv redis-server

macOS:

brew install python@3.11 redis

Windows:
- Скачать Python 3.11 с python.org
- Redis скачать с github.com/microsoftarchive/redis/releases (или использовать WSL)

### Шаг 2: Настройка часового пояса

Важно! Все даты и время в базе данных хранятся в часовом поясе Иркутска
(Asia/Irkutsk, UTC+8). Если сервер в другом часовом поясе, данные поедут.

Установить часовой пояс:

sudo timedatectl set-timezone Asia/Irkutsk
date

Должно показать время с +08.

Если сервер физически находится в другом регионе и переключать пояс нельзя —
свяжитесь с разработчиком для миграции данных.

### Шаг 3: Создание виртуального окружения

cd путь_к_проекту

python3.11 -m venv venv

# Активация (Linux/macOS)
source venv/bin/activate

# Активация (Windows)
venv\Scripts\activate

### Шаг 4: Установка зависимостей

pip install -r requirements.txt

### Шаг 5: Конфигурация

Создать файл .env в корне проекта:

TG_TOKEN=ваш_токен_бота
PAYMENTS_TOKEN=ваш_токен_yookassa
YOOKASSA_SHOP_ID=ваш_shop_id
YOOKASSA_SECRET_KEY=ваш_секретный_ключ
LOG_LEVEL=INFO
ENABLE_CONSOLE_LOGGING=false
ENABLE_FILE_LOGGING=true
LOG_DIR=logs
ROTATION_MAX_SIZE_MB=10
ROTATION_BACKUP_COUNT=5
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REFUND_HOURS_BEFORE=4

### Шаг 6: Запуск

Убедиться что Redis запущен:

redis-cli ping
# Должен ответить PONG

Запустить бота:

python run.py

## Как сделать первого администратора

1. Зарегистрироваться в боте как обычный пользователь (через команду /start и кнопку "Личный кабинет")

2. Написать в бот команду /first_admin

   Если в системе ещё нет ни одного администратора, вы получите права администратора.
   Если администраторы уже есть — команда сообщит об этом и предложит обратиться к ним.

3. После назначения станут доступны:
   - /admin — вход в админ-панель
   - /promote — назначение других администраторов и капитанов

Если что-то пошло не так — обратитесь к разработчику.
Можно открыть database.db через программу SQLiteStudio и вручную поменять в
таблице users (вкладка "Данные") значение ячейки role с 'client' на 'admin',
после чего сохранить изменения

## Структура бота

После запуска будут доступны команды:

- /start — главное меню клиента
- /admin — вход в админ-панель (только для администраторов)
- /captain — вход в панель капитана (только для капитанов)

## Логи

Логи находятся в папке logs/:

- logs/app.log — основной лог
- logs/errors.log — дублирование ошибок

При ошибках в первую очередь проверять эти файлы.

## Резервное копирование

Рекомендуется регулярно копировать файл database.db.
В нём вся информация о пользователях, бронированиях, платежах.

## Контакты

Разработчик: Илья Гройс
Email: iliagrois@gmail.com

При проблемах с запуском, восстановлением или доработкой — обращаться.