from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='Мои подписки'), KeyboardButton(text='Добавить ИНН')],
            [KeyboardButton(text='Проверить сейчас'), KeyboardButton(text='Расписание')],
            [KeyboardButton(text='Уведомления'), KeyboardButton(text='Помощь')],
        ],
        resize_keyboard=True,
    )


def watch_actions(inn: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Проверить сейчас', callback_data=f'check:{inn}')],
        [InlineKeyboardButton(text='Удалить подписку', callback_data=f'unwatch:{inn}')],
    ])


def schedule_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Каждые 2 минуты', callback_data='schedule:every_2_min')],
        [InlineKeyboardButton(text='Каждый час', callback_data='schedule:hourly')],
        [InlineKeyboardButton(text='Ежедневно', callback_data='schedule:daily')],
        [InlineKeyboardButton(text='Еженедельно', callback_data='schedule:weekly')],
        [InlineKeyboardButton(text='Ежемесячно', callback_data='schedule:monthly')],
    ])


def notifications_menu(notify_on_no_change: bool) -> InlineKeyboardMarkup:
    state_label = 'выключено' if not notify_on_no_change else 'включено'
    toggle_label = 'Включить' if not notify_on_no_change else 'Выключить'
    toggle_value = 'on' if not notify_on_no_change else 'off'

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f'Уведомлять без изменений: {state_label}',
                              callback_data='noop')],
        [InlineKeyboardButton(text=toggle_label,
                              callback_data=f'notify_no_change:{toggle_value}')],
    ])