from typing import Any, Dict, List


SOURCE_LABELS = {
    'nalog': 'ФНС (Прозрачный бизнес)',
    'egrul': 'ЕГРЮЛ',
    'ras': 'Арбитражные суды',
}


FIELD_LABELS = {
    'company_name': 'Название компании',
    'full_name': 'Полное наименование',
    'short_name': 'Сокращённое наименование',
    'ogrn': 'ОГРН',
    'kpp': 'КПП',
    'registration_date': 'Дата регистрации',
    'legal_address': 'Юридический адрес',
    'status': 'Статус',
    'main_activity': 'Основной вид деятельности',
    'tax_office': 'Налоговый орган',
    'authorized_capital': 'Уставный капитал',
    'director.name': 'Руководитель',
    'director.position': 'Должность руководителя',
    'has_invalid_info': 'Недостоверные сведения',
    'has_tax_debts': 'Налоговые задолженности',
    'has_tax_offenses': 'Налоговые правонарушения',
    'has_court_cases': 'Судебные дела',
    'cases_count': 'Количество судебных дел',
}


def humanize_field(field: str) -> str:
    if field in FIELD_LABELS:
        return FIELD_LABELS[field]

    last = field.split('.')[-1]
    if last in FIELD_LABELS:
        return FIELD_LABELS[last]

    if ' | ' in field:
        panel, sub = field.split(' | ', 1)
        return f'{panel}: {sub}'

    return field


def _format_value(value: Any) -> str:
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'Да' if value else 'Нет'
    if isinstance(value, (list, dict)):
        return str(value)
    text = str(value)
    if len(text) > 300:
        text = text[:297] + '...'
    return text


def format_diff_message(inn: str, diff: Dict[str, Any], company_name: str = None) -> str:
    lines: List[str] = []

    header = f'Изменения по ИНН {inn}'
    if company_name:
        header = f'{company_name}\n(ИНН {inn})'
    lines.append(header)
    lines.append('')

    for source, details in diff.get('sources', {}).items():
        if not details.get('changed'):
            continue

        source_label = SOURCE_LABELS.get(source, source)
        lines.append(f'Источник: {source_label}')

        for change in details.get('fields', []):
            field = change.get('field', '')
            ctype = change.get('type', 'changed')

            label = humanize_field(field)

            if ctype == 'changed':
                old = _format_value(change.get('from'))
                new = _format_value(change.get('to'))
                lines.append(f'  • {label}:')
                lines.append(f'      было: {old}')
                lines.append(f'      стало: {new}')
            elif ctype == 'added':
                new = _format_value(change.get('to'))
                lines.append(f'  • {label} (появилось): {new}')
            elif ctype == 'removed':
                old = _format_value(change.get('from'))
                lines.append(f'  • {label} (пропало): {old}')

        lines.append('')

    return '\n'.join(lines).strip()


def format_no_change_message(inn: str, company_name: str = None) -> str:
    name = f'{company_name} ' if company_name else ''
    return f'{name}(ИНН {inn}): изменений не обнаружено.'


def format_error_message(error_code: str, message: str) -> str:
    return f'Ошибка при обработке запроса:\n{message}\n\nКод: {error_code}'