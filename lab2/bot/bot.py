import asyncio
import logging
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("stage1-sqlite-bot")

DB_PATH = Path("feedback.db")

# Набор file_id стикеров из указанных стикерпаков.
# Важно: в реальном проекте teacher может обновить этот список актуальными file_id.
STICKER_FILE_IDS = [
    # Praysmilelove (примерные ID, рекомендуется заменить на реальные)
    "CAACAgIAAxkBAAEFJQ5mX2u0ExampleStickerId1",
    # PopCatAnimated
    "CAACAgIAAxkBAAEFJRBmX2u0ExampleStickerId2",
    # Kotyakot
    "CAACAgIAAxkBAAEFJRJmX2u0ExampleStickerId3",
]

# Небольшие "факты" для кнопки Fact после сохранения отзыва.
FACTS = [
    "Fun fact: English has a word with no rhymes — “orange” (mostly)! 🍊",
    "Fun fact: The most common letter in English is “E”.",
    "Fun fact: “I am” is the shortest complete sentence in English.",
    "Fun fact: The dot over “i” and “j” is called a tittle.",
]


def utc_now_iso() -> str:
    """Возвращает время в ISO-формате (UTC) для хранения в SQLite."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Config:
    bot_token: str
    teacher_telegram_id: int


def get_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    teacher_id_raw = os.getenv("TEACHER_TELEGRAM_ID", "").strip()
    if not token:
        raise ValueError("BOT_TOKEN is not set. Put it into .env (see .env.example).")
    if not teacher_id_raw.isdigit():
        raise ValueError("TEACHER_TELEGRAM_ID is not set (must be a number). Put it into .env.")
    return Config(bot_token=token, teacher_telegram_id=int(teacher_id_raw))


async def init_db() -> None:
    """
    Инициализация схемы SQLite.

    Требования:
    - users таблица
    - reviews таблица
    """
    DB_PATH.touch(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys=ON;")

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                username TEXT UNIQUE,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
                created_at TEXT NOT NULL
            );
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                teacher_id INTEGER NOT NULL,
                lesson_date TEXT NOT NULL,
                rating INTEGER,
                useful INTEGER,
                difficult INTEGER,
                repeat INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )

        # Миграция для Этапа 3: добавляем текстовые поля для отзывов.
        # Старые колонки useful/difficult/repeat (INTEGER) оставляем для совместимости,
        # но новые данные пишем в useful_text/difficult_text/repeat_next.
        async with db.execute("PRAGMA table_info(reviews);") as cur:
            cols = {row[1] for row in await cur.fetchall()}  # row[1] = name

        if "useful_text" not in cols:
            await db.execute("ALTER TABLE reviews ADD COLUMN useful_text TEXT;")
        if "difficult_text" not in cols:
            await db.execute("ALTER TABLE reviews ADD COLUMN difficult_text TEXT;")
        if "repeat_next" not in cols:
            await db.execute("ALTER TABLE reviews ADD COLUMN repeat_next TEXT;")

        await db.commit()


def escape_markdown(text: str) -> str:
    """
    Минимальное экранирование для Markdown (не MarkdownV2).
    Нужно, чтобы имена/username не ломали форматирование.
    """
    if text is None:
        return ""
    return (
        text.replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


async def get_user_by_telegram_id(db: aiosqlite.Connection, telegram_id: int) -> Optional[dict]:
    async with db.execute(
        "SELECT id, telegram_id, username, full_name, role, created_at FROM users WHERE telegram_id=?;",
        (telegram_id,),
    ) as cur:
        row = await cur.fetchone()
        if not row:
            return None
        keys = ["id", "telegram_id", "username", "full_name", "role", "created_at"]
        return dict(zip(keys, row))


async def get_user_by_username(db: aiosqlite.Connection, username: str) -> Optional[dict]:
    """
    Ищет пользователя по username (без @).
    """
    normalized = username.lower()
    async with db.execute(
        "SELECT id, telegram_id, username, full_name, role, created_at FROM users WHERE lower(username)=?;",
        (normalized,),
    ) as cur:
        row = await cur.fetchone()
        if not row:
            return None
        keys = ["id", "telegram_id", "username", "full_name", "role", "created_at"]
        return dict(zip(keys, row))


async def upsert_user(
    db: aiosqlite.Connection,
    *,
    telegram_id: int,
    username: Optional[str],
    full_name: str,
    role: str,
) -> dict:
    """
    Создаёт пользователя в таблице `users` (если нет) или обновляет поля.
    """
    normalized_username = username.lower() if username else None

    existing = await get_user_by_telegram_id(db, telegram_id)
    if existing:
        await db.execute(
            """
            UPDATE users
            SET username=?, full_name=?, role=?
            WHERE telegram_id=?;
            """,
            (normalized_username, full_name, role, telegram_id),
        )
        await db.commit()
        existing["username"] = normalized_username
        existing["full_name"] = full_name
        existing["role"] = role
        return existing

    await db.execute(
        """
        INSERT INTO users (telegram_id, username, full_name, role, created_at)
        VALUES (?, ?, ?, ?, ?);
        """,
        (telegram_id, normalized_username, full_name, role, utc_now_iso()),
    )
    await db.commit()

    # Возвращаем созданную запись
    created = await get_user_by_telegram_id(db, telegram_id)
    if not created:
        raise RuntimeError("User insert failed unexpectedly.")
    return created


def parse_feedback_username(text: str) -> str:
    """
    Парсит аргумент команды /feedback @username.
    """
    pattern = r"^/feedback\s+(@?[A-Za-z0-9_]{5,})\s*$"
    match = re.match(pattern, text.strip())
    if not match:
        raise ValueError("Invalid format. Use: /feedback @username")
    raw_username = match.group(1)
    if raw_username.startswith("@"):
        raw_username = raw_username[1:]
    return raw_username


router = Router()
config_ref: Optional[Config] = None


class FeedbackFSM(StatesGroup):
    """
    Состояния пошагового опроса ученика.
    На этапе 2 мы собираем ответы, но пока не сохраняем их в БД —
    только сам факт начала опроса хранится в таблице reviews.
    """

    waiting_rating = State()
    waiting_useful = State()
    waiting_difficult = State()
    waiting_repeat = State()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """
    /start — регистрация и приветствие.

    Новая логика:
    - любой пользователь, который пишет /start, регистрируется как student (если его ещё нет в БД);
    - teacher определяется по TEACHER_TELEGRAM_ID.
    """
    assert message.from_user is not None
    telegram_id = message.from_user.id
    username = message.from_user.username  # может быть None
    full_name = " ".join(
        part for part in [message.from_user.first_name, message.from_user.last_name] if part
    ).strip()

    if not full_name:
        full_name = message.from_user.first_name or "User"

    try:
        if not config_ref:
            raise RuntimeError("Config is not initialized.")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys=ON;")

            existing = await get_user_by_telegram_id(db, telegram_id)
            role = "teacher" if telegram_id == config_ref.teacher_telegram_id else "student"

            # Если пользователя нет — создаём.
            # Если есть — обновляем username/full_name (и роль, если это teacher).
            user = await upsert_user(
                db,
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                role=role,
            )

        if role == "student" and (existing is None):
            logger.info(
                "[REGISTRATION] New student @%s (id=%s) has been added",
                user["username"] or "unknown",
                telegram_id,
            )

        if role == "teacher":
            await message.answer(
                "👋 Welcome, Teacher!\n\n"
                "Use /students to see all registered students.\n"
                "Use /feedback @username to send the feedback survey.\n\n"
                "Let’s make learning progress together! 💪",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer(
                f"👋 Welcome, Student, {full_name}!\n\n"
                "✅ You have been added to the system.\n"
                "The teacher will request your feedback using /feedback @username.\n"
                "Hang tight — you’ve got this! 🌟",
                parse_mode=ParseMode.HTML,
            )
    except Exception as exc:
        logger.exception("cmd_start failed: %r", exc)
        await message.answer("Sorry, something went wrong. Please try again later.")

@router.message(Command("students"))
async def cmd_students(message: Message) -> None:
    """
    /students — показывает список всех зарегистрированных учеников (teacher only).
    """
    assert message.from_user is not None
    if not config_ref:
        await message.answer("Sorry, bot is not configured yet.")
        return
    if message.from_user.id != config_ref.teacher_telegram_id:
        await message.answer("Access denied. Only the teacher can view the students list.")
        return

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            async with db.execute(
                """
                SELECT full_name, username, created_at
                FROM users
                WHERE role='student'
                ORDER BY datetime(created_at) ASC;
                """
            ) as cur:
                rows = await cur.fetchall()

        if not rows:
            await message.answer("No students registered yet.")
            return

        lines = ["👥 Registered students:\n"]
        for full_name, username, created_at in rows:
            uname = f"@{username}" if username else "(no username)"
            # created_at хранится в ISO UTC, показываем как есть (можно улучшить позже).
            lines.append(f"• {full_name}\n  {uname}\n  Registered: {created_at}")

        await message.answer("\n\n".join(lines))
    except Exception as exc:
        logger.exception("cmd_students failed: %r", exc)
        await message.answer("Sorry, something went wrong while loading students.")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    """
    /stats — сводная статистика по отзывам (teacher only).

    Требования:
    - список учеников с количеством отзывов и средней оценкой
    - общая средняя оценка
    - последние 5 отзывов за неделю
    - вывод в Markdown
    """
    assert message.from_user is not None
    if not config_ref:
        await message.answer("Sorry, bot is not configured yet.")
        return
    if message.from_user.id != config_ref.teacher_telegram_id:
        await message.answer("Access denied. Only the teacher can view stats.")
        return

    now = datetime.now(timezone.utc)
    week_ago = (now.timestamp() - 7 * 24 * 60 * 60)
    week_ago_iso = datetime.fromtimestamp(week_ago, tz=timezone.utc).isoformat()

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys=ON;")

            # 1) По каждому ученику: количество отзывов и средняя оценка
            async with db.execute(
                """
                SELECT u.full_name, u.username,
                       COUNT(r.id) AS reviews_count,
                       AVG(r.rating) AS avg_rating
                FROM users u
                LEFT JOIN reviews r ON r.student_id = u.id
                WHERE u.role='student'
                GROUP BY u.id
                ORDER BY reviews_count DESC, u.full_name ASC;
                """
            ) as cur:
                per_student = await cur.fetchall()

            # 2) Общая средняя оценка
            async with db.execute("SELECT AVG(rating) FROM reviews WHERE rating IS NOT NULL;") as cur:
                row = await cur.fetchone()
                overall_avg = row[0] if row else None

            # 3) Последние 5 отзывов за неделю
            async with db.execute(
                """
                SELECT u.full_name, u.username, r.lesson_date, r.rating, r.created_at
                FROM reviews r
                JOIN users u ON u.id = r.student_id
                WHERE r.created_at >= ?
                ORDER BY datetime(r.created_at) DESC
                LIMIT 5;
                """,
                (week_ago_iso,),
            ) as cur:
                last_week = await cur.fetchall()

        lines = ["📊 *Stats*"]

        if not per_student:
            lines.append("\nNo students registered yet.")
            await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
            return

        lines.append("\n*Students:*")
        for full_name, username, reviews_count, avg_rating in per_student:
            safe_name = escape_markdown(full_name)
            safe_username = escape_markdown(username or "")
            uname = f"@{safe_username}" if safe_username else "(no username)"

            count = int(reviews_count or 0)
            if avg_rating is None:
                stars = "—"
            else:
                stars = "⭐" * max(1, min(5, int(round(float(avg_rating)))))
            lines.append(f"• *{safe_name}* ({uname}) — {count} reviews, avg: {stars}")

        if overall_avg is None:
            lines.append("\n*Overall average:* —")
        else:
            overall_stars = "⭐" * max(1, min(5, int(round(float(overall_avg)))))
            lines.append(f"\n*Overall average:* {overall_stars}")

        lines.append("\n*Last 5 reviews (last 7 days):*")
        if not last_week:
            lines.append("• No reviews in the last 7 days.")
        else:
            for full_name, username, lesson_date, rating, created_at in last_week:
                safe_name = escape_markdown(full_name)
                safe_username = escape_markdown(username or "")
                uname = f"@{safe_username}" if safe_username else "(no username)"
                stars = "⭐" * max(1, min(5, int(rating or 0))) if rating else "—"
                lines.append(f"• {safe_name} ({uname}) — {stars}, lesson: {lesson_date}, saved: {created_at}")

        await message.answer("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:
        logger.exception("cmd_stats failed: %r", exc)
        await message.answer("Sorry, something went wrong while building stats.")


@router.message(Command("feedback"))
async def cmd_feedback(message: Message) -> None:
    """
    /feedback @username — запускает опрос ученика.

    Этап 2:
    - Teacher вызывает команду;
    - находит ученика по username;
    - создаёт "пустую" запись в reviews (только связи и дата урока);
    - отправляет ученику random sticker + опрос (FSM);
    - teacher получает подтверждение "Feedback sent to @username".
    """
    assert message.from_user is not None
    telegram_id = message.from_user.id

    try:
        username = parse_feedback_username(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    try:
        if not config_ref:
            raise RuntimeError("Config is not initialized.")
        if telegram_id != config_ref.teacher_telegram_id:
            await message.answer("Access denied. Only the teacher can request feedback.")
            return

        logger.info("[FEEDBACK] Teacher requested feedback for @%s", username.lower())

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            teacher = await get_user_by_telegram_id(db, telegram_id)
            if not teacher:
                # Если teacher ещё не делал /start, добавим его в users (role teacher).
                # Это гарантирует корректные связи teacher_id в reviews.
                teacher_user = message.from_user
                teacher_full_name = " ".join(
                    part for part in [teacher_user.first_name, teacher_user.last_name] if part
                ).strip() or (teacher_user.first_name or "Teacher")
                teacher = await upsert_user(
                    db,
                    telegram_id=telegram_id,
                    username=teacher_user.username,
                    full_name=teacher_full_name,
                    role="teacher",
                )

            student = await get_user_by_username(db, username)
            if not student or student["role"] != "student":
                await message.answer(
                    f"❌ @{username} has not started the bot yet. "
                    "Ask the student to send /start to this bot first."
                )
                return

            # Создаём запись в reviews: пока только связь и дата урока.
            lesson_date = datetime.now(timezone.utc).date().isoformat()
            cur = await db.execute(
                """
                INSERT INTO reviews (student_id, teacher_id, lesson_date, rating, useful, difficult, repeat, created_at)
                VALUES (?, ?, ?, NULL, NULL, NULL, NULL, ?);
                """,
                (student["id"], teacher["id"], lesson_date, utc_now_iso()),
            )
            await db.commit()
            review_id = cur.lastrowid

        logger.info(
            "[FEEDBACK] Survey started for @%s (review_id=%s)",
            student["username"] or username.lower(),
            review_id,
        )

        # Пытаемся отправить random sticker ученику.
        sticker_id = random.choice(STICKER_FILE_IDS)
        try:
            await message.bot.send_sticker(chat_id=student["telegram_id"], sticker=sticker_id)
            logger.info("[SEND] Sticker sent to @%s successfully", student["username"] or username.lower())
        except Exception as exc:
            # Если стикер не отправился (например, неверный file_id) — не падаем.
            logger.warning("Failed to send sticker to student %s: %r", student["telegram_id"], exc)
            await message.bot.send_message(
                chat_id=student["telegram_id"],
                text="🎁 Imagine a cute motivational sticker here! (sticker sending failed, but feedback still works)",
            )

        # Отправляем первый вопрос ученику с inline-кнопками 1–5 звёздочек.
        stars_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⭐", callback_data=f"feedback_rate:{review_id}:1"),
                    InlineKeyboardButton(text="⭐⭐", callback_data=f"feedback_rate:{review_id}:2"),
                    InlineKeyboardButton(text="⭐⭐⭐", callback_data=f"feedback_rate:{review_id}:3"),
                    InlineKeyboardButton(text="⭐⭐⭐⭐", callback_data=f"feedback_rate:{review_id}:4"),
                    InlineKeyboardButton(text="⭐⭐⭐⭐⭐", callback_data=f"feedback_rate:{review_id}:5"),
                ]
            ]
        )
        await message.bot.send_message(
            chat_id=student["telegram_id"],
            text="Question 1/4: How was the lesson? Please choose a rating:",
            reply_markup=stars_kb,
        )

        # Teacher получает подтверждение.
        await message.answer(f"✅ Feedback sent to @{username.lower()}")
    except Exception as exc:
        logger.exception("cmd_feedback failed: %r", exc)
        await message.answer("Sorry, something went wrong while sending feedback.")


@router.callback_query(F.data.startswith("feedback_rate:"))
async def feedback_rate_callback(query: CallbackQuery, state: FSMContext) -> None:
    """
    Обработка выбора рейтинга (1–5 звёздочек) учеником.
    """
    try:
        _, review_id_str, rating_str = (query.data or "").split(":", maxsplit=2)
        review_id = int(review_id_str)
        rating = int(rating_str)
    except Exception:
        await query.answer()
        return

    await query.answer()

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            # Обновляем только rating — остальные ответы добавим на следующих этапах.
            await db.execute("UPDATE reviews SET rating=? WHERE id=?;", (rating, review_id))
            await db.commit()
    except Exception as exc:
        logger.exception("Failed to update rating in reviews: %r", exc)

    logger.info("[FEEDBACK] Student answered Q1 (rating=%s) review_id=%s", rating, review_id)

    # Сохраняем review_id в FSM состояния ученика.
    await state.set_state(FeedbackFSM.waiting_useful)
    await state.update_data(review_id=review_id, rating=rating)

    # Переходим к вопросу 2.
    await query.message.edit_text(
        "Question 2/4:\nWhat was the most useful thing during this lesson?\n\n"
        "Please answer in a few words. 💬",
    )


@router.callback_query(F.data == "fact")
async def fact_callback(query: CallbackQuery) -> None:
    """
    Кнопка Fact после успешного сохранения отзыва.
    """
    await query.answer()
    fact = random.choice(FACTS)
    try:
        await query.message.edit_text(fact)
    except Exception:
        await query.message.answer(fact)


@router.message(FeedbackFSM.waiting_useful)
async def feedback_useful(message: Message, state: FSMContext) -> None:
    """
    Вопрос 2: что было самым полезным.
    На этапе 2 сохраняем ответ только в FSM (можно будет добавить запись в БД на следующем этапе).
    """
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please write at least a few words 🙂")
        return

    await state.update_data(useful=text)
    data = await state.get_data()
    logger.info("[FEEDBACK] Student answered Q2 (useful) review_id=%s", data.get("review_id"))
    await state.set_state(FeedbackFSM.waiting_difficult)
    await message.answer(
        "Question 3/4:\nWhat was difficult for you?\n\n"
        "You can write anything that felt challenging.",
    )


@router.message(FeedbackFSM.waiting_difficult)
async def feedback_difficult(message: Message, state: FSMContext) -> None:
    """
    Вопрос 3: что было сложным.
    """
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please write at least a few words 🙂")
        return

    await state.update_data(difficult=text)
    data = await state.get_data()
    logger.info("[FEEDBACK] Student answered Q3 (difficult) review_id=%s", data.get("review_id"))
    await state.set_state(FeedbackFSM.waiting_repeat)
    await message.answer(
        "Question 4/4:\nWhat would you like to repeat next time?\n\n"
        "This helps the teacher plan the next lesson for you 💡",
    )


@router.message(FeedbackFSM.waiting_repeat)
async def feedback_repeat(message: Message, state: FSMContext) -> None:
    """
    Вопрос 4: что ученик хочет повторить.
    """
    text = (message.text or "").strip()
    if not text:
        await message.answer("Please write at least a few words 🙂")
        return

    data = await state.get_data()
    review_id = data.get("review_id")
    rating = data.get("rating")
    useful = data.get("useful")
    difficult = data.get("difficult")

    logger.info("[FEEDBACK] Student answered Q4 (repeat_next) review_id=%s", review_id)

    # Этап 3: сохраняем полный отзыв в SQLite.
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            await db.execute(
                """
                UPDATE reviews
                SET useful_text=?, difficult_text=?, repeat_next=?
                WHERE id=?;
                """,
                (useful, difficult, text, int(review_id)),
            )
            await db.commit()
        logger.info("[FEEDBACK] Review saved successfully (review_id=%s, rating=%s)", review_id, rating)
    except Exception as exc:
        logger.exception("Failed to save review text answers: %r", exc)

    await state.clear()

    fact_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Fact", callback_data="fact")]]
    )
    await message.answer(
        "Thank you so much for your feedback! 💙\n"
        "Your answers will help make the next lesson even better.\n\n"
        "Want a quick fun fact?",
        reply_markup=fact_kb,
    )


async def main() -> None:
    global config_ref
    config = get_config()
    config_ref = config
    await init_db()

    bot = Bot(token=config.bot_token)
    # Используем память для FSM-хранилища состояний.
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")

