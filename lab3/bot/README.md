# Telegram Bot (aiogram 3.x) — SQLite Feedback (Stage 1)

This project is a simplified Telegram bot (aiogram 3.x + FSM-ready structure) that stores data in SQLite (`feedback.db`).
All bot messages are **in English** as required.

## Files

- `bot.py` — bot code
- `requirements.txt` — dependencies
- `.env.example` — environment variables template
- `README.md` — instructions

## Setup

1. Install Python 3.10+.
2. Create virtual environment and activate it.

```bash
python -m venv .venv
.venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create `.env` from `.env.example`:

```bash
copy .env.example .env
```

5. Put your bot token into `.env`:

```env
BOT_TOKEN=your_telegram_bot_token_here
```

6. Run:

```bash
python bot.py
```

## Commands (Teacher / Admin)

- `/start` — registers the user (student by default) and greets based on role
- `/students` — list all registered students (teacher only)
- `/feedback @username` — sends the feedback survey to a student (teacher only)

## Этап 1 — Что сделано

1. Добавлена SQLite база данных `feedback.db` и создана схема:
   - `users` (teacher/student roles)
   - `reviews` (таблица подготовки под будущие оценки)
2. Реализованы команды:
   - `/start`: авто-регистрация пользователя в `users` как `student` (если это не teacher)
   - `/students`: просмотр списка всех зарегистрированных учеников (teacher only)
   - `/feedback @username`: работает только для учеников, которые уже написали боту `/start`
3. Teacher определяется по `TEACHER_TELEGRAM_ID` в `.env`. Подключение к SQLite сделано через `aiosqlite`, конфигурация берётся через `python-dotenv`.

## Этап 2 — Что сделано

1. Команда `/feedback @username` теперь:
   - находит ученика по username в таблице `users`;
   - создаёт запись в таблице `reviews` (student_id, teacher_id, lesson_date, created_at; поля ответов пока `NULL`);
   - отправляет ученику random sticker (с обработкой ошибок) и запускает опрос из 4 вопросов.
2. Опрос реализован через FSM (`FeedbackFSM`) для ученика:
   - Q1: "How was the lesson?" — inline-кнопки со звёздочками 1–5 (rating сохраняется в `reviews.rating`);
   - Q2: "What was the most useful thing?" — текстовый ответ;
   - Q3: "What was difficult?" — текстовый ответ;
   - Q4: "What do you want to repeat next time?" — текстовый ответ.
3. По завершении опроса бот благодарит ученика, а teacher сразу после вызова `/feedback` получает подтверждение `"✅ Feedback sent to @username"`.

## Этап 3 — Что сделано

1. Добавлена миграция схемы `reviews`:
   - добавлены текстовые поля `useful_text`, `difficult_text`, `repeat_next` (для сохранения ответов ученика).
2. После завершения опроса бот сохраняет полный отзыв в SQLite:
   - `rating` (Q1) сохраняется сразу после нажатия на звёздочки,
   - `useful_text`, `difficult_text`, `repeat_next` сохраняются после Q4.
3. Добавлена команда `/stats` (только teacher):
   - список учеников с количеством отзывов и средней оценкой,
   - общая средняя оценка,
   - последние 5 отзывов за последние 7 дней.
4. После успешного завершения отзыва ученик получает кнопку **Fact**.
