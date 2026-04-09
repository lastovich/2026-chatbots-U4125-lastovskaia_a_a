University: [ITMO University](https://itmo.ru/ru/)  
Faculty: [FICT](https://fict.itmo.ru)  
Course: [Vibe Coding: AI-боты для бизнеса](https://github.com/itmo-ict-faculty/vibe-coding-for-business)  
Year: 2025/2026    
Group: U4125    
Author: Lastovskaia Anna Alexandrovna  
Lab: Lab3  
Date of create: 27.03.2026  
Date of finished:  

# Подготовка
Установла ngrok, довольно простая настройка:  
<img width="558" height="129" alt="Снимок" src="https://github.com/user-attachments/assets/ef551c1e-772a-4342-93bf-1f574bccbdee" />

Попытка запуска со строчкой кода из описания к лабораторной упала
```
{"ok":false,"error_code":404,"description":"Not Found"}
```

# Проблемы и решения
Довольно быстро поняла, что скорее всего проблема связана с тем, что мой бот не запускается на нужном порту или в принципе не способен к этому.  
У этой ошибки несколько причин, но моя оказалась очевидной -  
> Это значит, что Telegram успешно вызвал твой ngrok-URL, но твой бот не нашёл обработчик запроса (endpoint) и вернул 404.  
> Бот запущен в режиме polling, а не webhook.

Внесенные изменения в код bot.py  
```
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# ==================== WEBHOOK НАСТРОЙКИ ====================
WEBHOOK_PATH = "/webhook"                    # Путь, по которому Telegram будет отправлять обновления
WEBHOOK_PORT = 8000                          # Порт, на котором будет слушать aiohttp сервер

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ИЗМЕНИ НА СВОЙ ngrok URL !!!
BASE_WEBHOOK_URL = "https://твой-ngrok-url.ngrok-free.app"
# Например: "https://a1b2c3d4.ngrok-free.app"
# ========================================================

WEBHOOK_URL = BASE_WEBHOOK_URL.rstrip("/") + WEBHOOK_PATH
# =========================================================

```
В основной части кода  
```
# Регистрируем функцию on_startup
    dp.startup.register(on_startup)

    # === Запуск webhook сервера вместо polling ===
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=WEBHOOK_PORT)
    
    await site.start()
    logger.info(f"🚀 Webhook сервер запущен на порту {WEBHOOK_PORT}")
    logger.info("Ожидаем обновлений от Telegram...")

    # Держим сервер запущенным
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception("Critical error during bot startup: %r", e)
```

Запуск бота после обновления успешен
```
python bot.py
2026-04-09 17:25:38,490 | INFO | stage1-sqlite-bot | ✅ Webhook успешно установлен: https://nonappropriative-kylan-frigidly.ngrok-free.dev/webhook
2026-04-09 17:25:38,530 | INFO | stage1-sqlite-bot | 🚀 Webhook сервер запущен на порту 8000
2026-04-09 17:25:38,531 | INFO | stage1-sqlite-bot | Ожидаем обновлений от Telegram...
```

Обращение к ngrok URL выдает `405: Method Not Allowed`, что тоже окей  
<img width="373" height="77" alt="Снимок1" src="https://github.com/user-attachments/assets/27fb1e26-2772-43ba-89d0-a698887ebe48" />


>Почему так происходит:  
> Ngrok + webhook-сервер ожидает POST-запросы от Telegram.  
> Когда ты открываешь URL в браузере, браузер отправляет GET-запрос.  
> Твой сервер правильно отвечает: «Метод GET не разрешён» → 405 Method Not Allowed.  
> Это хороший знак — сервер webhook работает и слушает запросы.

Для дополнительной проверки отправила в бот команду /stats, в консоли это событие отражено запросами  
<img width="626" height="90" alt="Снимок" src="https://github.com/user-attachments/assets/b7113ac0-a793-4495-aa6b-394f8320fb43" />  

# Фидбек
Обсудили с 1 пользователем. Вот, что можно было бы улучшить для пользователя "ученик":
- Сделать более "понятным": описание и доступные функции
- Добавить кнопки Fact и починить стикеры
Мой фидбек, как пользователя "учитель":
- Стоит добавить нотификацию о том, что новый ученик воспользовался ботом (/start)
- В будущем интересно было бы добавить возможность добавлять свободные слоты для самостоятельной записи учеников и упрощения ведения календаря
  
# Выводы
В этой лабораторной работе бот был переключен из режима Polling в Webhook.  
Благодаря этому, Telegram сам оповещает бота о новых событиях, а не сам бот делает запросы.  
Минусы ngrok:
- Нужно держать ngrok и бот запущенными одновременно
- При каждом новом запуске ngrok URL меняется (приходится обновлять)
Следующие улучшения:
- Вынести работу бота из зависимости от локального устройства
Чему научилась:
- Корректировать код с помощью LLM и блокнота
- Понимать разницу между polling/webhook











