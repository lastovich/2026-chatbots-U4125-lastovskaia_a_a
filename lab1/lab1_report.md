University: [ITMO University](https://itmo.ru/ru/)  
Faculty: [FICT](https://fict.itmo.ru)  
Course: [Vibe Coding: AI-боты для бизнеса](https://github.com/itmo-ict-faculty/vibe-coding-for-business)    
Year: 2025/2026  
Group: U4125  
Author: Lastovskaia Anna Alexandrovna  
Lab: Lab1  
Date of create: 27.03.2026  
Date of finished:    
## Preparation
* Установка Cursor  
  <img width="338" height="132" alt="1" src="https://github.com/user-attachments/assets/ade7b3e6-fb4b-425a-b443-2a208eb1a0f4"/>    
* Проверка python  
  <img width="211" height="25" alt="2" src="https://github.com/user-attachments/assets/9704f956-61a7-41c8-847c-eb04efb544f1" />  
* Знакомство с BotFather  
Придумывание имени и генерация ключа прошли успешно
<img width="324" height="321" alt="3" src="https://github.com/user-attachments/assets/0640b76d-f8bc-42a7-bb33-53946de76a48" />

## Fly me to the Moon 🌕  
* С помощью Grok уточнила функционал своего бота  
  ```
  Бот должен:
  Позволять учителю вручную добавлять учеников
  Принимать расписание занятий на ближайшие 2 дня пошагово
  Через 1 час после запланированного времени автоматически спрашивать у учителя подтверждение, прошёл ли урок
  После подтверждения учителя «урок прошёл»:
  Запрашивать у учителя оценку взаимодействия и усвоения материала
  «Отправлять» ученику стикер-приз (заглушка + подробный лог)
  Сразу после этого «отправлять» ученику опросник обратной связи (заглушка + лог)
  Если ученик не ответил на опрос в течение 30 минут — «отправлять» напоминание (заглушка + лог)
  Вести статистику проведённых уроков, тем и оценок
  Каждую субботу в 19:00 автоматически формировать и присылать учителю сводный еженедельный отчёт
  ```  
* Cursor выполнил промпт  
<img width="549" height="380" alt="4" src="https://github.com/user-attachments/assets/300367d1-710f-4441-8568-a9ef8628852a" />


* Заменяю .env.example BOT_TOKEN на значение токена моего бота и убираю .example из названия.
* Столкнулась с проблемой при скачивании  
  ```
  pip install -r requirements.txt
  WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection broken by 'ReadTimeoutError("HTTPSConnectionPool(host='pypi.org', port=443): Read timed out. (read timeout=15)")': /simple/aiogram/
  ```  
  Исправила через зеркало  
  ```
  pip install --default-timeout=200 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
  ```  
* 🆘 снова проблемы, теперь с запуском бота  
  ```
  2026-03-27 23:28:33,064 | ERROR | english-feedback-bot | Критическая ошибка запуска бота: HTTP Client says - ClientConnectorError: Cannot connect to host api.telegram.org:443 ssl:default [None]
  Traceback (most recent call last): File "C:\Users\user\AppData\Local\Programs\Python\Python313\Lib\site-packages\aiohttp\connector.py", line 1313, in _wrap_create_connection
  return await self._loop.create_connection(*args, **kwargs, sock=sock)
    ```  
  * To be continued..
