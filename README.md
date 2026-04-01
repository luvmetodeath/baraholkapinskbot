
## СТРУКТУРА
flea_market_bot/
├── main.py                  Запуск бота
├── config.py                Настройки бота
├── requirements.txt         Нужные приколы
├── database/
│   ├── __init__.py
│   ├── db.py                подключение к базе
│   ├── users.py            Челики
│   └── posts.py            Посты
├── services/
│   ├── __init__.py
│   ├── post_service.py      Код публикаций
│   └── validators.py       
└── handlers/
    ├── __init__.py
    ├── states.py            
    ├── user_handlers.py     Код челов
    └── admin_handlers.py    Код админов
```

---

## ⚙️ Настройка

### 1. Отредактируй `config.py`

```python
BOT_TOKEN = "токен он @botfather"
CHANNEL_ID = "@ваш канал"  # 
ADMIN_IDS = [123456789]    # айдишник в тг @gemyid
```

!!!Бот должен быть администратором канала с правом публикации сообщений.!!!

Виртуальное окружение

```bash
python -m venv venv
venv\Scripts\activate.bat
```

!!!Зависимости!!! ОЧЕНЬ ВАЖНО

```bash
pip install -r requirements.txt
```

ЗАПУСК БОТА (ЕСЛИ НА ПК) НА СЕРВЕ ОНО НЕ НАДО БУДЕТ

```bash
python main.py
```

Логи пишутся в `logs.txt`.