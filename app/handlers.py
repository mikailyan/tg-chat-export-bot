from io import BytesIO
from typing import List, Tuple

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile

from app.config import Settings
from app.states import UploadStates
from app.parsing.telegram_json import parse_telegram_export_json
from app.parsing.telegram_html import parse_telegram_export_html
from app.export.excel import build_excel

router = Router()

def kb_main():
    kb = InlineKeyboardBuilder()
    kb.button(text="Готово (обработать)", callback_data="process")
    kb.button(text="Сброс", callback_data="reset")
    kb.adjust(1)
    return kb.as_markup()

def detect_format(filename: str) -> str:
    fn = (filename or "").lower().strip()
    if fn.endswith(".json"):
        return "json"
    if fn.endswith(".html") or fn.endswith(".htm"):
        return "html"
    return "unknown"

@router.message(CommandStart())
async def start(message: Message, state: FSMContext, settings: Settings):
    await state.clear()
    await state.set_state(UploadStates.waiting_files)
    await state.update_data(files=[])
    text = (
        "Пришли файлы экспорта истории чата Telegram (JSON или HTML).\n"
        f"Можно отправить до {settings.max_files} файлов.\n\n"
        "Когда закончишь — нажми «Готово (обработать)».\n"
        "Важно: бот обрабатывает файлы на лету и не хранит их."
    )
    await message.answer(text, reply_markup=kb_main())

@router.message(UploadStates.waiting_files, F.document)
async def on_document(message: Message, state: FSMContext, bot: Bot, settings: Settings):
    data = await state.get_data()
    files: List[Tuple[str, str]] = data.get("files", [])

    if len(files) >= settings.max_files:
        await message.answer(f"Лимит: не более {settings.max_files} файлов. Нажми «Готово» или «Сброс».", reply_markup=kb_main())
        return

    doc = message.document
    if doc.file_size and doc.file_size > settings.max_file_size:
        await message.answer("Файл слишком большой для обработки в текущих лимитах. Экспортируй меньший диапазон сообщений.")
        return

    fmt = detect_format(doc.file_name or "")
    if fmt == "unknown":
        await message.answer("Не понимаю формат. Пришли .json или .html файл экспорта Telegram.")
        return

    files.append((doc.file_id, fmt))
    await state.update_data(files=files)

    await message.answer(f"Файл принят ({len(files)}/{settings.max_files}). Можешь отправить ещё или нажать «Готово».", reply_markup=kb_main())

@router.callback_query(F.data == "reset")
async def reset(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(UploadStates.waiting_files)
    await state.update_data(files=[])
    await call.message.edit_text("Сбросил. Пришли файлы заново (JSON/HTML), затем нажми «Готово».", reply_markup=kb_main())
    await call.answer()

@router.callback_query(F.data == "process")
async def process(call: CallbackQuery, state: FSMContext, bot: Bot, settings: Settings):
    data = await state.get_data()
    files: List[Tuple[str, str]] = data.get("files", [])

    if not files:
        await call.answer("Сначала пришли хотя бы один файл.", show_alert=True)
        return

    await call.message.edit_text("Обрабатываю файлы…")

    all_participants = []
    all_mentions = []
    total_messages = 0

    for file_id, fmt in files:
        buf = BytesIO()
        raw = b""

        try:
            tg_file = await bot.get_file(file_id)
            await bot.download_file(tg_file.file_path, destination=buf)
            raw = buf.getvalue()

        except TelegramBadRequest as e:
            if "file is too big" in str(e).lower():
                await call.message.answer(
                    "❌ Файл слишком большой, бот не может его скачать через Telegram Bot API.\n\n"
                    "Что сделать:\n"
                    "1) Экспортируй чат заново в **JSON**\n"
                    "2) Выключи медиа (фото/видео/файлы)\n"
                    "3) Выбери меньший диапазон сообщений (например последние 1–2 недели)\n\n"
                    "После этого пришли файл(ы) снова и нажми «Готово»."
                )
                await call.answer()
                await state.clear()
                await state.set_state(UploadStates.waiting_files)
                await state.update_data(files=[])
                return
            raise

        except Exception:
            await call.message.answer(
                "❌ Не удалось скачать/прочитать один из файлов экспорта.\n"
                "Попробуй экспортировать заново (лучше JSON) и отправить снова."
            )
            await call.answer()
            await state.clear()
            await state.set_state(UploadStates.waiting_files)
            await state.update_data(files=[])
            return

        finally:
            buf.close()

        try:
            if fmt == "json":
                res = parse_telegram_export_json(raw)
            else:
                res = parse_telegram_export_html(raw)

        except Exception:
            await call.message.answer(
                "❌ Не смог распарсить файл экспорта.\n\n"
                "Проверь, что это стандартный экспорт Telegram Desktop и формат JSON/HTML.\n"
                "Если файл очень большой — сделай экспорт меньшего диапазона."
            )
            await call.answer()
            await state.clear()
            await state.set_state(UploadStates.waiting_files)
            await state.update_data(files=[])
            return

        all_participants.extend(res.participants)
        all_mentions.extend(res.mentions)
        total_messages += res.total_messages

        raw = b""

    merged = {}
    for p in all_participants:
        if p.user_id:
            key = f"id:{p.user_id}"
        elif p.username:
            key = f"u:{p.username.lower()}"
        else:
            key = f"n:{(p.full_name or '').lower()}"
        merged.setdefault(key, p)

    participants = list(merged.values())

    mentions_map = {}
    for m in all_mentions:
        mentions_map.setdefault(m.lower(), m)
    mentions = list(mentions_map.values())

    if len(participants) < settings.inline_limit:
        lines = []
        for p in sorted(participants, key=lambda x: (x.username or "", x.full_name or "")):
            lines.append(f"@{p.username}" if p.username else p.full_name)

        text = "Участники (по авторам сообщений):\n" + "\n".join(lines)
        await call.message.answer(text)
    else:
        xlsx_io = build_excel(participants, mentions)
        xlsx_bytes = xlsx_io.getvalue()
        xlsx_io.close()
    
        doc = BufferedInputFile(xlsx_bytes, filename="participants.xlsx")
    
        try:
            await call.message.answer_document(
                document=doc,
                caption=f"Участников: {len(participants)}. Сообщений просмотрено: {total_messages}."
            )
        except TelegramBadRequest as e:
            if "file is too big" in str(e).lower():
                await call.message.answer(
                    "Excel получился слишком большим для отправки через Telegram.\n"
                    "Попробуй экспортировать меньший диапазон сообщений."
                )
            else:
                raise

    await state.clear()
    await state.set_state(UploadStates.waiting_files)
    await state.update_data(files=[])

    await call.message.answer("Готово. Можешь прислать новую историю чата.", reply_markup=kb_main())
    await call.answer()
