import re
import config


def validate_title(text: str) -> tuple[bool, str]:
    """Возвращает (ok, cleaned_or_error)."""
    text = text.strip()
    if not text:
        return False, "Название не может быть пустым."
    if len(text) > config.TITLE_MAX_LEN:
        return False, f"Слишком длинное название. Максимум {config.TITLE_MAX_LEN} символов."
    return True, text


def validate_description(text: str) -> tuple[bool, str]:
    text = text.strip()
    if not text:
        return False, "Описание не может быть пустым."
    # Обрезаем до максимума без ошибки
    if len(text) > config.DESCRIPTION_MAX_LEN:
        text = text[: config.DESCRIPTION_MAX_LEN]
    return True, text


def validate_price(text: str) -> tuple[bool, str]:
    text = text.strip()
    # Разрешаем: цифры, пробелы, запятые, точки, $, ₽, знак «договорная»
    pattern = r"^[\d\s.,]+[\s]*([$₽руб\.]*)?$|^[Дд]оговорная?$|^[Бб]есплатно$"
    if re.match(pattern, text, re.IGNORECASE):
        return True, text
    return False, "Некорректная цена. Введите число (например: 500, 1500 ₽, 20$)."
