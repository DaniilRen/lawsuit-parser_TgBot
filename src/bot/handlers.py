from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from src.config import Config
from src.database.db_manager import BotDatabase
from src.api_client.parser_client import ParserClient, ParserApiError
from src.bot import formatting
from src.bot.keyboards import main_menu, watch_actions, schedule_menu, notifications_menu
from src.utils.logger import setup_logger


router = Router()
logger = setup_logger()

_db: Optional[BotDatabase] = None
_parser: Optional[ParserClient] = None


SCHEDULE_LABELS = {
    'every_2_min': 'каждые 2 минуты',
    'hourly': 'каждый час',
    'daily': 'ежедневно',
    'weekly': 'еженедельно',
    'monthly': 'ежемесячно',
}


def init_handlers(db: BotDatabase, parser: ParserClient) -> None:
    global _db, _parser
    _db = db
    _parser = parser


def _is_valid_inn(inn: str) -> bool:
    if not inn or not inn.isdigit():
        return False
    return len(inn) in (10, 12)


def _extract_company_name(latest: dict) -> Optional[str]:
    sources = latest.get('sources', {})
    for source_data in sources.values():
        if isinstance(source_data, dict):
            name = source_data.get('company_name') or source_data.get('short_name')
            if name:
                return name
    return None


async def _guard(message: Message) -> bool:
    user = _db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or '',
        full_name=message.from_user.full_name or '',
    )
    if not user.is_allowed:
        await message.answer(
            'Доступ запрещён. Обратитесь к администратору для добавления в белый список.'
        )
        return False
    return True


async def _guard_callback(callback: CallbackQuery) -> bool:
    user = _db.get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username or '',
        full_name=callback.from_user.full_name or '',
    )
    if not user.is_allowed:
        await callback.answer('Доступ запрещён', show_alert=True)
        return False
    return True


async def _send(chat_id: int, text: str) -> None:
    from src.bot.app import get_bot
    bot = get_bot()
    await bot.send_message(chat_id=chat_id, text=text, parse_mode=None)


@router.message(Command('start'))
async def cmd_start(message: Message):
    _db.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username or '',
        full_name=message.from_user.full_name or '',
    )

    if message.from_user.id == Config.ADMIN_TELEGRAM_ID:
        _db.allow_user(message.from_user.id)

    if not await _guard(message):
        return

    await message.answer(
        'Привет. Я слежу за изменениями в данных компаний.\n\n'
        'Добавьте ИНН через кнопку «Добавить ИНН», и я буду проверять его '
        'по расписанию и сообщать об изменениях.',
        reply_markup=main_menu(),
        parse_mode=None,
    )


@router.message(Command('help'))
@router.message(F.text == 'Помощь')
async def cmd_help(message: Message):
    if not await _guard(message):
        return
    await message.answer(
        'Доступные команды:\n\n'
        '/start — начать\n'
        '/watch ИНН [название] — добавить подписку\n'
        '/unwatch ИНН — удалить подписку\n'
        '/list — список моих подписок\n'
        '/check ИНН — проверить сейчас\n'
        '/schedule — изменить расписание\n'
        '/notify — уведомления без изменений\n'
        '/help — эта справка',
        parse_mode=None,
    )


@router.message(Command('list'))
@router.message(F.text == 'Мои подписки')
async def cmd_list(message: Message):
    if not await _guard(message):
        return

    watches = _db.get_user_watches(message.from_user.id)
    if not watches:
        await message.answer('У вас пока нет подписок.', parse_mode=None)
        return

    for watch in watches:
        label = f'{watch.label}\n' if watch.label else ''
        text = f'{label}ИНН: {watch.inn}'
        await message.answer(text, reply_markup=watch_actions(watch.inn), parse_mode=None)


@router.message(Command('watch'))
async def cmd_watch(message: Message):
    if not await _guard(message):
        return

    args = (message.text or '').split(maxsplit=2)
    if len(args) < 2:
        await message.answer('Использование: /watch ИНН [название]', parse_mode=None)
        return

    inn = args[1].strip()
    label = args[2].strip() if len(args) > 2 else None

    if not _is_valid_inn(inn):
        await message.answer('Неверный формат ИНН. Ожидается 10 или 12 цифр.', parse_mode=None)
        return

    _db.add_watch(message.from_user.id, inn, label)
    await message.answer(f'Подписка на ИНН {inn} добавлена.', parse_mode=None)


@router.message(Command('unwatch'))
async def cmd_unwatch(message: Message):
    if not await _guard(message):
        return

    args = (message.text or '').split(maxsplit=1)
    if len(args) < 2:
        await message.answer('Использование: /unwatch ИНН', parse_mode=None)
        return

    inn = args[1].strip()
    if _db.remove_watch(message.from_user.id, inn):
        await message.answer(f'Подписка на ИНН {inn} удалена.', parse_mode=None)
    else:
        await message.answer(f'Подписка на ИНН {inn} не найдена.', parse_mode=None)


