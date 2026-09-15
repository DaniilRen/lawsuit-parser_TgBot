import hashlib
import json
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from src.config import Config
from src.database.db_manager import BotDatabase
from src.api_client.parser_client import ParserClient, ParserApiError
from src.bot import formatting
from src.bot.keyboards import main_menu, watch_actions, schedule_menu
from src.utils.logger import setup_logger


router = Router()
logger = setup_logger()

_db: Optional[BotDatabase] = None
_parser: Optional[ParserClient] = None


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
        'Добавьте ИНН через «Добавить ИНН», и я буду проверять его '
        'по расписанию и сообщать об изменениях.',
        reply_markup=main_menu(),
    )


@router.message(Command('help'))
@router.message(F.text == 'Помощь')
async def cmd_help(message: Message):
    if not await _guard(message):
        return
    await message.answer(
        'Доступные команды:\n\n'
        '/start — начать\n'
        '/watch <ИНН> [название] — добавить подписку\n'
        '/unwatch <ИНН> — удалить подписку\n'
        '/list — список моих подписок\n'
        '/check <ИНН> — проверить сейчас\n'
        '/schedule — изменить расписание\n'
        '/help — эта справка'
    )


@router.message(Command('list'))
@router.message(F.text == 'Мои подписки')
async def cmd_list(message: Message):
    if not await _guard(message):
        return

    watches = _db.get_user_watches(message.from_user.id)
    if not watches:
        await message.answer('У вас пока нет подписок.')
        return

    for watch in watches:
        label = f'{watch.label}\n' if watch.label else ''
        text = f'{label}ИНН: {watch.inn}'
        await message.answer(text, reply_markup=watch_actions(watch.inn))


@router.message(Command('watch'))
async def cmd_watch(message: Message):
    if not await _guard(message):
        return

    args = (message.text or '').split(maxsplit=2)
    if len(args) < 2:
        await message.answer('Использование: /watch <ИНН> [название]')
        return

    inn = args[1].strip()
    label = args[2].strip() if len(args) > 2 else None

    if not _is_valid_inn(inn):
        await message.answer('Неверный формат ИНН. Ожидается 10 или 12 цифр.')
        return

    _db.add_watch(message.from_user.id, inn, label)
    await message.answer(f'Подписка на ИНН {inn} добавлена.')


@router.message(Command('unwatch'))
async def cmd_unwatch(message: Message):
    if not await _guard(message):
        return

    args = (message.text or '').split(maxsplit=1)
    if len(args) < 2:
        await message.answer('Использование: /unwatch <ИНН>')
        return

    inn = args[1].strip()
    if _db.remove_watch(message.from_user.id, inn):
        await message.answer(f'Подписка на ИНН {inn} удалена.')
    else:
        await message.answer(f'Подписка на ИНН {inn} не найдена.')


@router.message(Command('check'))
@router.message(F.text == 'Проверить сейчас')
async def cmd_check(message: Message):
    if not await _guard(message):
        return

    args = (message.text or '').split(maxsplit=1)
    if len(args) < 2:
        await message.answer('Использование: /check <ИНН>')
        return

    inn = args[1].strip()
    await _run_check(message.chat.id, inn, message)


@router.message(Command('schedule'))
@router.message(F.text == 'Расписание')
async def cmd_schedule(message: Message):
    if not await _guard(message):
        return
    await message.answer('Выберите частоту проверок:', reply_markup=schedule_menu())


@router.callback_query(F.data.startswith('schedule:'))
async def on_schedule(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    schedule = callback.data.split(':', 1)[1]
    if _db.set_user_schedule(callback.from_user.id, schedule):
        labels = {'daily': 'ежедневно', 'weekly': 'еженедельно', 'monthly': 'ежемесячно'}
        await callback.message.edit_text(f'Расписание обновлено: {labels[schedule]}')
    else:
        await callback.answer('Не удалось обновить', show_alert=True)


@router.callback_query(F.data.startswith('check:'))
async def on_check_callback(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    inn = callback.data.split(':', 1)[1]
    await callback.message.edit_text(f'Проверяю ИНН {inn}...')
    await _run_check(callback.message.chat.id, inn, callback.message)


@router.callback_query(F.data.startswith('unwatch:'))
async def on_unwatch_callback(callback: CallbackQuery):
    if not await _guard_callback(callback):
        return

    inn = callback.data.split(':', 1)[1]
    if _db.remove_watch(callback.from_user.id, inn):
        await callback.message.edit_text(f'Подписка на ИНН {inn} удалена.')
    else:
        await callback.answer('Не найдена', show_alert=True)


@router.message(F.text == 'Добавить ИНН')
async def on_add_inn(message: Message):
    if not await _guard(message):
        return
    await message.answer('Отправьте команду: /watch <ИНН> [название]')


async def _run_check(chat_id: int, inn: str, reply_to: Message = None):
    if not _is_valid_inn(inn):
        await _parser_send(chat_id, 'Неверный формат ИНН.')
        return

    try:
        await _parser_send(chat_id, f'Проверяю ИНН {inn}...')
        parse_result = await _parser.parse_inn(inn)
        latest = await _parser.get_latest(inn)
        company_name = _extract_company_name(latest)

        diff = await _parser.get_diff_latest(inn)
        if diff.get('changed'):
            text = formatting.format_diff_message(inn, diff, company_name)
            await _parser_send(chat_id, text)
        else:
            text = formatting.format_no_change_message(inn, company_name)
            await _parser_send(chat_id, text)

    except ParserApiError as e:
        logger.error(f'Parser API error: {e.code} - {e.message}')
        await _parser_send(chat_id, formatting.format_error_message(e.code, e.message))
    except Exception as e:
        logger.exception('Unexpected error while checking INN')
        await _parser_send(chat_id, f'Внутренняя ошибка: {e}')


async def _parser_send(chat_id: int, text: str):
    from src.bot.app import get_bot
    bot = get_bot()
    await bot.send_message(chat_id=chat_id, text=text)