# настройки бота

# Токен бота (получить у @BotFather)
BOT_TOKEN = os.getenv"8741526930:AAGFfZj152slRGbF87steBfOpbWTjkOZjso"

# ID канала для публикации объявлений (например: @my_channel или -1001234567890)
CHANNEL_ID = "@testbaraholkapinskbot"

# Список Telegram user_id администраторов
ADMIN_IDS = [
    1025207777,  # замените на реальные ID
]

# Ограничение: одна публикация раз в N минут
POST_COOLDOWN_MINUTES = 10

# Через сколько дней после публикации отправлять напоминание
REMINDER_DAYS = 3

# Сколько жалоб нужно чтобы уведомить всех админов
COMPLAINT_THRESHOLD = 3

# Ограничения длинны 
TITLE_MAX_LEN = 150
DESCRIPTION_MAX_LEN = 1500
