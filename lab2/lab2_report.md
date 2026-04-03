University: [ITMO University](https://itmo.ru/ru/)  
Faculty: [FICT](https://fict.itmo.ru)  
Course: [Vibe Coding: AI-боты для бизнеса](https://github.com/itmo-ict-faculty/vibe-coding-for-business)  
Year: 2025/2026  
Group: U4125    
Author: Lastovskaia Anna Alexandrovna  
Lab: Lab2  
Date of create: 27.03.2026  
Date of finished:    
# Подключение бота к данным
## Выбор типа интеграции
Я выбрала интеграцию с БД для хранения данных об учениках и уроках.  
Также, решила изменить структура бота. Теперь его основная задача - собирать обратную связь с учеников.  
## Описание функций бота
**Для учителя:**
- Команда `/feedback @username` — запускает опрос именно этому ученику.
- Команда `/stats` — показывает статистику (средняя оценка по каждому ученику, количество проведённых уроков, все отзывы за неделю).

**Для ученика:**
- После команды учителя `/feedback @username` ученик получает:
  1. Стикер-приз (рандом из твоих стикерпаков: praysmilelove, PopCatAnimated, Kotyakot).
  2. Короткий опрос со звёздочками:
     - How was the lesson? (1–5 stars)
     - What was the most useful thing? (text)
     - What was difficult? (text)
     - What do you want to repeat next time? (text)
- После отправки отзыва бот автоматически отправляет ученику мотивационный факт об английском языке.
- Ученик в любой момент может нажать кнопку **"Fact"** и получить новый мотивационный факт.

**Технические требования:**
- Хранить данные в SQLite (таблицы: users, lessons/feedbacks, reviews).
- Все отзывы сохраняются с датой, именем ученика и оценками.
- Реализовать простую статистику для команды `/stats`.

# Выполнение 
### План разработки бота 

| Этап | Результат |
|------|---------|
| **Этап 1** | Настроена база данных SQLite (`feedback.db`). Реализованы таблицы `users` и `reviews`. Добавлены команды `/start` (с разным приветствием для учителя и ученика) и `/add_student @username Full Name`. Бот может регистрировать учеников. |
| **Этап 2** | Реализована команда `/feedback @username`. При её использовании бот отправляет выбранному ученику случайный стикер из указанных стикерпаков и запускает пошаговый опрос из 4 вопросов (со звёздочками 1–5 и текстовыми ответами). |
| **Этап 3** | Полностью реализовано сохранение отзывов учеников в базу данных SQLite. Добавлена команда `/stats` для учителя, которая выводит среднюю оценку по каждому ученику, количество проведённых уроков и последние отзывы за неделю. |
| **Этап 4** | Добавлена кнопка **"Fact"** для учеников. При нажатии бот отправляет случайный мотивационный факт или цитату об изучении английского языка. Кнопка доступна в любое время. Завершена интеграция с SQLite для хранения и отображения данных. |

## Этап 1. Фрагмент кода интеграции БД
### Создание таблиц
``` 
import aiosqlite
DB_PATH = Path("feedback.db")
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
        await db.commit()
```

## Этап 3. Фрагмент кода интеграции БД
### Сохранение отзывов в БД
```
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
```

## Тестирование
### Этап 1
- Оказалось, БД библиотеку нужно установить сперва локально
  `` ModuleNotFoundError: No module named 'aiosqlite' ``
- Обновленный старт  
  <img width="486" height="339" alt="Снимок" src="https://github.com/user-attachments/assets/5fa1ec00-7345-4fdd-b38d-49ced84561ac" />
  
  <img width="383" height="127" alt="Снимок" src="https://github.com/user-attachments/assets/50392374-14d4-4885-abaa-933cd0c7fc27" />  
### Этап 2
- Оказалось, что, если человек не написал боту первым, бот не может найти его @username  
  <img width="370" height="77" alt="Снимок" src="https://github.com/user-attachments/assets/b53047dc-8a08-4975-96de-10c59bbbfba4" />
  
- Попросила ученика отправить боту /start
- Поняла, что смысла в команде /add_student нет, скорректировала логику:
  1. Ученик сам пишет боту /start → бот автоматически регистрирует его в базе как студента.
  2. Учитель использует команду /students — видит список всех учеников, которые уже написали боту.
  3. Команда /add_student убирается (больше не нужна).
  4. Команда /feedback @username работает только для тех учеников, которые уже зарегистрированы.
  Как следствие, появилась необходимость отличать id учителя от остальных, прописали TEACHER ID в .env  
- Ученик  
  ![5ace750e-0bea-447c-8de2-831662a8ce76](https://github.com/user-attachments/assets/4a2ce356-bb2b-48e1-8d3c-e207c9fa0441)

  ![photo_5368638300744258859_y](https://github.com/user-attachments/assets/12785a1d-fede-4840-9d66-6ab43f97abe1)  

- Учитель  
  <img width="295" height="220" alt="Снимок" src="https://github.com/user-attachments/assets/e68f3716-3a87-499e-8886-d62d56f8d182" />

- Не вышло отправить стикер, поправим позже  
  ```
  2026-04-03 13:33:00,235 | WARNING | stage1-sqlite-bot | Failed to send sticker to student 739256240: TelegramBadRequest('Telegram server says - Bad Request: wrong remote file identifier specified: Wrong string length')
  ```

### Этап 3
- Добавили обзор статистики учителю /stats  
  <img width="367" height="196" alt="Снимок" src="https://github.com/user-attachments/assets/42ee3a9d-0dc2-49f4-b453-b3d200937fde" />  
# Выводы
- У ЛЛМ нет возможности анализировать на шаг вперед, платой за исправление стал лимит в Cursor
- Хорошо получилось облегчить логику, учителю нужно только отправить команду на полусение ОС
- Улучшить можно регистрацию учителей, не фиксировать TEACHER ID 