@router.message(Command('check'))
async def cmd_check(message: Message):
    if not await _guard(message):
        return

    args = (message.text or '').split(maxsplit=1)
    if len(args) < 2:
        await message.answer('Использование: /check ИНН', parse_mode=None)
        return

    inn = args[1].strip()
    await _run_check(message.chat.id, inn)


@router.message(F.text == 'Проверить сейчас')
async def on_check_button(message: Message):
    if not await _guard(message):
        return

    watches = _db.get_user_watches(message.from_user.id)
    if not watches:
        await message.answer('У вас пока нет подписок.', parse_mode=None)
        return

    for watch in watches:
        await _run_check(message.chat.id, watch.inn)


@router.message(Command('schedule'))
@router.message(F.text == 'Расписание')
async def cmd_schedule(message: Message):
    if not await _guard(message):
        return
    await message.answer('Выберите частоту проверок:', reply_markup=schedule_menu(), parse_mode=None)


@router.message(F.text == 'Добавить ИНН')
async def on_add_inn(message: Message):
    if not await _guard(message):
        return
    await message.answer(
        'Отправьте команду: /watch ИНН [название]\n'
        'Например: /watch 7807234722 Литера-В',
        parse_mode=None,
    )


@router.callback_query(F.data.startswith('schedule:'))
async def on_schedule(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    schedule = callback.data.split(':', 1)[1]
    if _db.set_user_schedule(callback.from_user.id, schedule):
        label = SCHEDULE_LABELS.get(schedule, schedule)
        await callback.message.edit_text(f'Расписание обновлено: {label}')
    else:
        await callback.answer('Не удалось обновить', show_alert=True)


@router.callback_query(F.data.startswith('check:'))
async def on_check_callback(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    inn = callback.data.split(':', 1)[1]
    await callback.message.edit_text(f'Проверяю ИНН {inn}...')
    await _run_check(callback.message.chat.id, inn)


@router.callback_query(F.data.startswith('unwatch:'))
async def on_unwatch_callback(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    inn = callback.data.split(':', 1)[1]
    if _db.remove_watch(callback.from_user.id, inn):
        await callback.message.edit_text(f'Подписка на ИНН {inn} удалена.')
    else:
        await callback.answer('Не найдена', show_alert=True)


async def _run_check(chat_id: int, inn: str):
    if not _is_valid_inn(inn):
        await _send(chat_id, 'Неверный формат ИНН.')
        return

    try:
        await _send(chat_id, f'Проверяю ИНН {inn}...')

        await _parser.parse_inn(inn)
        latest = await _parser.get_latest(inn)
        company_name = _extract_company_name(latest)

        diff = await _parser.get_diff_latest(inn)
        if diff.get('changed'):
            text = formatting.format_diff_message(inn, diff, company_name)
        else:
            text = formatting.format_no_change_message(inn, company_name)

        await _send(chat_id, text)

    except ParserApiError as e:
        logger.error(f'Parser API error: {e.code} - {e.message}')
        await _send(chat_id, formatting.format_error_message(e.code, e.message))
    except Exception as e:
        logger.exception('Unexpected error while checking INN')
        await _send(chat_id, f'Внутренняя ошибка: {e}')


@router.message(Command('notify'))
@router.message(F.text == 'Уведомления')
async def cmd_notify(message: Message):
    if not await _guard(message):
        return

    enabled = _db.get_notify_on_no_change(message.from_user.id)

    await message.answer(
        'Уведомления о плановых проверках.\n\n'
        'По умолчанию бот молчит, если данные не изменились, '
        'и присылает сообщение только при обнаружении изменений.\n\n'
        'Если включить эту опцию, бот будет присылать сообщение '
        'после каждой плановой проверки, даже если изменений нет.',
        reply_markup=notifications_menu(enabled),
        parse_mode=None,
    )


@router.callback_query(F.data.startswith('notify_no_change:'))
async def on_notify_no_change(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    action = callback.data.split(':', 1)[1]
    enabled = (action == 'on')

    if _db.set_notify_on_no_change(callback.from_user.id, enabled):
        state = 'включено' if enabled else 'выключено'
        await callback.answer(f'Уведомления без изменений: {state}')

        new_menu = notifications_menu(enabled)
        try:
            await callback.message.edit_reply_markup(reply_markup=new_menu)
        except Exception:
            pass
    else:
        await callback.answer('Не удалось обновить', show_alert=True)


@router.callback_query(F.data == 'noop')
async def on_noop(callback: CallbackQuery):
    await callback.answer()