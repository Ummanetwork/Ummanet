from __future__ import annotations

from typing import Dict, Optional

DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = {"ru", "en", "ar", "de", "tr", "dev"}

# Runtime storage populated from DB at startup
_RUNTIME_TEXTS: Dict[str, Dict[str, str]] = {}


def set_runtime_language_texts(lang_code: str, mapping: Dict[str, str]) -> None:
    """Replace runtime texts for a language (loaded from DB)."""
    if not lang_code:
        return
    code = lang_code.lower()
    _RUNTIME_TEXTS[code] = dict(mapping or {})

# Minimal dictionaries; unknown keys fall back to the key itself.
TEXTS_RU: Dict[str, str] = {
    # Welcome
    "welcome.new": "Добро пожаловать, {full_name}!",
    "welcome.back": "С возвращением, {full_name}!",
    # Registration
    "registration.intro": "Для дальнейшего использования бота необходимо зарегистрироваться.",
    "registration.success": "Регистрация завершена!",
    "registration.required": "Чтобы продолжить, зарегистрируйтесь — выберите язык ниже.",
    "registration.already": "Вы уже зарегистрированы.",
    "registration.prompt.name": "Введите ваше имя.",
    "registration.error.name_invalid": "Пожалуйста, укажите корректное имя.",
    "registration.prompt.email": "Укажите адрес электронной почты.",
    "registration.error.email_invalid": "Введите действительный адрес электронной почты.",
    "registration.prompt.phone": "Отправьте номер телефона в международном формате.",
    "registration.prompt.phone_retry": "Номер не совпал. Повторите ввод номера в международном формате.",
    "registration.error.phone_invalid": "Введите корректный номер телефона: 9–14 цифр, можно начинать с +.",
    "registration.prompt.phone_contact": "Поделитесь контактом кнопкой ниже, чтобы подтвердить номер.",
    "registration.error.phone_mismatch": "Номер в контакте не совпадает с указанным.",
    "registration.error.phone_contact_missing": "В присланном контакте отсутствует номер телефона.",
    "registration.error.phone_debug_mismatch": "Отладка: вы ввели {typed}, в контакте {contact}.",
    "registration.error.contact_expected": "Пожалуйста, нажмите кнопку \"Отправить контакт\" ниже.",
    "registration.button.share_contact": "Отправить контакт",

    # Commands & meta
    "command.start.description": "Перезапустить бота",
    "command.lang.description": "Настроить язык интерфейса",
    "command.help.description": "Показать справку",
    "bot.version.info": "Версия бота: {version}",
    "help.message": "Это Шариатский бот. Доступны команды /start, /lang, /help.",

    # Settings dialog
    "language.menu.title": "Пожалуйста, выберите язык интерфейса бота",
    "language.back": "Назад",
    "language.save": "Сохранить",
    "language.saved": "Настройки языка успешно сохранены!",

    # Misc (committee/minimal)
    "welcome.body": "Выберите раздел в главном меню.",
    "input.placeholder.question": "Опишите ваш вопрос…",
    "user.default_name": "Пользователь",
    "docs.default_name": "Документ",
    "error.document.send": "Не удалось отправить документ: {name}",

    # AI
    "ai.system.prompt": (
        "🕌 ПРОМТ: Шариатский ассистент (только Shamela, арабский + перевод, без ссылок)"
        ""
        "Ты — исламский шариатский ассистент, который отвечает на вопросы исключительно на основе классических исламских книг, представленных в библиотеке Shamela."
        ""
        "📌 Главный принцип"
        ""
        "Ты не имеешь права использовать никакие источники, кроме текстов из Shamela."
        "Запрещено опираться на Википедию, современные сайты, личные мнения или неподтверждённые ответы."
        ""
        "---"
        ""
        "✅ Обязательный формат ответа"
        ""
        "1) Арабский оригинал (дословно из книги)"
        ""
        "Ты всегда приводишь оригинальный арабский текст:"
        ""
        "النص العربي: «…цитата…»"
        ""
        "---"
        ""
        "2) Точный перевод на язык вопроса"
        ""
        "Перевод должен быть на том языке, на котором пользователь задал вопрос"
        "(русский → русский перевод, английский → английский перевод, турецкий → турецкий перевод)."
        ""
        "Перевод: «…перевод…»"
        ""
        "---"
        ""
        "3) Полная библиографическая ссылка (без URL)"
        ""
        "После цитаты обязательно указывай:"
        ""
        "название книги"
        ""
        "имя автора"
        ""
        "раздел/глава (باب / فصل)"
        ""
        "том (الجزء)"
        ""
        "страница (الصفحة)"
        ""
        "номер вопроса (если есть)"
        ""
        "Пример:"
        ""
        "المصدر:"
        ""
        "الكتاب: المغни"
        ""
        "المؤلف: ابن قدامة"
        ""
        "الباب: كتاب الطهارة"
        ""
        "الجزء: 1"
        ""
        "الصفحة: 215"
        ""
        "---"
        ""
        "4) Разъяснение (только в рамках текста)"
        ""
        "Ты можешь кратко объяснить вывод, но без личных домыслов:"
        ""
        "Пояснение: Этот текст указывает, что…"
        ""
        "---"
        ""
        "5) Если есть разногласие — привести мнения"
        ""
        "Если вопрос спорный, приведи несколько цитат из Shamela:"
        ""
        "قول الحنفية: …"
        "قول المالكية: …"
        "قول الشافعية: …"
        "قول الحنابلة: …"
        ""
        "Каждое мнение — с арабской цитатой и переводом."
        ""
        "---"
        ""
        "❌ Запрещено"
        ""
        "давать ответ без арабской цитаты"
        ""
        "писать «учёные говорят» без источника"
        ""
        "вставлять ссылки на Shamela"
        ""
        "использовать любые сайты кроме Shamela"
        ""
        "выдавать фетву от себя"
        ""
        "сокращать ответы до общих слов"
        ""
        "---"
        ""
        "🧠 Если ответа нет в Shamela"
        ""
        "Ты обязан сказать:"
        ""
        "«В текстах Shamela не найден прямой однозначный ответ. Ниже приведены ближайшие связанные упоминания из классических книг…»"
        ""
        "И привести ближайшие тексты."
        ""
        "---"
        ""
        "📝 Стиль ответа"
        ""
        "Ответ должен быть:"
        ""
        "обширным"
        ""
        "строго академическим"
        ""
        "основанным на книгах фикха и хадиса"
        ""
        "с уважительным исламским языком"
        ""
        "---"
        ""
        "Пример ответа (шаблон)"
        ""
        "Вопрос: Можно ли объединять молитвы в пути?"
        ""
        "النص العربي: «…»"
        ""
        "Перевод: «…»"
        ""
        "المصدر:"
        ""
        "الكتاب: زاد المعاد"
        ""
        "المؤلف: ابن القيم"
        ""
        "الفصل: صلاة المسافر"
        ""
        "الجزء: 1"
        ""
        "الصفحة: 456"
    ),
    "ai.response.prefix": "🤖 Ответ ИИ:",
    "ai.response.footer": "При необходимости направим вопрос улемам.",
    "ai.error.unavailable": "ИИ сейчас недоступен.",
    "ai.error.empty": "Ответ пуст.",
    "ai.error.empty.trimmed": "Ответ пуст после фильтрации.",
    "ai.error.generic": "Произошла ошибка при генерации ответа.",
    "ai.response.waiting": "Формируем ответ…",

# Buttons & menus
    "button.back": "Назад",
    "button.cancel": "Отменить",
    "button.materials": "Материалы",
    "button.ask.scholars": "Обратиться к учёным",
    "button.community.support": "Поддержать сообщество",
    "button.holiday.ask_ai": "Спросить ИИ",
    "button.holiday.download": "Скачать документ",
    "button.answer.user": "Ответить пользователю",
    "button.profile.open": "Профиль",
    "button.my_cases.contracts": "Мои договоры",
    "button.my_cases.courts": "Мои суды",
    "button.my_cases.inheritance": "Наследство и завещания",
    "button.my_cases.nikah": "Никах",
    "button.my_cases.spouse_search": "🌿 Знакомство",
    "button.spouse.profile": "📝 Моя анкета",
    "button.spouse.search": "🔎 Поиск",
    "button.spouse.requests": "📨 Мои запросы",
    "button.spouse.rules": "🛡 Правила и защита",
    "button.spouse.ask": "❓ Обратиться к учёным",
    "button.nikah.new": "📝 Создать новый никях",
    "button.nikah.my": "📄 Мои браки",
    "button.nikah.rules": "🕋 Правила шариата о браке",
    "button.nikah.ask": "❓ Обратиться к учёным",
    "button.blacklist.view": "Просмотреть",
    "button.blacklist.search": "Искать",
    "button.blacklist.report": "Пожаловаться",
    "button.blacklist.appeal": "Оспорить",
    "button.knowledge.foundation": "Основы",
    "button.knowledge.holidays": "Мусульманские праздники",
    "button.meetings.open": "Совещания",
    "button.chat.men": "Мужской чат",
    "button.chat.women": "Женский чат",
    "button.enforcement.open": "Перейти",

    # Contract flow
    "contracts.create.menu.title": "Создание договора",
    "contracts.create.option.templates": "Выбрать из шаблонов",
    "contracts.create.option.upload": "Загрузить файл",
    "contracts.none": "Нет доступных шаблонов.",
    "contracts.saved": "Договор сохранён.",
    "contracts.search.found": "Найдены шаблоны.",
    "contracts.search.none": "Шаблоны не найдены.",
    "contracts.search.prompt": "Введите тему или название шаблона.",
    "contracts.sent": "Договор отправлен.",
    "contracts.flow.party.approve": "✅ Подтвердить",
    "contracts.flow.party.changes": "✍️ Нужны правки",
    "contracts.flow.party.sign": "✅ Подписать договор",
    "contracts.flow.party.comment.prompt": "Опишите, что нужно изменить в договоре.",
    "contracts.flow.party.thanks": "Спасибо! Ваш ответ отправлен автору договора.",
    "contracts.flow.party.approved.notice": "Пользователь {party} подтвердил договор.",
    "contracts.flow.party.changes.notice": "Пользователь {party} запросил правки: {comment}",
    "contracts.flow.party.signed.notice": "Пользователь {party} подписал договор.",
    "contracts.list.title": "Ваши договоры:",
    "contracts.title.unknown": "Договор",
    "contracts.list.item": "📄 {title}\nСтатус: {status}\nДата: {date}\nКонтрагент: {party}",
    "contracts.list.party.unknown": "Не указан",
    "contracts.status.draft": "Черновик",
    "contracts.status.confirmed": "Сформирован",
    "contracts.status.sent_to_party": "Отправлен стороне",
    "contracts.status.party_approved": "Подтверждён стороной",
    "contracts.status.party_changes_requested": "Запрошены правки",
    "contracts.status.sent_to_scholar": "Отправлен учёному",
    "contracts.status.scholar_send_failed": "Ошибка отправки учёному",
    "contracts.status.signed": "Подписан",
    "contracts.status.sent": "Отправлен",
    "contracts.edit.not_allowed": "Редактирование недоступно для этого статуса договора.",
    "contracts.stats.info": "Статистика доступных шаблонов.",
    "contracts.template.coming_soon": "Скоро будет доступно.",
    "contracts.template.download": "Скачать шаблон",
    "contracts.template.missing": "Шаблон недоступен.",
    "contracts.template.start": "Начать работу с шаблонами",
    "contracts.flow.placeholder.prompt": "Введите значение для поля: {field}",
    "contracts.flow.field.required": "Это поле обязательно.",
    "contracts.flow.actions.title": "Выберите действие",
    "contracts.flow.button.download_txt": "⬇️ Скачать текст (txt)",
    "contracts.flow.button.download_pdf": "⬇️ Скачать PDF",
    "contracts.flow.button.send_other": "📤 Отправить другой стороне",
    "contracts.flow.button.send_scholar": "🕌 Отправить учёному",
    "contracts.flow.button.send_court": "⚖️ Передать дело в суд",
    "contracts.flow.send_court.not_signed": "Передать дело в суд можно только после подписания обеими сторонами.",
    "contracts.flow.button.delete": "🗑 Удалить договор",
    "contracts.flow.button.back_actions": "↩️ Назад к действиям",
    "contracts.delete.done": "Договор удалён.",
    "contracts.flow.preview.too_long": "Текст слишком длинный, используйте кнопки скачивания.",
    "contracts.flow.template.empty": "Шаблон пустой.",
    "contracts.flow.pdf.failed": "Не удалось сформировать PDF.",
    "contracts.flow.send_other.prompt": "Введите @username или Telegram ID получателя.",
    "contracts.flow.send_other.pick_contact": "Или выберите контакт:",
    "contracts.flow.send_other.invalid": "Неверный формат. Введите @username или числовой ID.",
    "contracts.flow.send_other.not_found": "Пользователь с таким именем не найден. Укажите @username или Telegram ID.",
    "contracts.flow.send_other.ambiguous": "Найдено несколько пользователей с таким именем. Укажите @username или Telegram ID.",
    "contracts.flow.send_other.message": "Договор от {sender}.",
    "contracts.flow.send_other.sent": "Договор отправлен пользователю {recipient}.",
    "contracts.flow.send_other.failed": "Не удалось отправить договор. Получатель должен запустить бота или разрешить сообщения.",
    "contracts.flow.button.pick_contact": "📇 Выбрать контакт",
    "contracts.invite.code": "Контрагент ещё не зарегистрирован. Передайте ссылку:\n{invite_link}",
    "contracts.invite.code.only": "Контрагент ещё не зарегистрирован. Передайте код: {invite_code}",
    "contracts.invite.self": "Это ваш договор.",
    "contracts.invite.used": "Приглашение уже использовано.",
    "contracts.invite.joined": "Вы присоединились к договору «{title}».",
    "contracts.invite.owner_notice": "Контрагент присоединился к договору «{title}».",
    "contracts.flow.send_scholar.sent": "Договор отправлен учёному.",
    "contracts.flow.send_scholar.failed": "Не удалось отправить договор учёному.",
    "contracts.flow.title": "Создать договор",
    "contracts.flow.ready": "Данные для договора «{contract}» собраны. Сформировать договор?",
    "contracts.flow.confirmed": "Договор сохранен.",
    "contracts.flow.button.generate": "Сформировать договор",
    "contracts.flow.button.confirm": "Подтвердить и сохранить",
    "contracts.flow.button.edit": "Подробнее",
    "contracts.flow.button.skip": "Пропустить",
    "contracts.flow.choice.required": "Выберите вариант на кнопках.",
    "contracts.flow.choice.yes": "Да",
    "contracts.flow.choice.no": "Нет",
    "contracts.flow.choice.ijara.damage.tenant": "По вине арендатора",
    "contracts.flow.choice.ijara.damage.agreement": "По договоренности",
    "contracts.flow.choice.istisna.materials.customer": "Материалы заказчика",
    "contracts.flow.choice.istisna.materials.contractor": "Материалы исполнителя",
    "contracts.flow.choice.bay.condition.new": "Новый",
    "contracts.flow.choice.bay.condition.used": "Б/у",
    "contracts.flow.choice.bay.payment.before": "До передачи",
    "contracts.flow.choice.bay.payment.after": "После передачи",
    "contracts.flow.choice.bay.payment.installments": "Частями",
    "contracts.flow.choice.bay.payment.deferred": "С отсрочкой платежа",
    "contracts.flow.type.qard": "💸 Карды-хасан (займ без процентов)",
    "contracts.flow.type.ijara": "🏠 Аренда / Иджара",
    "contracts.flow.type.salam": "🚚 Предоплата — Саляма",
    "contracts.flow.type.istisna": "🛠 Изготовление — Истисна",
    "contracts.flow.type.bay": "💼 Купля-продажа / Бай’",
    "contracts.flow.type.musharaka": "👥 Партнёрство / Мушарака",
    "contracts.flow.type.mudaraba": "📊 Инвестиция / Мудараба",
    "contracts.flow.type.hiba": "🎁 Дарение / Хиба",
    "contracts.flow.type.amana": "📦 Хранение / Аманат",
    "contracts.flow.type.kafala": "🛡 Поручительство / Кафаля",
    "contracts.flow.type.sulh": "⚖️ Мирное соглашение / Сульх",
    "contracts.flow.type.installment": "💳 Рассрочка",
    "contracts.flow.type.murabaha": "📦 Мурабаха (наценка)",
    "contracts.flow.type.rahn": "📌 Рахн (залог)",
    "contracts.flow.type.hawala": "🔁 Хавала (перевод долга)",
    "contracts.flow.type.inan": "🤝 Инан (общее участие)",
    "contracts.flow.type.wakala": "🧾 Вакала (доверенность)",
    "contracts.flow.type.sadaqa": "💞 Садака (пожертвование)",
    "contracts.flow.type.ariya": "🪙 Ария (временное пользование)",
    "contracts.flow.type.waqf": "🏛 Вакф (эндаумент)",
    "contracts.flow.type.wasiya": "📝 Васия (завещание)",
    "contracts.flow.type.nikah": "💍 Никях (брак)",
    "contracts.flow.type.talaq": "🕊 Талак (развод)",
    "contracts.flow.type.khul": "🕊 Хуль (развод по инициативе жены)",
    "contracts.flow.type.ridaa": "👶 Ридаа (вскармливание)",
    "contracts.flow.type.uaria": "🪙 Уария (временное пользование имуществом)",
    "contracts.flow.qard.lender_name": "Имя дающего",
    "contracts.flow.qard.lender_document": "Документ / регистрация займодавца",
    "contracts.flow.qard.lender_address": "Адрес займодавца",
    "contracts.flow.qard.lender_contact": "Контактные данные займодавца",
    "contracts.flow.qard.borrower_name": "Имя получателя",
    "contracts.flow.qard.borrower_document": "Документ / регистрация займополучателя",
    "contracts.flow.qard.borrower_address": "Адрес займополучателя",
    "contracts.flow.qard.borrower_contact": "Контактные данные займополучателя",
    "contracts.flow.qard.amount": "Сумма",
    "contracts.flow.qard.purpose": "Цель займа",
    "contracts.flow.qard.due_date": "Срок возврата (дата или текст)",
    "contracts.flow.qard.repayment_method": "Форма возврата",
    "contracts.flow.qard.collateral_required": "Есть залог?",
    "contracts.flow.qard.collateral_description": "Описание залога",
    "contracts.flow.qard.extra_terms": "Доп. условия (опционально)",
    "contracts.flow.ijara.landlord": "Арендодатель",
    "contracts.flow.ijara.landlord_document": "Документ / регистрация арендодателя",
    "contracts.flow.ijara.landlord_address": "Адрес арендодателя",
    "contracts.flow.ijara.landlord_contact": "Контактные данные арендодателя",
    "contracts.flow.ijara.tenant": "Арендатор",
    "contracts.flow.ijara.tenant_document": "Документ / регистрация арендатора",
    "contracts.flow.ijara.tenant_address": "Адрес арендатора",
    "contracts.flow.ijara.tenant_contact": "Контактные данные арендатора",
    "contracts.flow.ijara.object": "Объект аренды",
    "contracts.flow.ijara.object_details": "Количество, характеристики",
    "contracts.flow.ijara.object_condition": "Состояние имущества",
    "contracts.flow.ijara.term": "Срок",
    "contracts.flow.ijara.price": "Цена",
    "contracts.flow.ijara.currency": "Валюта расчёта",
    "contracts.flow.ijara.payment_order": "Порядок оплаты",
    "contracts.flow.ijara.damage_responsibility": "Ответственность при порче",
    "contracts.flow.ijara.additional_terms": "Дополнительные условия (опционально)",
    "contracts.flow.choice.ijara.payment.monthly": "Ежемесячно",
    "contracts.flow.choice.ijara.payment.one_time": "Единоразово",
    "contracts.flow.choice.ijara.payment.other": "По иной договорённости",
    "contracts.flow.salam.buyer": "Покупатель",
    "contracts.flow.salam.buyer_document": "Документ / регистрация покупателя",
    "contracts.flow.salam.buyer_address": "Адрес покупателя",
    "contracts.flow.salam.buyer_contact": "Контактные данные покупателя",
    "contracts.flow.salam.supplier": "Поставщик",
    "contracts.flow.salam.supplier_document": "Документ / регистрация продавца",
    "contracts.flow.salam.supplier_address": "Адрес продавца",
    "contracts.flow.salam.supplier_contact": "Контактные данные продавца",
    "contracts.flow.salam.goods": "Что будет поставлено (описание)",
    "contracts.flow.salam.goods_name": "Наименование товара",
    "contracts.flow.salam.goods_quality": "Вид / сорт / качество",
    "contracts.flow.salam.goods_quantity": "Количество (в мерах Шариата)",
    "contracts.flow.salam.goods_packaging": "Упаковка / характеристики",
    "contracts.flow.salam.delivery_date": "Срок поставки",
    "contracts.flow.salam.fixed_price": "Стоимость (фиксированная)",
    "contracts.flow.salam.delivery_place": "Место получения",
    "contracts.flow.istisna.customer": "Заказчик",
    "contracts.flow.istisna.customer_document": "Документ / регистрация заказчика",
    "contracts.flow.istisna.customer_address": "Адрес заказчика",
    "contracts.flow.istisna.customer_contact": "Контактные данные заказчика",
    "contracts.flow.istisna.contractor": "Исполнитель",
    "contracts.flow.istisna.contractor_document": "Документ / регистрация исполнителя",
    "contracts.flow.istisna.contractor_address": "Адрес исполнителя",
    "contracts.flow.istisna.contractor_contact": "Контактные данные исполнителя",
    "contracts.flow.istisna.product": "Что изготовить",
    "contracts.flow.istisna.product_name": "Наименование изделия",
    "contracts.flow.istisna.product_materials": "Материал(ы)",
    "contracts.flow.istisna.product_dimensions": "Размеры / объём / характеристики",
    "contracts.flow.istisna.product_quality": "Качество / стандарт",
    "contracts.flow.istisna.product_quantity": "Количество",
    "contracts.flow.istisna.term": "Срок",
    "contracts.flow.istisna.materials": "Материалы: чьи?",
    "contracts.flow.istisna.price": "Цена",
    "contracts.flow.istisna.payment_schedule": "Порядок оплаты",
    "contracts.flow.istisna.start_date": "Срок начала изготовления",
    "contracts.flow.istisna.delivery_place": "Место передачи изделия",
    "contracts.flow.bay.seller": "Продавец",
    "contracts.flow.bay.seller_document": "Документ / регистрация продавца",
    "contracts.flow.bay.seller_address": "Адрес продавца",
    "contracts.flow.bay.seller_contact": "Контактные данные продавца",
    "contracts.flow.bay.buyer": "Покупатель",
    "contracts.flow.bay.buyer_document": "Документ / регистрация покупателя",
    "contracts.flow.bay.buyer_address": "Адрес покупателя",
    "contracts.flow.bay.buyer_contact": "Контактные данные покупателя",
    "contracts.flow.bay.goods": "Товар",
    "contracts.flow.bay.goods_details": "Количество, характеристики",
    "contracts.flow.bay.condition": "Состояние товара",
    "contracts.flow.bay.price": "Цена",
    "contracts.flow.bay.currency": "Валюта расчёта",
    "contracts.flow.bay.payment_timing": "Когда производится оплата",
    "contracts.flow.bay.delivery_term": "Срок передачи товара",
    "contracts.flow.bay.khiyar_term": "Срок хияр аш-шарт (если есть)",
    "contracts.flow.installment.seller": "Продавец",
    "contracts.flow.installment.buyer": "Покупатель",
    "contracts.flow.installment.goods": "Описание товара",
    "contracts.flow.installment.goods_details": "Количество, характеристики",
    "contracts.flow.installment.goods_condition": "Состояние товара",
    "contracts.flow.installment.total_price": "Общая цена",
    "contracts.flow.installment.currency": "Валюта расчёта",
    "contracts.flow.installment.down_payment": "Первоначальный взнос",
    "contracts.flow.installment.count": "Количество платежей",
    "contracts.flow.installment.amount": "Сумма каждого платежа",
    "contracts.flow.installment.schedule": "График платежей",
    "contracts.flow.installment.delivery_term": "Срок передачи товара",
    "contracts.flow.murabaha.seller": "Продавец",
    "contracts.flow.murabaha.buyer": "Покупатель",
    "contracts.flow.murabaha.goods": "Описание товара",
    "contracts.flow.murabaha.cost_price": "Себестоимость",
    "contracts.flow.murabaha.markup": "Наценка",
    "contracts.flow.murabaha.final_price": "Итоговая цена",
    "contracts.flow.murabaha.currency": "Валюта расчёта",
    "contracts.flow.murabaha.payment_schedule": "Порядок оплаты",
    "contracts.flow.murabaha.delivery_term": "Срок передачи товара",
    "contracts.flow.musharaka.partner1_contribution": "Участник 1: вклад",
    "contracts.flow.musharaka.partner2_contribution": "Участник 2: вклад",
    "contracts.flow.musharaka.profit_split": "Распределение прибыли (в %)",
    "contracts.flow.musharaka.partner1_name": "Партнёр 1",
    "contracts.flow.musharaka.partner2_name": "Партнёр 2",
    "contracts.flow.musharaka.business_description": "Описание проекта",
    "contracts.flow.musharaka.loss_share": "Распределение убытков",
    "contracts.flow.musharaka.management_roles": "Роли и управление",
    "contracts.flow.musharaka.duration": "Срок партнёрства",
    "contracts.flow.mudaraba.investor": "Инвестор",
    "contracts.flow.mudaraba.manager": "Управляющий",
    "contracts.flow.mudaraba.capital": "Сумма капитала",
    "contracts.flow.mudaraba.profit_investor": "Доля прибыли инвестора (%)",
    "contracts.flow.mudaraba.profit_manager": "Доля прибыли управляющего (%)",
    "contracts.flow.mudaraba.business_description": "Описание проекта",
    "contracts.flow.mudaraba.duration": "Срок проекта",
    "contracts.flow.mudaraba.profit_distribution": "Условия распределения прибыли",
    "contracts.flow.mudaraba.loss_terms": "Условия убытков",
    "contracts.flow.inan.partner1_name": "Участник 1",
    "contracts.flow.inan.partner2_name": "Участник 2",
    "contracts.flow.inan.business_description": "Описание проекта",
    "contracts.flow.inan.partner1_contribution": "Вклад участника 1",
    "contracts.flow.inan.partner2_contribution": "Вклад участника 2",
    "contracts.flow.inan.profit_split": "Распределение прибыли",
    "contracts.flow.inan.management_roles": "Роли и управление",
    "contracts.flow.inan.duration": "Срок партнёрства",
    "contracts.flow.wakala.principal": "Доверитель",
    "contracts.flow.wakala.agent": "Представитель",
    "contracts.flow.wakala.scope": "Объём полномочий",
    "contracts.flow.wakala.fee": "Вознаграждение",
    "contracts.flow.wakala.duration": "Срок действия",
    "contracts.flow.wakala.reporting_terms": "Отчётность",
    "contracts.flow.wakala.termination_terms": "Условия прекращения",
    "contracts.flow.hiba.donor": "Даритель",
    "contracts.flow.hiba.recipient": "Получатель",
    "contracts.flow.hiba.gift": "Что дарится",
    "contracts.flow.hiba.return_condition": "Есть ли условие возврата?",
    "contracts.flow.sadaqa.donor": "Жертвователь",
    "contracts.flow.sadaqa.beneficiary": "Получатель",
    "contracts.flow.sadaqa.description": "Описание пожертвования",
    "contracts.flow.sadaqa.amount": "Сумма пожертвования",
    "contracts.flow.sadaqa.purpose": "Цель пожертвования",
    "contracts.flow.sadaqa.transfer_method": "Способ передачи",
    "contracts.flow.ariya.lender": "Даритель пользования",
    "contracts.flow.ariya.borrower": "Пользователь",
    "contracts.flow.ariya.item_description": "Описание имущества",
    "contracts.flow.ariya.use_term": "Срок пользования",
    "contracts.flow.ariya.return_condition": "Условия возврата",
    "contracts.flow.ariya.liability_terms": "Ответственность за повреждение",
    "contracts.flow.waqf.founder": "Учредитель вакфа",
    "contracts.flow.waqf.manager": "Управляющий (мутавалли)",
    "contracts.flow.waqf.asset": "Имущество вакфа",
    "contracts.flow.waqf.purpose": "Цель вакфа",
    "contracts.flow.waqf.beneficiaries": "Бенефициары",
    "contracts.flow.waqf.management_conditions": "Условия управления",
    "contracts.flow.wasiya.testator": "Завещатель",
    "contracts.flow.wasiya.beneficiary": "Получатель",
    "contracts.flow.wasiya.executor": "Исполнитель завещания",
    "contracts.flow.wasiya.description": "Описание имущества/права",
    "contracts.flow.wasiya.conditions": "Условия передачи",
    "contracts.flow.amana.owner": "Владелец имущества",
    "contracts.flow.amana.custodian": "Хранитель",
    "contracts.flow.amana.asset": "Имущество (описание)",
    "contracts.flow.amana.term": "Срок хранения",
    "contracts.flow.amana.storage_conditions": "Условия хранения",
    "contracts.flow.amana.custodian_liability": "Ответственность хранителя",
    "contracts.flow.amana.return_terms": "Условия возврата",
    "contracts.flow.uaria.lender": "Передающая сторона",
    "contracts.flow.uaria.borrower": "Пользующаяся сторона",
    "contracts.flow.uaria.item_description": "Описание имущества",
    "contracts.flow.uaria.use_term": "Срок пользования",
    "contracts.flow.uaria.return_condition": "Условия возврата",
    "contracts.flow.uaria.liability_terms": "Ответственность за повреждение",
    "contracts.flow.kafala.guarantor": "Поручитель",
    "contracts.flow.kafala.debtor": "За кого",
    "contracts.flow.kafala.creditor": "Кредитор",
    "contracts.flow.kafala.obligation": "Обязательство",
    "contracts.flow.kafala.term": "Срок поручительства",
    "contracts.flow.rahn.pledger": "Залогодатель",
    "contracts.flow.rahn.pledgee": "Залогодержатель",
    "contracts.flow.rahn.asset": "Предмет залога",
    "contracts.flow.rahn.asset_value": "Оценочная стоимость",
    "contracts.flow.rahn.debt_amount": "Сумма обязательства",
    "contracts.flow.rahn.debt_due_date": "Срок исполнения обязательства",
    "contracts.flow.rahn.storage_terms": "Условия хранения залога",
    "contracts.flow.rahn.redemption_terms": "Условия выкупа/возврата",
    "contracts.flow.hawala.transferor": "Передающий долг",
    "contracts.flow.hawala.new_debtor": "Новый должник",
    "contracts.flow.hawala.transferee": "Кредитор",
    "contracts.flow.hawala.debt_amount": "Сумма долга",
    "contracts.flow.hawala.debt_currency": "Валюта долга",
    "contracts.flow.hawala.due_date": "Срок исполнения",
    "contracts.flow.hawala.transfer_terms": "Условия перевода",
    "contracts.flow.sulh.side_a": "Сторона А",
    "contracts.flow.sulh.side_b": "Сторона Б",
    "contracts.flow.sulh.dispute": "Суть спора",
    "contracts.flow.sulh.resolution": "Предлагаемое решение",
    "contracts.flow.sulh.waive_claims": "Стороны отказываются от претензий?",
    "contracts.flow.sulh.party_one_name": "Сторона 1: ФИО / наименование",
    "contracts.flow.sulh.party_one_document": "Сторона 1: документ / регистрация",
    "contracts.flow.sulh.party_one_address": "Сторона 1: адрес",
    "contracts.flow.sulh.party_one_contact": "Сторона 1: контактные данные",
    "contracts.flow.sulh.party_two_name": "Сторона 2: ФИО / наименование",
    "contracts.flow.sulh.party_two_document": "Сторона 2: документ / регистрация",
    "contracts.flow.sulh.party_two_address": "Сторона 2: адрес",
    "contracts.flow.sulh.party_two_contact": "Сторона 2: контактные данные",
    "contracts.flow.sulh.dispute_subject": "Суть спора / конфликта",
    "contracts.flow.sulh.proposed_resolution": "Предлагаемое решение",
    "contracts.flow.sulh.claims_waived": "Стороны отказываются от претензий?",
    "contracts.flow.nikah.groom": "Жених",
    "contracts.flow.nikah.bride": "Невеста",
    "contracts.flow.nikah.wali": "Вали (опекун невесты)",
    "contracts.flow.nikah.mahr": "Махр (брачный дар)",
    "contracts.flow.nikah.witnesses": "Свидетели",
    "contracts.flow.nikah.date_place": "Дата и место",
    "contracts.flow.nikah.additional_terms": "Дополнительные условия",
    "contracts.flow.talaq.husband": "Муж",
    "contracts.flow.talaq.wife": "Жена",
    "contracts.flow.talaq.date": "Дата талака",
    "contracts.flow.talaq.iddah_terms": "Срок ‘идда",
    "contracts.flow.talaq.rights_settlement": "Вопросы махра и прав",
    "contracts.flow.khul.wife": "Жена",
    "contracts.flow.khul.husband": "Муж",
    "contracts.flow.khul.compensation": "Компенсация (фидия)",
    "contracts.flow.khul.date": "Дата соглашения",
    "contracts.flow.khul.additional_terms": "Дополнительные условия",
    "contracts.flow.ridaa.nurse": "Кормящая женщина",
    "contracts.flow.ridaa.child": "Ребёнок",
    "contracts.flow.ridaa.guardian": "Опекун ребёнка",
    "contracts.flow.ridaa.period": "Период вскармливания",
    "contracts.flow.ridaa.compensation": "Вознаграждение",
    "contracts.flow.ridaa.additional_terms": "Дополнительные условия",
    "contracts.validation.riba": "⚠️ Проценты, выгода или риба запрещены в шариате. Удалите пункт.",
    "contracts.validation.unclear_terms": "⚠️ Условия должны быть конкретными. Уточните пункт.",
    "contracts.validation.haram_goods": "⚠️ Этот товар запрещён по шариату.",
    "contracts.validation.price_fixed": "⚠️ Цена должна быть фиксирована заранее по шариату.",
    "contracts.validation.profit_guarantee": "⚠️ В шариате прибыль не гарантируется, только распределяется.",
    "contracts.validation.hiba_return_forbidden": "⚠️ Условие возврата в хиба запрещено (кроме отца детям).",
    "contracts.validation.percent_invalid": "Введите корректные проценты (например, 60/40 или 50%).",
    "contracts.auto.button": "🤖 Автоподбор",
    "contracts.auto.question.intent": "Что хотите оформить?",
    "contracts.auto.question.money": "Есть ли деньги?",
    "contracts.auto.question.money_kind": "Выберите тип сделки с деньгами",
    "contracts.auto.question.goods": "Есть ли товар?",
    "contracts.auto.question.investment": "Выберите тип партнёрства",
    "contracts.auto.option.family": "Семья",
    "contracts.auto.option.money": "Деньги",
    "contracts.auto.option.purchase": "Покупка",
    "contracts.auto.option.work": "Работа",
    "contracts.auto.option.rent": "Аренда",
    "contracts.auto.option.storage": "Хранение",
    "contracts.auto.option.gift": "Дарение",
    "contracts.auto.option.guarantee": "Поручительство",
    "contracts.auto.option.settlement": "Мирное соглашение",
    "contracts.auto.option.loan": "Займ",
    "contracts.auto.option.investment": "Инвестиция",
    "contracts.auto.option.goods_now": "Есть сейчас",
    "contracts.auto.option.goods_later": "Будет позже (деньги сейчас)",
    "contracts.auto.option.goods_custom": "Изготовят под заказ",
    "contracts.auto.option.goods_none": "Нет товара",
    "contracts.auto.result": "Подходит договор: {contract}. Создать?",
    "contracts.auto.family": "Семейные договоры оформляются в разделе Никях/Васийя.",
    "contracts.auto.unsupported": "Не удалось подобрать договор. Выберите вручную.",
    "contracts.auto.button.confirm": "Да",
    "contracts.auto.button.restart": "Изменить ответы",
    "contracts.templates.choose_category": "Выберите категорию",
    "contracts.templates.choose_contract": "Выберите шаблон",
    "contracts.templates.select_action": "Выберите действие",
    "contracts.title.prompt": "Название договора",
    "contracts.upload.prompt": "Загрузите файл (PDF)",

    # Courts
    "courts.file.instructions": "Прикрепите файл заявления в PDF.",
    "courts.info.closed": "Дело закрыто.",
    "courts.info.in_progress": "Дело в процессе.",
    "courts.info.opened": "Дело открыто.",

    # Docs
    "docs.empty": "Материалы отсутствуют.",
    "docs.searching": "Идёт поиск материалов…",
    "docs.holiday.searching": "Идёт поиск праздничных материалов…",
    "holiday.ai.default_question": "Поздравление и наставление по празднику",
    "holiday.description.template": "Подготовленный материал к празднику.",
    "holiday.document.missing": "Документ не найден.",

    # Errors & notifications
    "error.request.invalid": "Некорректный запрос.",
    "error.answer.recipient_unknown": "Получатель неизвестен.",
    "answer.delivery.failed": "Не удалось доставить ответ.",
    "answer.sent.confirmation": "Ответ отправлен.",
    "notify.answer.user": "Ответ отправлен пользователю.",
    "notify.question.forward": "Вопрос отправлен на рассмотрение.",

    # Contracts validation errors
    "error.contracts.file.only_pdf": "Разрешён только PDF.",
    "error.contracts.file.required_pdf": "Нужен файл PDF.",
    "error.contracts.file.too_large": "Файл слишком большой.",
    "error.contracts.name.empty": "Введите название.",
    "error.contracts.name.missing_state": "Ошибка состояния.",
    "error.contracts.name.too_long": "Название слишком длинное.",
    "error.contracts.search.empty": "Введите поисковый запрос.",

# Questions
    "question.prompt": "Опишите ваш вопрос.",
    "question.sent": "Вопрос отправлен.",
    "question.failed": "Не удалось отправить вопрос.",
    "question.empty": "Пустой вопрос.",

    # Blacklist & enforcement
    "blacklist.view.header": "Актуальные записи чёрного списка",
    "blacklist.view.empty": "Чёрный список пока пуст.",
    "blacklist.view.more": "Показаны первые записи. Осталось ещё {count}.",
    "blacklist.error.backend_unavailable": "Связь с бекендом недоступна. Попробуйте позже.",
    "blacklist.error.generic": "Не удалось выполнить запрос. Повторите позже.",
    "blacklist.error.validation": "Данные не прошли проверку. Проверьте поля и попробуйте снова.",
    "blacklist.field.empty": "не указано",
    "blacklist.field.date_format": "%d.%m.%Y",
    "blacklist.entry.status.active": "активна",
    "blacklist.entry.status.inactive": "снята",
    "blacklist.entry.template": (
        "• {name}\n"
        "  Статус: {status}\n"
        "  Город: {city}\n"
        "  Телефон: {phone}\n"
        "  Дата рождения: {birthdate}\n"
        "  Жалобы: {complaints}, апелляции: {appeals}\n"
        "  Обновлено: {added}"
    ),
    "blacklist.common.cancel_hint": "Вы можете написать «отмена», чтобы прервать процесс.",
    "blacklist.common.cancelled": "Ввод отменён.",
    "blacklist.search.prompt": (
        "Введите запрос в формате «Имя;Город;ГГГГ-ММ-ДД». Город и дату рождения можно опустить."
    ),
    "blacklist.search.error.empty": "Укажите имя для поиска.",
    "blacklist.search.error.birthdate": "Дата должна быть в формате ГГГГ-ММ-ДД.",
    "blacklist.search.results.empty": "Совпадений не найдено.",
    "blacklist.report.prompt.name": "Введите имя нарушителя (обязательно).",
    "blacklist.report.prompt.phone": "Укажите телефон нарушителя или поставьте «-», если неизвестно.",
    "blacklist.report.prompt.birthdate": "Укажите дату рождения (ГГГГ-ММ-ДД) или «-».",
    "blacklist.report.prompt.city": "Укажите город или «-», если неизвестно.",
    "blacklist.report.prompt.reason": "Опишите суть жалобы (обязательно).",
    "blacklist.report.error.name": "Имя обязательно.",
    "blacklist.report.error.birthdate": "Дата должна быть в формате ГГГГ-ММ-ДД или «-».",
    "blacklist.report.error.reason": "Опишите причину жалобы.",
    "blacklist.report.success.created": "Создана новая запись в чёрном списке для {name}.",
    "blacklist.report.success.existing": "Жалоба добавлена к записи {name}.",
    "blacklist.report.success.complaint": "Номер жалобы: {complaint_id}.",
    "blacklist.appeal.prompt.name": "Введите имя для поиска записи (обязательно).",
    "blacklist.appeal.prompt.phone": "Укажите телефон или «-», если хотите пропустить шаг.",
    "blacklist.appeal.prompt.birthdate": "Укажите дату рождения (ГГГГ-ММ-ДД) или «-».",
    "blacklist.appeal.prompt.city": "Укажите город или «-», если хотите пропустить шаг.",
    "blacklist.appeal.prompt.reason": "Опишите аргументы апелляции (обязательно).",
    "blacklist.appeal.error.name": "Имя обязательно.",
    "blacklist.appeal.error.birthdate": "Дата должна быть в формате ГГГГ-ММ-ДД или «-».",
    "blacklist.appeal.error.reason": "Опишите причину апелляции.",
    "blacklist.appeal.not_found": "Запись с указанными параметрами не найдена.",
    "blacklist.appeal.success": "Апелляция по записи {name} зарегистрирована.",
    "blacklist.appeal.success.appeal": "Номер апелляции: {appeal_id}.",
    "blacklist.media.prompt": (
        "Если есть доказательства, отправьте до {limit} фото или видео по одному. "
        "Напишите «готово» или «пропустить», чтобы завершить."
    ),
    "blacklist.media.received": "Файл {filename} сохранён. Можно отправить ещё или написать «готово».",
    "blacklist.media.error.type": "Пожалуйста, отправьте фото или видео.",
    "blacklist.media.error.size": "Файл слишком большой. Максимум {limit} МБ.",
    "blacklist.media.error.upload": "Не удалось сохранить файл. Попробуйте ещё раз.",
    "blacklist.media.completed": "Приём вложений завершён. Спасибо!",
    "blacklist.media.limit": "Достигнут лимит в {limit} файлов.",
    "enforcement.placeholder": "Служба контроля исполнения в разработке. Мы сообщим о запуске.",

# Menus (main buttons and titles)
    "menu.back.main": "К главному меню",
    "menu.my_cases": "Мои дела",
    "menu.blacklist": "Чёрный список",
    "menu.knowledge": "Шариатские знания",
    "menu.committee": "Шариатский комитет",
    "menu.meetings_chats": "Совещания и чаты",
    "menu.enforcement": "Контроль исполнения",
    "menu.good_deeds": "Добрые дела",
    "menu.zakat": "Закят и садака",
    "menu.contracts": "Мои договоры",
    "menu.courts": "Мои суды",
    "menu.inheritance": "Наследство и завещания",
    "menu.holidays": "Мусульманские праздники",
    "menu.nikah": "Никах",
    "menu.spouse_search": "Знакомство",
    "menu.my_cases.title": "Выберите направление для работы с вашими делами.",
    "menu.blacklist.title": (
        "Раздел, где публикуются мусульмане, нарушившие договоры, "
        "не исполнившие решения или угнетающие мусульман."
    ),
    "menu.knowledge.title": "Раздел шариатских знаний. Выберите необходимый подраздел.",
    "menu.knowledge.topics.title": "Основы: подборки по основам веры, фикху и культуре.",
    "menu.committee.title": (
        "Центральный орган разбирательств и управления ботом.\n\n"
        "Здесь происходят:\n"
        "• Подтверждение и хранение договоров между мусульманами\n"
        "• Набор надёжных братьев-контролёров для исполнения решений\n"
        "• Установление и применение наказаний за отказ от исполнения\n"
        "• Контроль, организация и координация работы всей платформы\n"
        "• Поддержка прозрачности, справедливости и шариатского порядка\n\n"
        "Это сердце системы — для тех, кто стремится к истинной справедливости по шариату "
        "и объединению мусульман на основе договора, ответственности и братства."
    ),
    "menu.meetings_chats.title": "Совещания и общение. Выберите нужный формат.",
    "menu.meetings.title": "Совещания\nПредложите идею или участвуйте в голосовании общины.",
    "menu.good_deeds.title": "Добрые дела и инициативы.",
    "menu.inheritance.title": "Наследство и завещания.",
    "menu.holidays.title": "Мусульманские праздники.",
    "menu.nikah.title": "Никах.",
    "menu.spouse_search.title": "Знакомство и поиск супруга.",
    "menu.zakat.title": "Закят и садака.",
    "menu.enforcement.title": (
        "Фиксация исполнения или отказа от исполнения шариатских решений. "
        "Сбор доказательств и напоминаний."
    ),
    "menu.contracts.title": "Мои договоры.",
    "menu.courts.title": "Мои суды.",
    "menu.courts.statuses.title": "Статусы дел.",

    # Scheduler
    "command.scheduler.unavailable": "Планировщик недоступен.",
}

TEXTS_EN: Dict[str, str] = {
    # Welcome
    "welcome.new": "Welcome, {full_name}!",
    "welcome.back": "Welcome back, {full_name}!",
    # Registration
    "registration.intro": "To continue using the bot, please complete registration.",
    "registration.success": "Registration complete!",
    "registration.required": "To continue, please register by choosing a language below.",
    "registration.already": "You are already registered.",
    "registration.prompt.name": "Enter your full name.",
    "registration.error.name_invalid": "Please enter a valid name.",
    "registration.prompt.email": "Enter your email address.",
    "registration.error.email_invalid": "Please enter a valid email address.",
    "registration.prompt.phone": "Share your phone number in international format.",
    "registration.prompt.phone_retry": "Phone did not match. Please re-enter your number in international format.",
    "registration.error.phone_invalid": "Enter a valid phone number: 9–14 digits, optionally starting with +.",
    "registration.prompt.phone_contact": "Share your contact via the button below to verify your number.",
    "registration.error.phone_mismatch": "The phone number in the contact does not match the one you typed.",
    "registration.error.phone_contact_missing": "The shared contact does not contain a phone number.",
    "registration.error.phone_debug_mismatch": "Debug: you typed {typed}, contact has {contact}.",
    "registration.error.contact_expected": "Please press the \"Share contact\" button below.",
    "registration.button.share_contact": "Share contact",

    # Commands & meta
    "command.start.description": "Restart bot",
    "command.lang.description": "Change language",
    "command.help.description": "Show help",
    "bot.version.info": "Bot version: {version}",
    "help.message": "This is Sharia bot. Available commands: /start, /lang, /help.",

    # Settings dialog
    "language.menu.title": "Please choose the bot interface language",
    "language.back": "Back",
    "language.save": "Save",
    "language.saved": "Language settings have been saved!",

    # Misc
    "welcome.body": "Choose a section from the main menu.",
    "input.placeholder.question": "Describe your question…",
    "user.default_name": "User",
    "docs.default_name": "Document",
    "error.document.send": "Failed to send document: {name}",

    # AI
    "ai.system.prompt": (
        "🕌 ПРОМТ: Шариатский ассистент (только Shamela, арабский + перевод, без ссылок)"
        ""
        "Ты — исламский шариатский ассистент, который отвечает на вопросы исключительно на основе классических исламских книг, представленных в библиотеке Shamela."
        ""
        "📌 Главный принцип"
        ""
        "Ты не имеешь права использовать никакие источники, кроме текстов из Shamela."
        "Запрещено опираться на Википедию, современные сайты, личные мнения или неподтверждённые ответы."
        ""
        "---"
        ""
        "✅ Обязательный формат ответа"
        ""
        "1) Арабский оригинал (дословно из книги)"
        ""
        "Ты всегда приводишь оригинальный арабский текст:"
        ""
        "النص العربي: «…цитата…»"
        ""
        "---"
        ""
        "2) Точный перевод на язык вопроса"
        ""
        "Перевод должен быть на том языке, на котором пользователь задал вопрос"
        "(русский → русский перевод, английский → английский перевод, турецкий → турецкий перевод)."
        ""
        "Перевод: «…перевод…»"
        ""
        "---"
        ""
        "3) Полная библиографическая ссылка (без URL)"
        ""
        "После цитаты обязательно указывай:"
        ""
        "название книги"
        ""
        "имя автора"
        ""
        "раздел/глава (باب / فصل)"
        ""
        "том (الجزء)"
        ""
        "страница (الصفحة)"
        ""
        "номер вопроса (если есть)"
        ""
        "Пример:"
        ""
        "المصدر:"
        ""
        "الكتاب: المغни"
        ""
        "المؤلف: ابن قدامة"
        ""
        "الباب: كتاب الطهارة"
        ""
        "الجزء: 1"
        ""
        "الصفحة: 215"
        ""
        "---"
        ""
        "4) Разъяснение (только в рамках текста)"
        ""
        "Ты можешь кратко объяснить вывод, но без личных домыслов:"
        ""
        "Пояснение: Этот текст указывает, что…"
        ""
        "---"
        ""
        "5) Если есть разногласие — привести мнения"
        ""
        "Если вопрос спорный, приведи несколько цитат из Shamela:"
        ""
        "قول الحنفية: …"
        "قول المالكية: …"
        "قول الشافعية: …"
        "قول الحنابلة: …"
        ""
        "Каждое мнение — с арабской цитатой и переводом."
        ""
        "---"
        ""
        "❌ Запрещено"
        ""
        "давать ответ без арабской цитаты"
        ""
        "писать «учёные говорят» без источника"
        ""
        "вставлять ссылки на Shamela"
        ""
        "использовать любые сайты кроме Shamela"
        ""
        "выдавать фетву от себя"
        ""
        "сокращать ответы до общих слов"
        ""
        "---"
        ""
        "🧠 Если ответа нет в Shamela"
        ""
        "Ты обязан сказать:"
        ""
        "«В текстах Shamela не найден прямой однозначный ответ. Ниже приведены ближайшие связанные упоминания из классических книг…»"
        ""
        "И привести ближайшие тексты."
        ""
        "---"
        ""
        "📝 Стиль ответа"
        ""
        "Ответ должен быть:"
        ""
        "обширным"
        ""
        "строго академическим"
        ""
        "основанным на книгах фикха и хадиса"
        ""
        "с уважительным исламским языком"
        ""
        "---"
        ""
        "Пример ответа (шаблон)"
        ""
        "Вопрос: Можно ли объединять молитвы в пути?"
        ""
        "النص العربي: «…»"
        ""
        "Перевод: «…»"
        ""
        "المصدر:"
        ""
        "الكتاب: زاد المعاد"
        ""
        "المؤلف: ابن القيم"
        ""
        "الفصل: صلاة المسافر"
        ""
        "الجزء: 1"
        ""
        "الصفحة: 456"
    ),
    "ai.response.prefix": "🤖 AI answer:",
    "ai.response.footer": "If needed, we will forward the question to scholars.",
    "ai.error.unavailable": "AI is unavailable right now.",
    "ai.error.empty": "Empty response.",
    "ai.error.empty.trimmed": "Empty after filtering.",
    "ai.error.generic": "An error occurred generating the answer.",
    "ai.response.waiting": "Generating an answer…",

# Buttons & menus
    "button.back": "Back",
    "button.cancel": "Cancel",
    "button.materials": "Materials",
    "button.ask.scholars": "Ask scholars",
    "button.community.support": "Support community",
    "button.holiday.ask_ai": "Ask AI",
    "button.holiday.download": "Download document",
    "button.answer.user": "Answer user",
    "button.profile.open": "Profile",
    "button.my_cases.contracts": "My contracts",
    "button.my_cases.courts": "My courts",
    "button.my_cases.inheritance": "Inheritance & wills",
    "button.my_cases.nikah": "Nikah",
    "button.my_cases.spouse_search": "🌿 Spouse search",
    "button.spouse.profile": "📝 My profile",
    "button.spouse.search": "🔎 Search",
    "button.spouse.requests": "📨 My requests",
    "button.spouse.rules": "🛡 Rules & protection",
    "button.spouse.ask": "❓ Ask scholars",
    "button.nikah.new": "📝 Create a new Nikah",
    "button.nikah.my": "📄 My marriages",
    "button.nikah.rules": "🕋 Nikah rules",
    "button.nikah.ask": "❓ Ask scholars",
    "button.blacklist.view": "View list",
    "button.blacklist.search": "Search",
    "button.blacklist.report": "Report",
    "button.blacklist.appeal": "Appeal",
    "button.knowledge.foundation": "Foundations",
    "button.knowledge.holidays": "Islamic holidays",
    "button.meetings.open": "Meetings",
    "button.chat.men": "Men’s chat",
    "button.chat.women": "Women’s chat",
    "button.enforcement.open": "Open",

    # Contract flow
    "contracts.create.menu.title": "Create a contract",
    "contracts.create.option.templates": "Choose from templates",
    "contracts.create.option.upload": "Upload a file",
    "contracts.none": "No templates available.",
    "contracts.saved": "Contract saved.",
    "contracts.search.found": "Templates found.",
    "contracts.search.none": "No templates found.",
    "contracts.search.prompt": "Enter a topic or template name.",
    "contracts.sent": "Contract sent.",
    "contracts.flow.party.approve": "✅ Approve",
    "contracts.flow.party.changes": "✍️ Request changes",
    "contracts.flow.party.sign": "✅ Sign contract",
    "contracts.flow.party.comment.prompt": "Describe what needs to be changed in the contract.",
    "contracts.flow.party.thanks": "Thanks! Your response has been sent to the contract author.",
    "contracts.flow.party.approved.notice": "User {party} approved the contract.",
    "contracts.flow.party.changes.notice": "User {party} requested changes: {comment}",
    "contracts.flow.party.signed.notice": "User {party} signed the contract.",
    "contracts.list.title": "Your contracts:",
    "contracts.title.unknown": "Contract",
    "contracts.list.item": "📄 {title}\nStatus: {status}\nDate: {date}\nCounterparty: {party}",
    "contracts.list.party.unknown": "Not specified",
    "contracts.status.draft": "Draft",
    "contracts.status.confirmed": "Generated",
    "contracts.status.sent_to_party": "Sent to party",
    "contracts.status.party_approved": "Approved by party",
    "contracts.status.party_changes_requested": "Changes requested",
    "contracts.status.sent_to_scholar": "Sent to scholar",
    "contracts.status.scholar_send_failed": "Scholar send failed",
    "contracts.status.signed": "Signed",
    "contracts.status.sent": "Sent",
    "contracts.edit.not_allowed": "Editing is not available for this contract status.",
    "contracts.stats.info": "Templates statistics.",
    "contracts.template.coming_soon": "Coming soon.",
    "contracts.template.download": "Download template",
    "contracts.template.missing": "Template unavailable.",
    "contracts.template.start": "Start with templates",
    "contracts.flow.placeholder.prompt": "Enter a value for: {field}",
    "contracts.flow.field.required": "This field is required.",
    "contracts.flow.actions.title": "Choose an action",
    "contracts.flow.button.download_txt": "⬇️ Download text (txt)",
    "contracts.flow.button.download_pdf": "⬇️ Download PDF",
    "contracts.flow.button.send_other": "📤 Send to the other party",
    "contracts.flow.button.send_scholar": "🕌 Send to scholar",
    "contracts.flow.button.send_court": "⚖️ Send to court",
    "contracts.flow.send_court.not_signed": "You can send the case to court only after both parties sign it.",
    "contracts.flow.button.delete": "🗑 Delete contract",
    "contracts.flow.button.back_actions": "↩️ Back to actions",
    "contracts.delete.done": "Contract deleted.",
    "contracts.flow.preview.too_long": "Text is too long. Use the download buttons.",
    "contracts.flow.template.empty": "Template is empty.",
    "contracts.flow.pdf.failed": "Failed to generate PDF.",
    "contracts.flow.send_other.prompt": "Enter @username or Telegram ID of the recipient.",
    "contracts.flow.send_other.pick_contact": "Or choose a contact:",
    "contracts.flow.send_other.invalid": "Invalid format. Use @username or numeric ID.",
    "contracts.flow.send_other.not_found": "No user found with that name. Use @username or Telegram ID.",
    "contracts.flow.send_other.ambiguous": "Multiple users found with that name. Use @username or Telegram ID.",
    "contracts.flow.send_other.message": "Contract from {sender}.",
    "contracts.flow.send_other.sent": "Contract sent to {recipient}.",
    "contracts.flow.send_other.failed": "Failed to send the contract. The recipient must start the bot or allow messages.",
    "contracts.flow.button.pick_contact": "📇 Pick a contact",
    "contracts.invite.code": "The counterparty is not registered yet. Share this link:\n{invite_link}",
    "contracts.invite.code.only": "The counterparty is not registered yet. Share this code: {invite_code}",
    "contracts.invite.self": "This is your contract.",
    "contracts.invite.used": "This invite has already been used.",
    "contracts.invite.joined": "You joined the contract \"{title}\".",
    "contracts.invite.owner_notice": "The counterparty joined the contract \"{title}\".",
    "contracts.flow.party.comment.prompt": "Describe what needs to be changed in the contract.",
    "contracts.flow.party.thanks": "Thanks! Your response has been sent to the contract author.",
    "contracts.flow.send_scholar.sent": "Contract sent to scholar.",
    "contracts.flow.send_scholar.failed": "Failed to send contract to scholar.",
    "contracts.flow.title": "Create contract",
    "contracts.flow.ready": "Data for contract \"{contract}\" collected. Generate the contract?",
    "contracts.flow.confirmed": "Contract saved.",
    "contracts.flow.button.generate": "Generate contract",
    "contracts.flow.button.confirm": "Confirm and save",
    "contracts.flow.button.edit": "Details",
    "contracts.flow.button.skip": "Skip",
    "contracts.flow.choice.required": "Please select a button option.",
    "contracts.flow.choice.yes": "Yes",
    "contracts.flow.choice.no": "No",
    "contracts.flow.choice.ijara.damage.tenant": "Tenant fault",
    "contracts.flow.choice.ijara.damage.agreement": "By agreement",
    "contracts.flow.choice.istisna.materials.customer": "Customer materials",
    "contracts.flow.choice.istisna.materials.contractor": "Contractor materials",
    "contracts.flow.choice.bay.condition.new": "New",
    "contracts.flow.choice.bay.condition.used": "Used",
    "contracts.flow.choice.bay.payment.before": "Before delivery",
    "contracts.flow.choice.bay.payment.after": "After delivery",
    "contracts.flow.choice.bay.payment.installments": "Installments",
    "contracts.flow.choice.bay.payment.deferred": "Deferred payment",
    "contracts.flow.type.qard": "💸 Qard Hasan (interest-free loan)",
    "contracts.flow.type.ijara": "🏠 Ijara (rent)",
    "contracts.flow.type.salam": "🚚 Salam (advance payment)",
    "contracts.flow.type.istisna": "🛠 Istisna (manufacturing)",
    "contracts.flow.type.bay": "💼 Bay' (sale/purchase)",
    "contracts.flow.type.musharaka": "👥 Musharaka (partnership)",
    "contracts.flow.type.mudaraba": "📊 Mudaraba (investment)",
    "contracts.flow.type.hiba": "🎁 Hiba (gift)",
    "contracts.flow.type.amana": "📦 Amana (storage)",
    "contracts.flow.type.kafala": "🛡 Kafala (guarantee)",
    "contracts.flow.type.sulh": "⚖️ Sulh (settlement)",
    "contracts.flow.type.installment": "💳 Installment sale",
    "contracts.flow.type.murabaha": "📦 Murabaha (markup)",
    "contracts.flow.type.rahn": "📌 Rahn (pledge)",
    "contracts.flow.type.hawala": "🔁 Hawala (debt transfer)",
    "contracts.flow.type.inan": "🤝 Inan (joint participation)",
    "contracts.flow.type.wakala": "🧾 Wakala (agency)",
    "contracts.flow.type.sadaqa": "💞 Sadaqa (charity)",
    "contracts.flow.type.ariya": "🪙 Ariya (temporary use)",
    "contracts.flow.type.waqf": "🏛 Waqf (endowment)",
    "contracts.flow.type.wasiya": "📝 Wasiya (bequest)",
    "contracts.flow.type.nikah": "💍 Nikah (marriage)",
    "contracts.flow.type.talaq": "🕊 Talaq (divorce)",
    "contracts.flow.type.khul": "🕊 Khul (divorce by wife)",
    "contracts.flow.type.ridaa": "👶 Ridaa (nursing)",
    "contracts.flow.type.uaria": "🪙 Uaria (temporary loan of property)",
    "contracts.flow.qard.lender_name": "Lender name",
    "contracts.flow.qard.lender_document": "Lender document / registration",
    "contracts.flow.qard.lender_address": "Lender address",
    "contracts.flow.qard.lender_contact": "Lender contact details",
    "contracts.flow.qard.borrower_name": "Borrower name",
    "contracts.flow.qard.borrower_document": "Borrower document / registration",
    "contracts.flow.qard.borrower_address": "Borrower address",
    "contracts.flow.qard.borrower_contact": "Borrower contact details",
    "contracts.flow.qard.amount": "Amount",
    "contracts.flow.qard.purpose": "Loan purpose",
    "contracts.flow.qard.due_date": "Due date (date or text)",
    "contracts.flow.qard.repayment_method": "Repayment method",
    "contracts.flow.qard.collateral_required": "Is there collateral?",
    "contracts.flow.qard.collateral_description": "Collateral description",
    "contracts.flow.qard.extra_terms": "Additional terms (optional)",
    "contracts.flow.ijara.landlord": "Landlord",
    "contracts.flow.ijara.landlord_document": "Landlord document / registration",
    "contracts.flow.ijara.landlord_address": "Landlord address",
    "contracts.flow.ijara.landlord_contact": "Landlord contact details",
    "contracts.flow.ijara.tenant": "Tenant",
    "contracts.flow.ijara.tenant_document": "Tenant document / registration",
    "contracts.flow.ijara.tenant_address": "Tenant address",
    "contracts.flow.ijara.tenant_contact": "Tenant contact details",
    "contracts.flow.ijara.object": "Lease object",
    "contracts.flow.ijara.object_details": "Quantity, characteristics",
    "contracts.flow.ijara.object_condition": "Asset condition",
    "contracts.flow.ijara.term": "Term",
    "contracts.flow.ijara.price": "Price",
    "contracts.flow.ijara.currency": "Payment currency",
    "contracts.flow.ijara.payment_order": "Payment schedule",
    "contracts.flow.ijara.damage_responsibility": "Damage responsibility",
    "contracts.flow.ijara.additional_terms": "Additional terms (optional)",
    "contracts.flow.choice.ijara.payment.monthly": "Monthly",
    "contracts.flow.choice.ijara.payment.one_time": "One-time",
    "contracts.flow.choice.ijara.payment.other": "By other agreement",
    "contracts.flow.salam.buyer": "Buyer",
    "contracts.flow.salam.buyer_document": "Buyer document / registration",
    "contracts.flow.salam.buyer_address": "Buyer address",
    "contracts.flow.salam.buyer_contact": "Buyer contact details",
    "contracts.flow.salam.supplier": "Supplier",
    "contracts.flow.salam.supplier_document": "Seller document / registration",
    "contracts.flow.salam.supplier_address": "Seller address",
    "contracts.flow.salam.supplier_contact": "Seller contact details",
    "contracts.flow.salam.goods": "Goods description",
    "contracts.flow.salam.goods_name": "Goods name",
    "contracts.flow.salam.goods_quality": "Kind / grade / quality",
    "contracts.flow.salam.goods_quantity": "Quantity (Sharia measures)",
    "contracts.flow.salam.goods_packaging": "Packaging / characteristics",
    "contracts.flow.salam.delivery_date": "Delivery date",
    "contracts.flow.salam.fixed_price": "Fixed price",
    "contracts.flow.salam.delivery_place": "Delivery place",
    "contracts.flow.istisna.customer": "Customer",
    "contracts.flow.istisna.customer_document": "Customer document / registration",
    "contracts.flow.istisna.customer_address": "Customer address",
    "contracts.flow.istisna.customer_contact": "Customer contact details",
    "contracts.flow.istisna.contractor": "Contractor",
    "contracts.flow.istisna.contractor_document": "Contractor document / registration",
    "contracts.flow.istisna.contractor_address": "Contractor address",
    "contracts.flow.istisna.contractor_contact": "Contractor contact details",
    "contracts.flow.istisna.product": "Product to manufacture",
    "contracts.flow.istisna.product_name": "Product name",
    "contracts.flow.istisna.product_materials": "Material(s)",
    "contracts.flow.istisna.product_dimensions": "Dimensions / volume / characteristics",
    "contracts.flow.istisna.product_quality": "Quality / standard",
    "contracts.flow.istisna.product_quantity": "Quantity",
    "contracts.flow.istisna.term": "Term",
    "contracts.flow.istisna.materials": "Materials owner",
    "contracts.flow.istisna.price": "Price",
    "contracts.flow.istisna.payment_schedule": "Payment schedule",
    "contracts.flow.istisna.start_date": "Production start date",
    "contracts.flow.istisna.delivery_place": "Delivery place",
    "contracts.flow.bay.seller": "Seller",
    "contracts.flow.bay.seller_document": "Seller document / registration",
    "contracts.flow.bay.seller_address": "Seller address",
    "contracts.flow.bay.seller_contact": "Seller contact details",
    "contracts.flow.bay.buyer": "Buyer",
    "contracts.flow.bay.buyer_document": "Buyer document / registration",
    "contracts.flow.bay.buyer_address": "Buyer address",
    "contracts.flow.bay.buyer_contact": "Buyer contact details",
    "contracts.flow.bay.goods": "Goods",
    "contracts.flow.bay.goods_details": "Quantity, characteristics",
    "contracts.flow.bay.condition": "Goods condition",
    "contracts.flow.bay.price": "Price",
    "contracts.flow.bay.payment_timing": "Payment timing",
    "contracts.flow.installment.seller": "Seller",
    "contracts.flow.installment.buyer": "Buyer",
    "contracts.flow.installment.goods": "Goods description",
    "contracts.flow.installment.goods_details": "Quantity, characteristics",
    "contracts.flow.installment.goods_condition": "Goods condition",
    "contracts.flow.installment.total_price": "Total price",
    "contracts.flow.installment.currency": "Payment currency",
    "contracts.flow.installment.down_payment": "Down payment",
    "contracts.flow.installment.count": "Number of payments",
    "contracts.flow.installment.amount": "Payment amount",
    "contracts.flow.installment.schedule": "Payment schedule",
    "contracts.flow.installment.delivery_term": "Delivery term",
    "contracts.flow.murabaha.seller": "Seller",
    "contracts.flow.murabaha.buyer": "Buyer",
    "contracts.flow.murabaha.goods": "Goods description",
    "contracts.flow.murabaha.cost_price": "Cost price",
    "contracts.flow.murabaha.markup": "Markup",
    "contracts.flow.murabaha.final_price": "Final price",
    "contracts.flow.murabaha.currency": "Payment currency",
    "contracts.flow.murabaha.payment_schedule": "Payment schedule",
    "contracts.flow.murabaha.delivery_term": "Delivery term",
    "contracts.flow.bay.currency": "Payment currency",
    "contracts.flow.bay.delivery_term": "Delivery term",
    "contracts.flow.bay.khiyar_term": "Khiyar ash-shart term (if any)",
    "contracts.flow.musharaka.partner1_contribution": "Partner 1 contribution",
    "contracts.flow.musharaka.partner2_contribution": "Partner 2 contribution",
    "contracts.flow.musharaka.profit_split": "Profit split (%)",
    "contracts.flow.musharaka.partner1_name": "Partner 1",
    "contracts.flow.musharaka.partner2_name": "Partner 2",
    "contracts.flow.musharaka.business_description": "Project description",
    "contracts.flow.musharaka.loss_share": "Loss sharing",
    "contracts.flow.musharaka.management_roles": "Roles and management",
    "contracts.flow.musharaka.duration": "Partnership term",
    "contracts.flow.mudaraba.investor": "Investor",
    "contracts.flow.mudaraba.manager": "Manager",
    "contracts.flow.mudaraba.capital": "Capital amount",
    "contracts.flow.mudaraba.profit_investor": "Investor profit share (%)",
    "contracts.flow.mudaraba.profit_manager": "Manager profit share (%)",
    "contracts.flow.mudaraba.business_description": "Project description",
    "contracts.flow.mudaraba.duration": "Project term",
    "contracts.flow.mudaraba.profit_distribution": "Profit distribution terms",
    "contracts.flow.mudaraba.loss_terms": "Loss terms",
    "contracts.flow.inan.partner1_name": "Partner 1",
    "contracts.flow.inan.partner2_name": "Partner 2",
    "contracts.flow.inan.business_description": "Project description",
    "contracts.flow.inan.partner1_contribution": "Partner 1 contribution",
    "contracts.flow.inan.partner2_contribution": "Partner 2 contribution",
    "contracts.flow.inan.profit_split": "Profit split",
    "contracts.flow.inan.management_roles": "Roles and management",
    "contracts.flow.inan.duration": "Partnership term",
    "contracts.flow.wakala.principal": "Principal",
    "contracts.flow.wakala.agent": "Agent",
    "contracts.flow.wakala.scope": "Scope of authority",
    "contracts.flow.wakala.fee": "Agency fee",
    "contracts.flow.wakala.duration": "Term",
    "contracts.flow.wakala.reporting_terms": "Reporting terms",
    "contracts.flow.wakala.termination_terms": "Termination terms",
    "contracts.flow.hiba.donor": "Donor",
    "contracts.flow.hiba.recipient": "Recipient",
    "contracts.flow.hiba.gift": "Gift description",
    "contracts.flow.hiba.return_condition": "Is there a return condition?",
    "contracts.flow.sadaqa.donor": "Donor",
    "contracts.flow.sadaqa.beneficiary": "Beneficiary",
    "contracts.flow.sadaqa.description": "Donation description",
    "contracts.flow.sadaqa.amount": "Donation amount",
    "contracts.flow.sadaqa.purpose": "Donation purpose",
    "contracts.flow.sadaqa.transfer_method": "Transfer method",
    "contracts.flow.ariya.lender": "Lender",
    "contracts.flow.ariya.borrower": "Borrower",
    "contracts.flow.ariya.item_description": "Item description",
    "contracts.flow.ariya.use_term": "Use term",
    "contracts.flow.ariya.return_condition": "Return condition",
    "contracts.flow.ariya.liability_terms": "Liability terms",
    "contracts.flow.waqf.founder": "Founder",
    "contracts.flow.waqf.manager": "Manager (mutawalli)",
    "contracts.flow.waqf.asset": "Waqf asset",
    "contracts.flow.waqf.purpose": "Waqf purpose",
    "contracts.flow.waqf.beneficiaries": "Beneficiaries",
    "contracts.flow.waqf.management_conditions": "Management conditions",
    "contracts.flow.wasiya.testator": "Testator",
    "contracts.flow.wasiya.beneficiary": "Beneficiary",
    "contracts.flow.wasiya.executor": "Executor",
    "contracts.flow.wasiya.description": "Bequest description",
    "contracts.flow.wasiya.conditions": "Bequest conditions",
    "contracts.flow.amana.owner": "Owner",
    "contracts.flow.amana.custodian": "Custodian",
    "contracts.flow.amana.asset": "Asset description",
    "contracts.flow.amana.term": "Storage term",
    "contracts.flow.amana.storage_conditions": "Storage conditions",
    "contracts.flow.amana.custodian_liability": "Custodian liability",
    "contracts.flow.amana.return_terms": "Return terms",
    "contracts.flow.uaria.lender": "Lender",
    "contracts.flow.uaria.borrower": "Borrower",
    "contracts.flow.uaria.item_description": "Item description",
    "contracts.flow.uaria.use_term": "Use term",
    "contracts.flow.uaria.return_condition": "Return condition",
    "contracts.flow.uaria.liability_terms": "Liability terms",
    "contracts.flow.kafala.guarantor": "Guarantor",
    "contracts.flow.kafala.debtor": "Debtor",
    "contracts.flow.kafala.creditor": "Creditor",
    "contracts.flow.kafala.obligation": "Obligation",
    "contracts.flow.kafala.term": "Guarantee term",
    "contracts.flow.rahn.pledger": "Pledger",
    "contracts.flow.rahn.pledgee": "Pledgee",
    "contracts.flow.rahn.asset": "Pledged asset",
    "contracts.flow.rahn.asset_value": "Asset value",
    "contracts.flow.rahn.debt_amount": "Secured debt amount",
    "contracts.flow.rahn.debt_due_date": "Debt due date",
    "contracts.flow.rahn.storage_terms": "Storage terms",
    "contracts.flow.rahn.redemption_terms": "Redemption terms",
    "contracts.flow.hawala.transferor": "Transferor",
    "contracts.flow.hawala.new_debtor": "New debtor",
    "contracts.flow.hawala.transferee": "Creditor",
    "contracts.flow.hawala.debt_amount": "Debt amount",
    "contracts.flow.hawala.debt_currency": "Debt currency",
    "contracts.flow.hawala.due_date": "Due date",
    "contracts.flow.hawala.transfer_terms": "Transfer terms",
    "contracts.flow.sulh.side_a": "Party A",
    "contracts.flow.sulh.side_b": "Party B",
    "contracts.flow.sulh.dispute": "Dispute essence",
    "contracts.flow.sulh.resolution": "Proposed resolution",
    "contracts.flow.sulh.waive_claims": "Do parties waive claims?",
    "contracts.flow.sulh.party_one_name": "Party 1: name / organization",
    "contracts.flow.sulh.party_one_document": "Party 1: document / registration",
    "contracts.flow.sulh.party_one_address": "Party 1: address",
    "contracts.flow.sulh.party_one_contact": "Party 1: contact details",
    "contracts.flow.sulh.party_two_name": "Party 2: name / organization",
    "contracts.flow.sulh.party_two_document": "Party 2: document / registration",
    "contracts.flow.sulh.party_two_address": "Party 2: address",
    "contracts.flow.sulh.party_two_contact": "Party 2: contact details",
    "contracts.flow.sulh.dispute_subject": "Dispute / conflict subject",
    "contracts.flow.sulh.proposed_resolution": "Proposed resolution",
    "contracts.flow.sulh.claims_waived": "Do parties waive claims?",
    "contracts.flow.nikah.groom": "Groom",
    "contracts.flow.nikah.bride": "Bride",
    "contracts.flow.nikah.wali": "Wali (guardian of the bride)",
    "contracts.flow.nikah.mahr": "Mahr",
    "contracts.flow.nikah.witnesses": "Witnesses",
    "contracts.flow.nikah.date_place": "Date and place",
    "contracts.flow.nikah.additional_terms": "Additional terms",
    "contracts.flow.talaq.husband": "Husband",
    "contracts.flow.talaq.wife": "Wife",
    "contracts.flow.talaq.date": "Talaq date",
    "contracts.flow.talaq.iddah_terms": "Iddah terms",
    "contracts.flow.talaq.rights_settlement": "Rights settlement",
    "contracts.flow.khul.wife": "Wife",
    "contracts.flow.khul.husband": "Husband",
    "contracts.flow.khul.compensation": "Compensation (fidya)",
    "contracts.flow.khul.date": "Agreement date",
    "contracts.flow.khul.additional_terms": "Additional terms",
    "contracts.flow.ridaa.nurse": "Nursing woman",
    "contracts.flow.ridaa.child": "Child",
    "contracts.flow.ridaa.guardian": "Child's guardian",
    "contracts.flow.ridaa.period": "Feeding period",
    "contracts.flow.ridaa.compensation": "Compensation",
    "contracts.flow.ridaa.additional_terms": "Additional terms",
    "contracts.validation.riba": "⚠️ Interest, benefit, or riba is forbidden. Remove the clause.",
    "contracts.validation.unclear_terms": "⚠️ Terms must be specific. Please clarify.",
    "contracts.validation.haram_goods": "⚠️ This item is haram.",
    "contracts.validation.price_fixed": "⚠️ Price must be fixed in advance.",
    "contracts.validation.profit_guarantee": "⚠️ Profit cannot be guaranteed in Sharia.",
    "contracts.validation.hiba_return_forbidden": "⚠️ Return condition is forbidden for hiba.",
    "contracts.validation.percent_invalid": "Enter valid percentages (e.g., 60/40 or 50%).",
    "contracts.auto.button": "🤖 Auto-pick",
    "contracts.auto.question.intent": "What do you want to arrange?",
    "contracts.auto.question.money": "Is there money involved?",
    "contracts.auto.question.money_kind": "Choose the money deal type",
    "contracts.auto.question.goods": "Is there a product?",
    "contracts.auto.question.investment": "Choose partnership type",
    "contracts.auto.option.family": "Family",
    "contracts.auto.option.money": "Money",
    "contracts.auto.option.purchase": "Purchase",
    "contracts.auto.option.work": "Work",
    "contracts.auto.option.rent": "Rent",
    "contracts.auto.option.storage": "Storage",
    "contracts.auto.option.gift": "Gift",
    "contracts.auto.option.guarantee": "Guarantee",
    "contracts.auto.option.settlement": "Settlement",
    "contracts.auto.option.loan": "Loan",
    "contracts.auto.option.investment": "Investment",
    "contracts.auto.option.goods_now": "Available now",
    "contracts.auto.option.goods_later": "Later (money now)",
    "contracts.auto.option.goods_custom": "Custom manufacture",
    "contracts.auto.option.goods_none": "No goods",
    "contracts.auto.result": "Recommended contract: {contract}. Create it?",
    "contracts.auto.family": "Family contracts are in Nikah/Wasiya sections.",
    "contracts.auto.unsupported": "Could not auto-pick a contract. Choose manually.",
    "contracts.auto.button.confirm": "Yes",
    "contracts.auto.button.restart": "Change answers",
    "contracts.templates.choose_category": "Choose a category",
    "contracts.templates.choose_contract": "Choose a template",
    "contracts.templates.select_action": "Choose an action",
    "contracts.title.prompt": "Contract title",
    "contracts.upload.prompt": "Upload a PDF file",

    # Courts
    "courts.file.instructions": "Attach a PDF file of your claim.",
    "courts.info.closed": "Case closed.",
    "courts.info.in_progress": "Case in progress.",
    "courts.info.opened": "Case opened.",

    # Docs
    "docs.empty": "No materials yet.",
    "docs.searching": "Searching materials…",
    "docs.holiday.searching": "Searching holiday materials…",
    "holiday.ai.default_question": "Holiday congratulations and advice",
    "holiday.description.template": "Prepared material for the holiday.",
    "holiday.document.missing": "Document not found.",

    # Errors & notifications
    "error.request.invalid": "Invalid request.",
    "error.answer.recipient_unknown": "Recipient unknown.",
    "answer.delivery.failed": "Failed to deliver answer.",
    "answer.sent.confirmation": "Answer sent.",
    "notify.answer.user": "Answer has been sent to the user.",
    "notify.question.forward": "Question forwarded for review.",

    # Contracts validation errors
    "error.contracts.file.only_pdf": "Only PDF is allowed.",
    "error.contracts.file.required_pdf": "PDF file is required.",
    "error.contracts.file.too_large": "File is too large.",
    "error.contracts.name.empty": "Enter a title.",
    "error.contracts.name.missing_state": "Invalid state.",
    "error.contracts.name.too_long": "Title is too long.",
    "error.contracts.search.empty": "Enter a search query.",

# Questions
    "question.prompt": "Describe your question.",
    "question.sent": "Question sent.",
    "question.failed": "Failed to send question.",
    "question.empty": "Empty question.",

    # Blacklist & enforcement
    "blacklist.view.header": "Latest blacklist entries",
    "blacklist.view.empty": "The blacklist is currently empty.",
    "blacklist.view.more": "Showing the first entries. {count} more remaining.",
    "blacklist.error.backend_unavailable": "Backend is unavailable. Please try again later.",
    "blacklist.error.generic": "Request failed. Please try again later.",
    "blacklist.error.validation": "Some fields failed validation. Check the data and try again.",
    "blacklist.field.empty": "not specified",
    "blacklist.field.date_format": "%Y-%m-%d",
    "blacklist.entry.status.active": "active",
    "blacklist.entry.status.inactive": "inactive",
    "blacklist.entry.template": (
        "• {name}\n"
        "  Status: {status}\n"
        "  City: {city}\n"
        "  Phone: {phone}\n"
        "  Birthdate: {birthdate}\n"
        "  Complaints: {complaints}, appeals: {appeals}\n"
        "  Updated: {added}"
    ),
    "blacklist.common.cancel_hint": "Send “cancel” to abort.",
    "blacklist.common.cancelled": "Input cancelled.",
    "blacklist.search.prompt": (
        "Enter a query as “Name;City;YYYY-MM-DD”. City and birthdate are optional."
    ),
    "blacklist.search.error.empty": "Please provide a name to search.",
    "blacklist.search.error.birthdate": "Birthdate must use YYYY-MM-DD format.",
    "blacklist.search.results.empty": "No matching records found.",
    "blacklist.report.prompt.name": "Enter the offender’s name (required).",
    "blacklist.report.prompt.phone": "Provide a phone number or “-” if unknown.",
    "blacklist.report.prompt.birthdate": "Provide birthdate (YYYY-MM-DD) or “-”.",
    "blacklist.report.prompt.city": "Provide a city or “-” to skip.",
    "blacklist.report.prompt.reason": "Describe the complaint (required).",
    "blacklist.report.error.name": "Name is required.",
    "blacklist.report.error.birthdate": "Birthdate must use YYYY-MM-DD or “-”.",
    "blacklist.report.error.reason": "Please describe the complaint.",
    "blacklist.report.success.created": "A new blacklist entry was created for {name}.",
    "blacklist.report.success.existing": "Complaint attached to the existing entry {name}.",
    "blacklist.report.success.complaint": "Complaint ID: {complaint_id}.",
    "blacklist.appeal.prompt.name": "Enter the name to locate the entry (required).",
    "blacklist.appeal.prompt.phone": "Provide a phone number or “-” to skip.",
    "blacklist.appeal.prompt.birthdate": "Provide birthdate (YYYY-MM-DD) or “-”.",
    "blacklist.appeal.prompt.city": "Provide a city or “-” to skip.",
    "blacklist.appeal.prompt.reason": "Describe your appeal arguments (required).",
    "blacklist.appeal.error.name": "Name is required.",
    "blacklist.appeal.error.birthdate": "Birthdate must use YYYY-MM-DD or “-”.",
    "blacklist.appeal.error.reason": "Please describe the appeal.",
    "blacklist.appeal.not_found": "No entry found with the provided details.",
    "blacklist.appeal.success": "Appeal for {name} has been recorded.",
    "blacklist.appeal.success.appeal": "Appeal ID: {appeal_id}.",
    "blacklist.media.prompt": (
        "If you have supporting photos or videos, send up to {limit} files one by one. "
        "Type \"done\" when finished or \"skip\" to continue without attachments."
    ),
    "blacklist.media.received": "File {filename} saved. You can send another or type \"done\".",
    "blacklist.media.error.type": "Please send a photo or video.",
    "blacklist.media.error.size": "File is too large. Limit is {limit} MB.",
    "blacklist.media.error.upload": "Failed to save the file. Try again.",
    "blacklist.media.completed": "Attachments saved. Thank you!",
    "blacklist.media.limit": "You reached the limit of {limit} files.",
    "enforcement.placeholder": "The enforcement control module is in development. Stay tuned.",

# Menus (main buttons and titles)
    "menu.back.main": "Back to main menu",
    "menu.my_cases": "My cases",
    "menu.blacklist": "Blacklist",
    "menu.knowledge": "Sharia knowledge",
    "menu.committee": "Sharia committee",
    "menu.meetings_chats": "Meetings & chats",
    "menu.enforcement": "Enforcement control",
    "menu.good_deeds": "Good deeds",
    "menu.zakat": "Zakat & sadaqah",
    "menu.contracts": "My contracts",
    "menu.courts": "My courts",
    "menu.inheritance": "Inheritance & wills",
    "menu.holidays": "Islamic holidays",
    "menu.nikah": "Nikah",
    "menu.spouse_search": "Spouse search",
    "menu.my_cases.title": "Choose how you want to work with your personal cases.",
    "menu.blacklist.title": (
        "A section that lists Muslims who violated contracts, ignored rulings, "
        "or oppress fellow Muslims."
    ),
    "menu.knowledge.title": "Knowledge hub. Pick a subsection.",
    "menu.knowledge.topics.title": "Foundations: collections on creed, fiqh, and culture.",
    "menu.committee.title": (
        "The central body for dispute resolution and platform governance.\n\n"
        "Here we:\n"
        "• Confirm and store contracts between Muslims\n"
        "• Recruit reliable brothers as enforcers of rulings\n"
        "• Define and apply penalties for refusing compliance\n"
        "• Coordinate, organise, and supervise the entire platform\n"
        "• Uphold transparency, justice, and Sharia order\n\n"
        "This is the heart of the system for those pursuing genuine Sharia justice "
        "and unity through covenants, responsibility, and brotherhood."
    ),
    "menu.meetings_chats.title": "Meetings and communication. Pick the format you need.",
    "menu.meetings.title": "Meetings\nSuggest an idea or vote with the community.",
    "menu.good_deeds.title": "Good deeds and initiatives.",
    "menu.inheritance.title": "Inheritance and wills.",
    "menu.holidays.title": "Islamic holidays.",
    "menu.nikah.title": "Nikah.",
    "menu.spouse_search.title": "Spouse search.",
    "menu.zakat.title": "Zakat & sadaqah.",
    "menu.enforcement.title": (
        "Recording fulfilment or refusal of Sharia rulings. Evidence collection and reminders."
    ),
    "menu.contracts.title": "My contracts.",
    "menu.courts.title": "My courts.",
    "menu.courts.statuses.title": "Case statuses.",

    # Scheduler
    "command.scheduler.unavailable": "Scheduler is unavailable.",
}

TEXTS_AR: Dict[str, str] = {
    # Welcome
    "welcome.new": "مرحباً بك، {full_name}!",
    "welcome.back": "مرحباً بعودتك، {full_name}!",
    # Registration
    "registration.intro": "لمتابعة استخدام البوت يجب إتمام التسجيل.",
    "registration.success": "تم إكمال التسجيل!",
    "registration.required": "للمتابعة يرجى التسجيل باختيار اللغة أدناه.",
    "registration.already": "أنت مسجل بالفعل.",
    "registration.prompt.name": "أدخل اسمك الكامل.",
    "registration.error.name_invalid": "يرجى إدخال اسم صالح.",
    "registration.prompt.email": "أدخل بريدك الإلكتروني.",
    "registration.error.email_invalid": "يرجى إدخال بريد إلكتروني صالح.",
    "registration.prompt.phone": "أدخل رقم هاتفك بصيغة دولية.",
    "registration.prompt.phone_retry": "الرقم غير متطابق. يرجى إعادة إدخال الرقم بصيغة دولية.",
    "registration.error.phone_invalid": "أدخل رقماً صحيحاً: من 9 إلى 14 رقماً، ويمكن أن يبدأ بـ +.",
    "registration.prompt.phone_contact": "شارك جهة الاتصال عبر الزر أدناه لتأكيد الرقم.",
    "registration.error.phone_mismatch": "رقم الهاتف في جهة الاتصال لا يطابق الرقم المُدخل.",
    "registration.error.phone_contact_missing": "جهة الاتصال المرسلة لا تحتوي على رقم هاتف.",
    "registration.error.phone_debug_mismatch": "تصحيح: أدخلت {typed}، وفي جهة الاتصال {contact}.",
    "registration.error.contact_expected": "يرجى الضغط على زر \"إرسال جهة الاتصال\" أدناه.",
    "registration.button.share_contact": "إرسال جهة الاتصال",

    # Commands & meta
    "command.start.description": "إعادة تشغيل البوت",
    "command.lang.description": "تغيير اللغة",
    "command.help.description": "عرض المساعدة",
    "bot.version.info": "إصدار البوت: {version}",
    "help.message": "هذا بوت الشريعة. الأوامر المتاحة: ‎/start‎ و ‎/lang‎ و ‎/help‎.",

    # Settings dialog
    "language.menu.title": "يرجى اختيار لغة واجهة البوت",
    "language.back": "رجوع",
    "language.save": "حفظ",
    "language.saved": "تم حفظ إعدادات اللغة!",

    # Misc
    "welcome.body": "اختر قسماً من القائمة الرئيسية.",
    "input.placeholder.question": "صف سؤالك…",
    "user.default_name": "مستخدم",
    "docs.default_name": "مستند",
    "error.document.send": "تعذّر إرسال المستند: {name}",

    # AI
    "ai.system.prompt": (
        "🕌 ПРОМТ: Шариатский ассистент (только Shamela, арабский + перевод, без ссылок)"
        ""
        "Ты — исламский шариатский ассистент, который отвечает на вопросы исключительно на основе классических исламских книг, представленных в библиотеке Shamela."
        ""
        "📌 Главный принцип"
        ""
        "Ты не имеешь права использовать никакие источники, кроме текстов из Shamela."
        "Запрещено опираться на Википедию, современные сайты, личные мнения или неподтверждённые ответы."
        ""
        "---"
        ""
        "✅ Обязательный формат ответа"
        ""
        "1) Арабский оригинал (дословно из книги)"
        ""
        "Ты всегда приводишь оригинальный арабский текст:"
        ""
        "النص العربي: «…цитата…»"
        ""
        "---"
        ""
        "2) Точный перевод на язык вопроса"
        ""
        "Перевод должен быть на том языке, на котором пользователь задал вопрос"
        "(русский → русский перевод, английский → английский перевод, турецкий → турецкий перевод)."
        ""
        "Перевод: «…перевод…»"
        ""
        "---"
        ""
        "3) Полная библиографическая ссылка (без URL)"
        ""
        "После цитаты обязательно указывай:"
        ""
        "название книги"
        ""
        "имя автора"
        ""
        "раздел/глава (باب / فصل)"
        ""
        "том (الجزء)"
        ""
        "страница (الصفحة)"
        ""
        "номер вопроса (если есть)"
        ""
        "Пример:"
        ""
        "المصدر:"
        ""
        "الكتاب: المغни"
        ""
        "المؤلف: ابن قدامة"
        ""
        "الباب: كتاب الطهارة"
        ""
        "الجزء: 1"
        ""
        "الصفحة: 215"
        ""
        "---"
        ""
        "4) Разъяснение (только в рамках текста)"
        ""
        "Ты можешь кратко объяснить вывод, но без личных домыслов:"
        ""
        "Пояснение: Этот текст указывает, что…"
        ""
        "---"
        ""
        "5) Если есть разногласие — привести мнения"
        ""
        "Если вопрос спорный, приведи несколько цитат из Shamela:"
        ""
        "قول الحنفية: …"
        "قول المالكية: …"
        "قول الشافعية: …"
        "قول الحنابلة: …"
        ""
        "Каждое мнение — с арабской цитатой и переводом."
        ""
        "---"
        ""
        "❌ Запрещено"
        ""
        "давать ответ без арабской цитаты"
        ""
        "писать «учёные говорят» без источника"
        ""
        "вставлять ссылки на Shamela"
        ""
        "использовать любые сайты кроме Shamela"
        ""
        "выдавать фетву от себя"
        ""
        "сокращать ответы до общих слов"
        ""
        "---"
        ""
        "🧠 Если ответа нет в Shamela"
        ""
        "Ты обязан сказать:"
        ""
        "«В текстах Shamela не найден прямой однозначный ответ. Ниже приведены ближайшие связанные упоминания из классических книг…»"
        ""
        "И привести ближайшие тексты."
        ""
        "---"
        ""
        "📝 Стиль ответа"
        ""
        "Ответ должен быть:"
        ""
        "обширным"
        ""
        "строго академическим"
        ""
        "основанным на книгах фикха и хадиса"
        ""
        "с уважительным исламским языком"
        ""
        "---"
        ""
        "Пример ответа (шаблон)"
        ""
        "Вопрос: Можно ли объединять молитвы в пути?"
        ""
        "النص العربي: «…»"
        ""
        "Перевод: «…»"
        ""
        "المصدر:"
        ""
        "الكتاب: زاد المعاد"
        ""
        "المؤلف: ابن القيم"
        ""
        "الفصل: صلاة المسافر"
        ""
        "الجزء: 1"
        ""
        "الصفحة: 456"
    ),
    "ai.response.prefix": "🤖 إجابة الذكاء الاصطناعي:",
    "ai.response.footer": "عند الحاجة سنحوّل السؤال إلى العلماء.",
    "ai.error.unavailable": "خدمة الذكاء الاصطناعي غير متاحة الآن.",
    "ai.error.empty": "الإجابة فارغة.",
    "ai.error.empty.trimmed": "فارغة بعد التصفية.",
    "ai.error.generic": "حدث خطأ أثناء توليد الإجابة.",
    "ai.response.waiting": "جارٍ توليد الإجابة…",

# Buttons & menus
    "button.back": "رجوع",
    "button.materials": "مواد",
    "button.ask.scholars": "سؤال العلماء",
    "button.community.support": "دعم المجتمع",
    "button.holiday.ask_ai": "سؤال الذكاء الاصطناعي",
    "button.holiday.download": "تحميل المستند",
    "button.answer.user": "الإجابة للمستخدم",
    "button.profile.open": "الملف الشخصي",
    "button.my_cases.contracts": "عقودي",
    "button.my_cases.courts": "محاكمي",
    "button.my_cases.inheritance": "الميراث والوصايا",
    "button.my_cases.nikah": "النكاح",
    "button.my_cases.spouse_search": "🌿 التعارف",
    "button.spouse.profile": "📝 ملفي",
    "button.spouse.search": "🔎 بحث",
    "button.spouse.requests": "📨 طلباتي",
    "button.spouse.rules": "🛡 القواعد والحماية",
    "button.spouse.ask": "❓ اسأل العلماء",
    "button.nikah.new": "📝 إنشاء نكاح جديد",
    "button.nikah.my": "📄 زيجاتي",
    "button.nikah.rules": "🕋 أحكام النكاح",
    "button.nikah.ask": "❓ اسأل العلماء",
    "button.blacklist.view": "عرض القائمة",
    "button.blacklist.search": "بحث",
    "button.blacklist.report": "تقديم بلاغ",
    "button.blacklist.appeal": "تقديم اعتراض",
    "button.knowledge.foundation": "الأساسيات",
    "button.knowledge.holidays": "الأعياد الإسلامية",
    "button.meetings.open": "الاجتماعات",
    "button.chat.men": "دردشة الرجال",
    "button.chat.women": "دردشة النساء",
    "button.enforcement.open": "انتقال",

    # Contract flow
    "contracts.create.menu.title": "إنشاء عقد",
    "contracts.create.option.templates": "اختيار من القوالب",
    "contracts.create.option.upload": "رفع ملف",
    "contracts.none": "لا توجد قوالب متاحة.",
    "contracts.saved": "تم حفظ العقد.",
    "contracts.search.found": "تم العثور على قوالب.",
    "contracts.search.none": "لم يتم العثور على قوالب.",
    "contracts.search.prompt": "أدخل موضوعاً أو اسم القالب.",
    "contracts.sent": "تم إرسال العقد.",
    "contracts.flow.button.delete": "🗑 حذف العقد",
    "contracts.delete.done": "تم حذف العقد.",
    "contracts.flow.party.approve": "✅ موافقة",
    "contracts.flow.party.changes": "✍️ طلب تعديلات",
    "contracts.flow.party.comment.prompt": "اشرح ما الذي يجب تغييره في العقد.",
    "contracts.flow.party.thanks": "شكرًا! تم إرسال ردك إلى مُنشئ العقد.",
    "contracts.flow.party.approved.notice": "قام المستخدم {party} بالموافقة على العقد.",
    "contracts.flow.party.changes.notice": "طلب المستخدم {party} تعديلات: {comment}",
    "contracts.list.title": "عقودك:",
    "contracts.title.unknown": "عقد",
    "contracts.list.item": "📄 {title}\nالحالة: {status}\nالتاريخ: {date}\nالطرف المقابل: {party}",
    "contracts.list.party.unknown": "غير محدد",
    "contracts.status.draft": "مسودة",
    "contracts.status.confirmed": "تم الإنشاء",
    "contracts.status.sent_to_party": "تم الإرسال للطرف",
    "contracts.status.party_approved": "تمت الموافقة من الطرف",
    "contracts.status.party_changes_requested": "تم طلب تعديلات",
    "contracts.status.sent_to_scholar": "أُرسل إلى العالِم",
    "contracts.status.scholar_send_failed": "فشل الإرسال إلى العالِم",
    "contracts.status.sent": "تم الإرسال",
    "contracts.edit.not_allowed": "لا يمكن تعديل العقد في هذه الحالة.",
    "contracts.stats.info": "إحصائيات القوالب.",
    "contracts.template.coming_soon": "قريباً.",
    "contracts.template.download": "تنزيل القالب",
    "contracts.template.missing": "القالب غير متاح.",
    "contracts.template.start": "البدء بالقوالب",
    "contracts.templates.choose_category": "اختر فئة",
    "contracts.templates.choose_contract": "اختر قالباً",
    "contracts.templates.select_action": "اختر إجراء",
    "contracts.title.prompt": "عنوان العقد",
    "contracts.upload.prompt": "ارفع ملف PDF",

    # Courts
    "courts.file.instructions": "أرفِق ملف الدعوى بصيغة PDF.",
    "courts.info.closed": "تم إغلاق القضية.",
    "courts.info.in_progress": "القضية قيد المعالجة.",
    "courts.info.opened": "تم فتح القضية.",

    # Docs
    "docs.empty": "لا توجد مواد بعد.",
    "docs.searching": "جارٍ البحث عن المواد…",
    "docs.holiday.searching": "جارٍ البحث عن مواد العيد…",
    "holiday.ai.default_question": "تهنئة ونصيحة بمناسبة العيد",
    "holiday.description.template": "مادة مُعدة خاصة بالعيد.",
    "holiday.document.missing": "المستند غير موجود.",

    # Errors & notifications
    "error.request.invalid": "طلب غير صالح.",
    "error.answer.recipient_unknown": "المستلم غير معروف.",
    "answer.delivery.failed": "تعذّر تسليم الإجابة.",
    "answer.sent.confirmation": "تم إرسال الإجابة.",
    "notify.answer.user": "تم إرسال الإجابة إلى المستخدم.",
    "notify.question.forward": "تم تحويل السؤال للمراجعة.",

    # Contracts validation errors
    "error.contracts.file.only_pdf": "مسموح بـ PDF فقط.",
    "error.contracts.file.required_pdf": "ملف PDF مطلوب.",
    "error.contracts.file.too_large": "الملف كبير جداً.",
    "error.contracts.name.empty": "أدخل عنواناً.",
    "error.contracts.name.missing_state": "حالة غير صالحة.",
    "error.contracts.name.too_long": "العنوان طويل جداً.",
    "error.contracts.search.empty": "أدخل عبارة البحث.",

# Questions
    "question.prompt": "صِف سؤالك.",
    "question.sent": "تم إرسال السؤال.",
    "question.failed": "فشل إرسال السؤال.",
    "question.empty": "سؤال فارغ.",

    # Blacklist & enforcement
    "blacklist.view.placeholder": "ميزة عرض القائمة قيد الإنشاء.",
    "blacklist.search.placeholder": "البحث في القائمة السوداء قيد التحضير.",
    "blacklist.report.placeholder": "سيتم تفعيل نموذج البلاغ قريباً. تواصل مع الإدارة حالياً.",
    "blacklist.appeal.placeholder": "سيُتاح تقديم الاعتراض في التحديث القادم.",
    "enforcement.placeholder": "وحدة متابعة التنفيذ قيد التطوير. سيتم الإعلان لاحقاً.",

# Menus (main buttons and titles)
    "menu.back.main": "عودة إلى القائمة الرئيسية",
    "menu.my_cases": "قضاياي",
    "menu.blacklist": "القائمة السوداء",
    "menu.knowledge": "المعرفة الشرعية",
    "menu.committee": "اللجنة الشرعية",
    "menu.meetings_chats": "الاجتماعات والدردشات",
    "menu.enforcement": "متابعة التنفيذ",
    "menu.good_deeds": "الأعمال الصالحة",
    "menu.zakat": "الزكاة والصدقات",
    "menu.contracts": "عقودي",
    "menu.courts": "محاكمي",
    "menu.inheritance": "الميراث والوصايا",
    "menu.holidays": "الأعياد الإسلامية",
    "menu.nikah": "النكاح",
    "menu.spouse_search": "التعارف",
    "menu.my_cases.title": "اختر المجال الذي تريد العمل عليه في قضاياك.",
    "menu.blacklist.title": (
        "قسم يُنشر فيه المسلمون الذين خالفوا العقود أو رفضوا تنفيذ الأحكام "
        "أو ظلموا المسلمين."
    ),
    "menu.knowledge.title": "مركز المعرفة الشرعية. اختر التصنيف المناسب.",
    "menu.knowledge.topics.title": "الأساسيات: مجموعات في العقيدة والفقه والثقافة.",
    "menu.committee.title": (
        "الهيئة المركزية لحل النزاعات وإدارة المنصة.\n\n"
        "هنا يتم:\n"
        "• توثيق العقود بين المسلمين وحفظها\n"
        "• اختيار الإخوة الموثوقين لمتابعة تنفيذ الأحكام\n"
        "• تحديد العقوبات لمن يرفض التنفيذ وتطبيقها\n"
        "• الإشراف على تنظيم المنصة وتنسيق أعمالها\n"
        "• دعم الشفافية والعدالة والنظام الشرعي\n\n"
        "إنه قلب المنظومة لمن يسعى إلى العدالة الحقيقية وفق الشريعة "
        "وتوحيد المسلمين على أساس العهد والمسؤولية والأخوة."
    ),
    "menu.meetings_chats.title": "اجتماعات وتواصل. اختر الصيغة المناسبة.",
    "menu.meetings.title": "الاجتماعات\nاقترح فكرة أو شارك في تصويت المجتمع.",
    "menu.good_deeds.title": "مبادرات وأعمال صالحة.",
    "menu.inheritance.title": "الميراث والوصايا.",
    "menu.holidays.title": "الأعياد الإسلامية.",
    "menu.nikah.title": "النكاح.",
    "menu.spouse_search.title": "التعارف والبحث عن الزوج/الزوجة.",
    "menu.zakat.title": "الزكاة والصدقات.",
    "menu.enforcement.title": (
        "توثيق تنفيذ الأحكام الشرعية أو رفضها. جمع الأدلة والتذكيرات."
    ),
    "menu.contracts.title": "عقودي.",
    "menu.courts.title": "محاكمي.",
    "menu.courts.statuses.title": "حالات القضايا.",

    # Scheduler
    "command.scheduler.unavailable": "الجدولة غير متاحة.",
}

TEXTS_RU.update(
    {
        "button.courts.file": "✍️ Подать в суд",
        "courts.claim.choose_category": "Выберите категорию:",
        "courts.claim.category.financial": "Финансовые споры",
        "courts.claim.category.family": "Семейные вопросы",
        "courts.claim.category.ethics": "Этические конфликты",
        "courts.claim.category.ask_scholars": "Спросить у ученых",
        "courts.claim.category.unknown": "Неизвестная категория",
        "courts.claim.redirect": "Для категории «{category}» перейдите в закрытый чат:",
        "courts.claim.open_chat": "Открыть чат",
        "courts.claim.prompt.question": "Напишите ваш вопрос:",
        "courts.claim.cancelled": "Запрос отменён.",
        "courts.file.sent": "Заявление отправлено. Мы свяжемся с вами при необходимости.",
        "courts.file.cancelled": "Отправка заявления отменена.",
        "courts.file.unavailable": "Не удалось принять заявление. Попробуйте позже.",
        "courts.file.admin.caption": "Новая заявка в суд ({category}) от {full_name} ({username}, id {user_id}).",
            "button.courts.details.invite": "\u041f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u0442\u044c \u043e\u0442\u0432\u0435\u0442\u0447\u0438\u043a\u0430",
        "button.courts.details.invite_share": "\u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0432\u0435\u0442\u0447\u0438\u043a\u0443",
        "courts.invite.missing": "\u041a\u043e\u0434 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d. \u0421\u043e\u0437\u0434\u0430\u0439\u0442\u0435 \u043d\u043e\u0432\u043e\u0435 \u0434\u0435\u043b\u043e \u0438\u043b\u0438 \u043e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443.",
"courts.invite.already_connected": "\u041e\u0442\u0432\u0435\u0442\u0447\u0438\u043a \u0443\u0436\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d \u043a \u0434\u0435\u043b\u0443.",
        "courts.invite.share.text": "Ссылка для подключения к делу: {invite_link}",
        "courts.error.closed": "\u0414\u0435\u043b\u043e \u0437\u0430\u043a\u0440\u044b\u0442\u043e. \u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b.",
        "courts.case.cancel.confirm": "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043e\u0442\u043c\u0435\u043d\u0443 \u0434\u0435\u043b\u0430.",
        "courts.case.cancel.aborted": "\u041e\u0442\u043c\u0435\u043d\u0430 \u0434\u0435\u043b\u0430 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430.",
        "button.courts.details.cancel_confirm": "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c",
        "button.courts.details.cancel_abort": "\u041d\u0435 \u043e\u0442\u043c\u0435\u043d\u044f\u0442\u044c",
}
)

TEXTS_EN.update(
    {
        "button.courts.file": "File a claim",
        "courts.claim.choose_category": "Choose a category:",
        "courts.claim.category.financial": "Financial disputes",
        "courts.claim.category.family": "Family matters",
        "courts.claim.category.ethics": "Ethical conflicts",
        "courts.claim.category.ask_scholars": "Ask scholars",
        "courts.claim.category.unknown": "Unknown category",
        "courts.claim.redirect": "For the “{category}” category, open the private chat:",
        "courts.claim.open_chat": "Open chat",
        "courts.claim.prompt.question": "Type your question:",
        "courts.claim.cancelled": "Request cancelled.",
        "courts.file.sent": "Your claim has been sent. We'll contact you if needed.",
        "courts.file.cancelled": "Claim submission cancelled.",
        "courts.file.unavailable": "Could not accept the claim. Please try again later.",
        "courts.file.admin.caption": "New court claim ({category}) from {full_name} ({username}, id {user_id}).",
    }
)

TEXTS_AR.update(
    {
        "button.courts.file": "تقديم دعوى",
        "courts.claim.choose_category": "اختر فئة:",
        "courts.claim.category.financial": "نزاعات مالية",
        "courts.claim.category.family": "مسائل أسرية",
        "courts.claim.category.ethics": "نزاعات أخلاقية",
        "courts.claim.category.ask_scholars": "اسأل العلماء",
        "courts.claim.category.unknown": "فئة غير معروفة",
        "courts.claim.redirect": "لفئة «{category}»، افتح الدردشة الخاصة:",
        "courts.claim.open_chat": "فتح الدردشة",
        "courts.claim.prompt.question": "اكتب سؤالك:",
        "courts.claim.cancelled": "تم إلغاء الطلب.",
        "courts.file.sent": "تم إرسال الدعوى. سنتواصل معك عند الحاجة.",
        "courts.file.cancelled": "تم إلغاء إرسال الدعوى.",
        "courts.file.unavailable": "تعذر قبول الدعوى. حاول مرة أخرى لاحقًا.",
        "courts.file.admin.caption": "طلب دعوى جديد ({category}) من {full_name} ({username}, id {user_id}).",
    }
)

TEXTS_RU.update(
    {
        "menu.courts.title": "⚖️ МОИ СУДЫ",
        "button.courts.file": "📝 Подать в суд",
        "button.courts.opened": "📖 Открытые дела",
        "button.courts.in_progress": "⏳ В процессе",
        "button.courts.closed": "✅ Завершённые дела",
        "button.courts.details.more": "➡️ Подробнее",
        "button.courts.details.add_evidence": "📥 Добавить доказательство",
        "button.courts.details.view_evidence": "📎 Просмотреть доказательства",
        "button.courts.details.edit_claim": "✏️ Редактировать описание",
        "button.courts.details.edit_category": "🗂 Изменить категорию",
        "button.courts.details.cancel_case": "❌ Отменить дело",
        "button.courts.details.send_scholar": "➡️ Передать учёному",
        "button.courts.confirm.send": "✔️ Отправить",
        "button.courts.confirm.edit": "✏️ Изменить",
        "button.courts.confirm.cancel": "❌ Отмена",
        "button.courts.evidence.photo": "📎 Фото документов",
        "button.courts.evidence.link": "🔗 Ссылка на облачное хранилище",
        "button.courts.evidence.audio": "🎧 Аудио",
        "button.courts.evidence.text": "📄 Текст",
        "button.courts.evidence.skip": "⏭️ Пропустить",
        "button.yes.upload": "📄 Да (загрузить)",
        "button.no": "❌ Нет",
        "courts.step.category": "Шаг 1. Выбор типа спора",
        "courts.step.plaintiff": "Укажите истца (например: Мухаммад).",
        "courts.step.defendant": "Укажите ответчика (имя или ник в Telegram).",
        "courts.step.claim": "Опишите ситуацию простыми словами:\n— что произошло\n— когда\n— что вы хотите (выплата, возврат, признание долга, извинение)",
        "courts.step.claim.contract": "Договор №{contract_number} («{contract_title}»). Ответчик: {defendant}.\nОпишите суть дела: что произошло и чего вы хотите.",
        "courts.claim.contract_prefix": "Договор №{contract_number} («{contract_title}»).",
        "courts.step.amount": "Укажите сумму спора (в валюте). Если нет суммы — напишите \"нет\".",
        "courts.step.contract": "Есть договор?",
        "courts.step.contract.upload": "Загрузите договор (документ или фото).",
        "courts.step.family": "Это связано с наследством или никахом?",
        "courts.step.evidence": "Вы можете прикрепить доказательства (по желанию):",
        "courts.evidence.prompt.photo": "Прикрепите фото документов.",
        "courts.evidence.prompt.link": "Отправьте ссылку на облачное хранилище.",
        "courts.evidence.prompt.audio": "Отправьте аудио.",
        "courts.evidence.prompt.text": "Отправьте текст доказательства.",
        "courts.evidence.added": "Доказательство добавлено. Хотите добавить ещё?",
        "courts.evidence.list.title": "📎 Доказательства по делу:",
        "courts.evidence.empty": "Доказательства по делу отсутствуют.",
        "courts.confirmation": "📌 ЗАЯВКА В СУД\n\nИстец: {plaintiff}\nОтветчик: {defendant}\nКатегория: {category}\nСуть: {claim_text}\nСумма (если есть): {amount}\nДоказательства: {evidence_count}\n\nОтправить дело учёному?",
        "courts.confirm.cancelled": "Заявка отменена.",
        "courts.case.created": "📁 Дело №{case_number} создано.\nСтатус: ОТКРЫТО\nУчёный будет назначен.",
        "courts.case.forward.summary": "📌 ЗАЯВКА В СУД №{case_number}\nПользователь: {full_name} {username} (id {user_id})\nИстец: {plaintiff}\nОтветчик: {defendant}\nКатегория: {category}\nСуть: {claim}\nСумма: {amount}\nДоказательства: {evidence_count}",
        "courts.case.forward.evidence.text": "📎 Доказательство: {text}",
        "courts.case.list.item": "📌 №{case_number} — {category}\nСтороны: Вы vs {defendant}\nСтатус: {status}",
        "courts.cases.empty.opened": "Открытых дел пока нет.",
        "courts.cases.empty.in_progress": "Дел в процессе пока нет.",
        "courts.cases.empty.closed": "Завершённых дел пока нет.",
        "courts.case.details": "📄 Описание\n№{case_number}\nКатегория: {category}\nСтатус: {status}\n⚖️ Суть: {claim}\n📎 Доказательства: {evidence_count}\n\nСудья: {scholar}\nСвязь: {contact}",
        "courts.case.not_found": "Дело не найдено.",
        "courts.case.cancelled": "Дело отменено.",
        "courts.case.sent_to_scholar": "Дело передано учёному.",
        "courts.case.already_sent": "Дело уже передано учёному.",
        "courts.error.name.empty": "Укажите имя или ник.",
        "courts.error.personal_data": "❌ Личные данные запрещены.\nУкажите только имя или ник.",
        "courts.error.claim.empty": "Опишите суть спора.",
        "courts.error.amount.invalid": "Введите сумму числом или напишите \"нет\".",
        "courts.error.contract.file": "Нужно загрузить документ или фото договора.",
        "courts.error.evidence.limit": "Слишком много доказательств. Добавьте меньше.",
        "courts.error.evidence.photo": "Нужно отправить фото.",
        "courts.error.evidence.audio": "Нужно отправить аудио или голосовое сообщение.",
        "courts.error.evidence.text": "Нужно отправить текст.",
        "courts.error.evidence.link": "Нужна ссылка, начинающаяся с http:// или https://",
        "courts.error.evidence.expected": "Отправьте файл или текст доказательства.",
        "courts.error.evidence.blocked": "❌ Этот файл нельзя использовать как доказательство.\nПопробуйте другой.",
        "courts.amount.none": "нет",
        "courts.sharia.blocked": "❌ Требование противоречит шариату и не может быть подано.\nПожалуйста, исправьте запрос.",
        "courts.sharia.clarify": "⚠️ Пожалуйста, уточните суть спора: что произошло и чего вы хотите.",
        "courts.category.financial": "💰 Финансовый спор",
        "courts.category.contract_breach": "🤝 Нарушение договора",
        "courts.category.property": "🏠 Имущество/аренда",
        "courts.category.goods": "📦 Поставка / товар",
        "courts.category.services": "🛠 Услуги / работа",
        "courts.category.family": "💍 Семейный вопрос",
        "courts.category.ethics": "✋ Этический конфликт",
        "courts.category.unknown": "Неизвестная категория",
        "courts.status.open": "Открыто",
        "courts.status.in_progress": "В процессе",
        "courts.status.closed": "Завершено",
        "courts.status.cancelled": "Отменено",
        "courts.scholar.unassigned": "не назначен",
        "courts.scholar.contact.none": "нет контакта",
        "courts.family.inheritance": "Наследство",
        "courts.family.nikah": "Никах",
        "courts.family.no": "Нет",
        "courts.family.redirect": "Перенаправляю в нужный раздел.",
        "courts.edit.done": "Готово.",
        "courts.edit.claim.prompt": "Отправьте новое описание дела.",
        "courts.edit.claim.saved": "Описание обновлено.",
        "courts.edit.category.saved": "Категория обновлена.",
        "button.courts.details.mediate": "🤝 Попытаться решить мирно",
        "courts.invite.code": "\u041e\u0442\u0432\u0435\u0442\u0447\u0438\u043a \u0435\u0449\u0451 \u043d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d. \u041f\u0435\u0440\u0435\u0434\u0430\u0439\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443:\\n{invite_link}",
        "courts.invite.code.only": "\u041e\u0442\u0432\u0435\u0442\u0447\u0438\u043a \u0435\u0449\u0451 \u043d\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d. \u041f\u0435\u0440\u0435\u0434\u0430\u0439\u0442\u0435 \u043a\u043e\u0434: {invite_code}",
        "courts.invite.invalid": "\u041a\u043e\u0434 \u043d\u0435\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0442\u0435\u043b\u0435\u043d.",
        "courts.invite.used": "\u041a\u043e\u0434 \u0443\u0436\u0435 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u043d.",
        "courts.invite.self": "\u0412\u044b \u0443\u0436\u0435 \u0443\u0447\u0430\u0441\u0442\u043d\u0438\u043a \u044d\u0442\u043e\u0433\u043e \u0434\u0435\u043b\u0430.",
        "courts.invite.joined": "\u0412\u044b \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u044b \u043a \u0434\u0435\u043b\u0443 \u2116{case_number}.",
        "courts.invite.plaintiff_notice": "\u041e\u0442\u0432\u0435\u0442\u0447\u0438\u043a \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0438\u043b\u0441\u044f \u043a \u0434\u0435\u043b\u0443 \u2116{case_number}.",
        "courts.error.permission": "Недостаточно прав для этого действия.",
        "courts.case.mediate.sent": "Запрос на мирное решение принят. Ожидайте ответа.",
        "button.courts.mediate.join": "Войти в чат",
        "button.courts.mediate.stop": "Закрыть чат",
        "courts.case.mediate.start": "Внутренний чат открыт. Напишите сообщение. Чтобы выйти, отправьте /cancel.",
        "courts.case.mediate.joined": "Вы подключились к чату по делу №{case_number}.",
        "courts.case.mediate.stopped": "Чат закрыт.",
        "courts.case.mediate.notice": "Открыт внутренний чат по делу №{case_number}. Инициатор: {name}. Нажмите «Войти в чат» чтобы ответить.",
        "courts.case.mediate.forward": "💬 {name}:\n{text}",
        "courts.case.mediate.forward.media": "💬 {name} отправил(а) файл.\n{caption}",
        "courts.case.mediate.no_recipients": "Некому отправить сообщение.",
        "courts.case.mediate.unsupported": "Можно отправлять только текст или файлы.",
        "courts.case.mediate.history.title": "История чата:",
        "courts.case.mediate.history.media": "Файл",
        "courts.case.mediate.pdf.saved": "Чат сохранён в доказательствах.",
        "courts.case.mediate.pdf.empty": "В чате нет сообщений для сохранения.",
        "courts.case.mediate.pdf.failed": "Не удалось сохранить чат.",
        "courts.case.mediate.pdf.caption": "Внутренний чат по делу №{case_number}",
        "courts.mediate.pdf.title": "Внутренний чат по делу №{case_number}",
        "courts.mediate.pdf.plaintiff": "Истец: {name}",
        "courts.mediate.pdf.defendant": "Ответчик: {name}",
        "courts.mediate.pdf.category": "Категория: {name}",
        "courts.mediate.pdf.generated": "Сформировано: {timestamp}",
        "courts.mediate.pdf.media": "Файл",
        "button.courts.details.cancel_abort": "\u041d\u0435 \u043e\u0442\u043c\u0435\u043d\u044f\u0442\u044c",
        "button.courts.details.cancel_confirm": "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c",
        "courts.case.cancel.aborted": "\u041e\u0442\u043c\u0435\u043d\u0430 \u0434\u0435\u043b\u0430 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430.",
        "courts.case.cancel.confirm": "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043e\u0442\u043c\u0435\u043d\u0443 \u0434\u0435\u043b\u0430.",
        "courts.error.closed": "\u0414\u0435\u043b\u043e \u0437\u0430\u043a\u0440\u044b\u0442\u043e. \u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u044f \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b.",
        "button.courts.details.invite": "\u041f\u0440\u0438\u0433\u043b\u0430\u0441\u0438\u0442\u044c \u043e\u0442\u0432\u0435\u0442\u0447\u0438\u043a\u0430",
        "button.courts.details.invite_share": "\u041e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u043e\u0442\u0432\u0435\u0442\u0447\u0438\u043a\u0443",
        "courts.invite.missing": "\u041a\u043e\u0434 \u043f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d. \u0421\u043e\u0437\u0434\u0430\u0439\u0442\u0435 \u043d\u043e\u0432\u043e\u0435 \u0434\u0435\u043b\u043e \u0438\u043b\u0438 \u043e\u0431\u0440\u0430\u0442\u0438\u0442\u0435\u0441\u044c \u0432 \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0443.",
        "courts.invite.already_connected": "\u041e\u0442\u0432\u0435\u0442\u0447\u0438\u043a \u0443\u0436\u0435 \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d \u043a \u0434\u0435\u043b\u0443.",
        "courts.invite.share.text": "Ссылка для подключения к делу: {invite_link}",
    }
)

TEXTS_EN.update(
    {
        "menu.courts.title": "⚖️ MY COURTS",
        "button.courts.file": "📝 File a claim",
        "button.courts.opened": "📖 Open cases",
        "button.courts.in_progress": "⏳ In progress",
        "button.courts.closed": "✅ Closed cases",
        "button.courts.details.more": "➡️ Details",
        "button.courts.details.add_evidence": "📥 Add evidence",
        "button.courts.details.view_evidence": "📎 View evidence",
        "button.courts.details.edit_claim": "✏️ Edit description",
        "button.courts.details.edit_category": "🗂 Change category",
        "button.courts.details.cancel_case": "❌ Cancel case",
        "button.courts.details.send_scholar": "➡️ Send to scholar",
        "button.courts.confirm.send": "✔️ Send",
        "button.courts.confirm.edit": "✏️ Edit",
        "button.courts.confirm.cancel": "❌ Cancel",
        "button.courts.evidence.photo": "📎 Document photo",
        "button.courts.evidence.link": "🔗 Cloud link",
        "button.courts.evidence.audio": "🎧 Audio",
        "button.courts.evidence.text": "📄 Text",
        "button.courts.evidence.skip": "⏭️ Skip",
        "button.yes.upload": "📄 Yes (upload)",
        "button.no": "❌ No",
        "courts.step.category": "Step 1. Choose a dispute type",
        "courts.step.plaintiff": "Enter the plaintiff name.",
        "courts.step.defendant": "Enter the defendant name or Telegram handle.",
        "courts.step.claim": "Describe the situation in simple words.",
        "courts.step.claim.contract": "Contract No. {contract_number} ({contract_title}). Defendant: {defendant}.\nDescribe the claim: what happened and what you want.",
        "courts.claim.contract_prefix": "Contract No. {contract_number} ({contract_title}).",
        "courts.step.amount": "Enter the dispute amount. If none, type \"no\".",
        "courts.step.contract": "Do you have a contract?",
        "courts.step.contract.upload": "Upload the contract file or photo.",
        "courts.step.family": "Is it related to inheritance or nikah?",
        "courts.step.evidence": "You can attach evidence (optional):",
        "courts.evidence.prompt.photo": "Send a document photo.",
        "courts.evidence.prompt.link": "Send a cloud storage link.",
        "courts.evidence.prompt.audio": "Send an audio file.",
        "courts.evidence.prompt.text": "Send evidence text.",
        "courts.evidence.added": "Evidence added. Add more?",
        "courts.evidence.list.title": "📎 Case evidence:",
        "courts.evidence.empty": "No evidence for this case.",
        "courts.confirmation": "📌 COURT CLAIM\n\nPlaintiff: {plaintiff}\nDefendant: {defendant}\nCategory: {category}\nClaim: {claim_text}\nAmount: {amount}\nEvidence: {evidence_count}\n\nSend the case to a scholar?",
        "courts.confirm.cancelled": "Claim cancelled.",
        "courts.case.created": "📁 Case №{case_number} created.\nStatus: OPEN\nA scholar will be assigned.",
        "courts.case.forward.summary": "📌 COURT CLAIM №{case_number}\nUser: {full_name} {username} (id {user_id})\nPlaintiff: {plaintiff}\nDefendant: {defendant}\nCategory: {category}\nClaim: {claim}\nAmount: {amount}\nEvidence: {evidence_count}",
        "courts.case.forward.evidence.text": "📎 Evidence: {text}",
        "courts.case.list.item": "📌 №{case_number} — {category}\nParties: You vs {defendant}\nStatus: {status}",
        "courts.cases.empty.opened": "No open cases yet.",
        "courts.cases.empty.in_progress": "No cases in progress yet.",
        "courts.cases.empty.closed": "No closed cases yet.",
        "courts.case.details": "📄 Details\n№{case_number}\nCategory: {category}\nStatus: {status}\n⚖️ Claim: {claim}\n📎 Evidence: {evidence_count}\n\nScholar: {scholar}\nContact: {contact}",
        "courts.case.not_found": "Case not found.",
        "courts.case.cancelled": "Case cancelled.",
        "courts.case.sent_to_scholar": "Case sent to scholar.",
        "courts.case.already_sent": "Case already sent to scholar.",
        "courts.error.name.empty": "Please enter a name or handle.",
        "courts.error.personal_data": "❌ Personal data is forbidden. Use only a name or handle.",
        "courts.error.claim.empty": "Describe the dispute.",
        "courts.error.amount.invalid": "Enter a number or \"no\".",
        "courts.error.contract.file": "Upload a contract document or photo.",
        "courts.error.evidence.limit": "Too many evidence items.",
        "courts.error.evidence.photo": "Send a photo.",
        "courts.error.evidence.audio": "Send an audio or voice message.",
        "courts.error.evidence.text": "Send a text.",
        "courts.error.evidence.link": "Link must start with http:// or https://",
        "courts.error.evidence.expected": "Send a file or text evidence.",
        "courts.error.evidence.blocked": "❌ This file cannot be used as evidence.",
        "courts.amount.none": "no",
        "courts.sharia.blocked": "❌ The request conflicts with Sharia and cannot be filed.",
        "courts.sharia.clarify": "⚠️ Please clarify the dispute details.",
        "courts.category.financial": "💰 Financial dispute",
        "courts.category.contract_breach": "🤝 Contract breach",
        "courts.category.property": "🏠 Property / rent",
        "courts.category.goods": "📦 Goods / supply",
        "courts.category.services": "🛠 Services / work",
        "courts.category.family": "💍 Family matter",
        "courts.category.ethics": "✋ Ethical conflict",
        "courts.category.unknown": "Unknown category",
        "courts.status.open": "Open",
        "courts.status.in_progress": "In progress",
        "courts.status.closed": "Closed",
        "courts.status.cancelled": "Cancelled",
        "courts.scholar.unassigned": "not assigned",
        "courts.scholar.contact.none": "no contact",
        "courts.family.inheritance": "Inheritance",
        "courts.family.nikah": "Nikah",
        "courts.family.no": "No",
        "courts.family.redirect": "Redirecting to the relevant section.",
        "courts.edit.done": "Done.",
        "courts.edit.claim.prompt": "Send the new case description.",
        "courts.edit.claim.saved": "Description updated.",
        "courts.edit.category.saved": "Category updated.",
        "button.courts.details.mediate": "🤝 Try to resolve peacefully",
        "courts.invite.code": "The defendant is not connected yet. Share the link:\n{invite_link}",
        "courts.invite.code.only": "The defendant is not connected yet. Share the code: {invite_code}",
        "button.courts.details.invite": "📨 Invite defendant",
        "button.courts.details.invite_share": "📤 Send to defendant",
        "courts.invite.missing": "Invite code is missing. Create a new case or contact support.",
        "courts.invite.already_connected": "The defendant is already connected to this case.",
        "courts.invite.share.text": "Case invite link: {invite_link}",
        "courts.invite.invalid": "Invalid code.",
        "courts.invite.used": "This code has already been used.",
        "courts.invite.self": "You are already a participant of this case.",
        "courts.invite.joined": "You are connected to case #{case_number}.",
        "courts.invite.plaintiff_notice": "The defendant has connected to case #{case_number}.",
        "courts.error.permission": "You do not have permission for this action.",
        "courts.case.mediate.sent": "Your mediation request has been received. Please wait.",
        "button.courts.mediate.join": "Join chat",
        "button.courts.mediate.stop": "Close chat",
        "courts.case.mediate.start": "The internal chat is open. Send a message. To exit, send /cancel.",
        "courts.case.mediate.joined": "You joined the chat for case #{case_number}.",
        "courts.case.mediate.stopped": "Chat closed.",
        "courts.case.mediate.notice": "An internal chat is open for case #{case_number}. Initiator: {name}. Tap \"Join chat\" to reply.",
        "courts.case.mediate.forward": "💬 {name}:\n{text}",
        "courts.case.mediate.forward.media": "💬 {name} sent a file.\n{caption}",
        "courts.case.mediate.no_recipients": "No recipients to send to.",
        "courts.case.mediate.unsupported": "Only text or files are supported.",
        "courts.case.mediate.history.title": "Chat history:",
        "courts.case.mediate.history.media": "File",
        "courts.case.mediate.pdf.saved": "Chat saved to evidence.",
        "courts.case.mediate.pdf.empty": "No chat messages to save.",
        "courts.case.mediate.pdf.failed": "Failed to save chat.",
        "courts.case.mediate.pdf.caption": "Internal chat for case #{case_number}",
        "courts.mediate.pdf.title": "Internal chat for case #{case_number}",
        "courts.mediate.pdf.plaintiff": "Plaintiff: {name}",
        "courts.mediate.pdf.defendant": "Defendant: {name}",
        "courts.mediate.pdf.category": "Category: {name}",
        "courts.mediate.pdf.generated": "Generated: {timestamp}",
        "courts.mediate.pdf.media": "File",
    }
)

TEXTS_RU.update(
    {
        "button.meetings.idea": "💡 Предложить идею",
        "button.meetings.vote": "📦 Голосовать",
        "button.meetings.admin": "🛠 Админ-панель",
        "meetings.field.empty": "-",
        "meetings.field.shariah.no_conflict": "Не противоречит шариату",
        "meetings.idea.summary": (
            "Проверьте данные:\n\n"
            "Название: {title}\n"
            "Суть: {description}\n"
            "Цель: {goal}\n"
            "Шариатское основание: {shariah}\n"
            "Условия: {conditions}\n"
            "Срок/формат: {terms}"
        ),
        "meetings.idea.prompt.title": "Введите название предложения.",
        "meetings.idea.prompt.description": "Опишите суть предложения.",
        "meetings.idea.prompt.goal": "Укажите цель/пользу.",
        "meetings.idea.prompt.shariah_basis": "Выберите шариатское основание.",
        "meetings.idea.prompt.shariah_text": "Введите шариатское основание.",
        "meetings.idea.prompt.conditions": "Условия (опционально, '-' чтобы пропустить).",
        "meetings.idea.prompt.terms": "Срок/формат (опционально, '-' чтобы пропустить).",
        "meetings.idea.basis.has": "📖 Есть основание",
        "meetings.idea.basis.no": "✅ Не противоречит шариату",
        "meetings.idea.submit": "✅ Отправить на проверку",
        "meetings.idea.cancel": "❌ Отмена",
        "meetings.idea.error.title": "Введите название предложения.",
        "meetings.idea.error.description": "Введите суть предложения.",
        "meetings.idea.error.goal": "Введите цель предложения.",
        "meetings.idea.error.shariah_text": "Введите шариатское основание.",
        "meetings.idea.error.generic": "Не удалось создать предложение. Попробуйте еще раз.",
        "meetings.idea.submitted": "Ваше предложение отправлено на проверку администрации.",
        "meetings.idea.cancelled": "Создание предложения отменено.",
        "meetings.admin.card": (
            "Предложение №{proposal_id}\n"
            "Автор: {author_id}\n"
            "Дата: {created_at}\n\n"
            "Название: {title}\n"
            "Суть: {description}\n"
            "Цель: {goal}\n"
            "Шариатское основание: {shariah}\n"
            "Условия: {conditions}\n"
            "Срок/формат: {terms}"
        ),
        "meetings.admin.approve": "✅ Допустить к голосованию",
        "meetings.admin.revise": "✏️ Вернуть на доработку",
        "meetings.admin.reject": "❌ Отклонить",
        "meetings.admin.denied": "Доступ только для администраторов.",
        "meetings.admin.none": "Нет предложений на проверку.",
        "meetings.admin.error": "Не удалось обработать запрос.",
        "meetings.admin.approved": "Предложение допущено к голосованию.",
        "meetings.admin.revision.prompt": "Введите комментарий для доработки.",
        "meetings.admin.revision.error": "Комментарий обязателен.",
        "meetings.admin.revision.sent": "Предложение отправлено на доработку.",
        "meetings.admin.reject.prompt": "Введите причину отклонения.",
        "meetings.admin.reject.error": "Причина обязательна.",
        "meetings.admin.rejected": "Предложение отклонено.",
        "meetings.admin.notify.revision": "Ваше предложение возвращено на доработку: {comment}",
        "meetings.admin.notify.rejected": "Ваше предложение отклонено: {reason}",
        "meetings.vote.card": (
            "Предложение №{proposal_id}\n"
            "Название: {title}\n"
            "Краткое описание: {description}\n"
            "Шариатское основание: {shariah}\n"
            "Условия: {conditions}\n"
            "Дата окончания голосования: {ends_at}"
        ),
        "meetings.vote.for": "👍 За",
        "meetings.vote.against": "👎 Против",
        "meetings.vote.abstain": "⚪ Воздержался",
        "meetings.vote.none": "Нет активных голосований.",
        "meetings.vote.invalid": "Голосование недоступно.",
        "meetings.vote.closed": "Голосование завершено.",
        "meetings.vote.already": "Вы уже голосовали по этому предложению.",
        "meetings.vote.saved": "Голос учтен.",
        "meetings.execution.card": (
            "Исполнение №{execution_id}\n"
            "ID решения: {proposal_id}\n"
            "Название: {title}\n"
            "Ответственный: {responsible_id}\n"
            "Срок: {deadline}\n"
            "Статус: {status}\n"
            "Комментарий: {comment}\n"
            "Подтверждение: {proof}\n"
            "Причина отклонения: {rejected_reason}"
        ),
        "meetings.execution.status.in_progress": "В работе",
        "meetings.execution.status.completed": "Выполнено",
        "meetings.execution.status.failed": "Не выполнено",
        "meetings.execution.proof.file": "Файл приложен",
        "meetings.execution.none": "Нет карточек исполнения.",
        "meetings.execution.report": "Добавить отчет",
        "meetings.execution.report.prompt": "Отправьте комментарий.",
        "meetings.execution.report.error": "Комментарий обязателен.",
        "meetings.execution.proof.prompt": "Отправьте файл/ссылку (или '-' чтобы пропустить).",
        "meetings.execution.report.saved": "Отчет сохранен.",
        "meetings.execution.confirm": "✅ Подтвердить исполнение",
        "meetings.execution.reject": "❌ Отклонить",
        "meetings.execution.confirmed": "Исполнение подтверждено.",
        "meetings.execution.reject.prompt": "Введите причину отклонения.",
        "meetings.execution.reject.error": "Причина обязательна.",
        "meetings.execution.rejected": "Исполнение отклонено.",
        "meetings.execution.error": "Карточка не найдена.",
    }
)

TEXTS_RU.update(
    {
        "menu.enforcement": "Шариатский контроль",
        "menu.enforcement.title": "Шариатский контроль и проверка заявок.",
        "button.good_deeds.list": "👍 Добрые дела",
        "button.good_deeds.add": "➕ Добавить доброе дело",
        "button.good_deeds.needy": "🧍 Нуждающиеся в помощи",
        "button.good_deeds.city": "🏙 Помощь в моем городе / стране",
        "button.good_deeds.category": "💰 Закят / Садака / Фитр",
        "button.good_deeds.my": "📋 Мои добрые дела",
        "good_deeds.list.empty": "Пока нет одобренных добрых дел.",
        "good_deeds.my.empty": "У вас пока нет добрых дел.",
        "good_deeds.prompt.location": "Введите город или страну для поиска.",
        "good_deeds.prompt.category": "Выберите категорию.",
        "good_deeds.prompt.title": "Введите название доброго дела.",
        "good_deeds.prompt.description": "Опишите доброе дело подробно.",
        "good_deeds.prompt.city": "Укажите город.",
        "good_deeds.prompt.country": "Укажите страну.",
        "good_deeds.prompt.type": "Выберите тип помощи.",
        "good_deeds.prompt.amount": "Укажите сумму (или '-' если не применимо).",
        "good_deeds.prompt.comment": "Комментарий (опционально, '-' чтобы пропустить).",
        "good_deeds.prompt.confirm": "Проверьте данные и отправьте на проверку.",
        "good_deeds.created": "Доброе дело №{deed_id} отправлено на проверку.",
        "good_deeds.cancelled": "Действие отменено.",
        "good_deeds.needy.empty": "Пока нет одобренных нуждающихся.",
        "good_deeds.needy.add.prompt": "Если хотите, добавьте нуждающегося.",
        "good_deeds.needy.prompt.type": "Выберите тип нуждающегося.",
        "good_deeds.needy.prompt.city": "Укажите город.",
        "good_deeds.needy.prompt.country": "Укажите страну.",
        "good_deeds.needy.prompt.reason": "Опишите причину нужды.",
        "good_deeds.needy.prompt.zakat": "Подходит для закята?",
        "good_deeds.needy.prompt.fitr": "Подходит для фитра?",
        "good_deeds.needy.prompt.comment": "Комментарий (опционально, '-' чтобы пропустить).",
        "good_deeds.needy.created": "Запись отправлена на проверку.",
        "good_deeds.confirm.not_allowed": "Подтверждение недоступно для этого дела.",
        "good_deeds.confirm.prompt.text": "Опишите, какую помощь оказали.",
        "good_deeds.confirm.prompt.attachment": "Приложите фото/файл/ссылку (или '-' чтобы пропустить).",
        "good_deeds.confirm.error": "Не удалось сохранить подтверждение.",
        "good_deeds.confirm.saved": "Подтверждение отправлено на проверку.",
        "good_deeds.clarify.prompt.text": "Опишите уточнения по делу.",
        "good_deeds.clarify.prompt.attachment": "Приложите фото/файл/ссылку (или '-' чтобы пропустить).",
        "good_deeds.clarify.saved": "Уточнения отправлены.",
        "good_deeds.history.title": "История изменений:",
        "shariah.menu.title": "Шариатский контроль. Выберите раздел или подайте заявку.",
        "shariah.status.none": "Заявок пока нет.",
        "shariah.status.current": "Статус заявки №{app_id}: {status}.",
        "shariah.section.denied": "Раздел недоступен.",
        "shariah.section.open": "Откройте веб-панель для раздела: {section}.",
        "shariah.section.no_url": "Ссылка на веб-панель не настроена для {section}.",
        "shariah.apply.exists": "У вас уже есть активная заявка. Статус: {status}.",
        "shariah.prompt.name": "Укажите ваше полное имя.",
        "shariah.prompt.country": "В какой стране вы живете?",
        "shariah.prompt.country.custom": "Введите название страны.",
        "shariah.prompt.city": "Укажите город.",
        "shariah.prompt.education.place": "Где вы получали исламские знания?",
        "shariah.prompt.education.completed": "Есть ли законченное обучение?",
        "shariah.prompt.education.details": "Уточните, что именно вы окончили.",
        "shariah.prompt.knowledge": "В каких областях вы наиболее сильны? (можно выбрать несколько)",
        "shariah.prompt.experience": "Опишите опыт (до {limit} символов).",
        "shariah.prompt.experience.limit": "Слишком длинно. Максимум {limit} символов.",
        "shariah.prompt.responsibility": "Готовы ли вы нести ответственность за решения?",
        "shariah.submitted": "Заявка принята. Мы свяжемся для знакомства.",
        "shariah.auto_rejected": "Заявка закрыта без принятия ответственности.",
        "shariah.cancelled": "Действие отменено.",
    }
)
TEXTS_EN.update(
    {
        "button.meetings.idea": "💡 Suggest an idea",
        "button.meetings.vote": "📦 Vote",
        "button.meetings.admin": "🛠 Admin panel",
        "meetings.field.empty": "-",
        "meetings.field.shariah.no_conflict": "Does not contradict Sharia",
        "meetings.idea.summary": (
            "Review the details:\n\n"
            "Title: {title}\n"
            "Description: {description}\n"
            "Goal: {goal}\n"
            "Shariah basis: {shariah}\n"
            "Conditions: {conditions}\n"
            "Terms: {terms}"
        ),
        "meetings.idea.prompt.title": "Enter the proposal title.",
        "meetings.idea.prompt.description": "Describe the proposal.",
        "meetings.idea.prompt.goal": "Specify the goal/benefit.",
        "meetings.idea.prompt.shariah_basis": "Choose the Shariah basis.",
        "meetings.idea.prompt.shariah_text": "Provide the Shariah basis.",
        "meetings.idea.prompt.conditions": "Conditions (optional, send '-' to skip).",
        "meetings.idea.prompt.terms": "Term/format (optional, send '-' to skip).",
        "meetings.idea.basis.has": "📖 Has basis",
        "meetings.idea.basis.no": "✅ No contradiction",
        "meetings.idea.submit": "✅ Send for review",
        "meetings.idea.cancel": "❌ Cancel",
        "meetings.idea.error.title": "Enter a title.",
        "meetings.idea.error.description": "Enter a description.",
        "meetings.idea.error.goal": "Enter a goal.",
        "meetings.idea.error.shariah_text": "Provide the Shariah basis.",
        "meetings.idea.error.generic": "Failed to create the proposal. Please try again.",
        "meetings.idea.submitted": "Your proposal has been sent for admin review.",
        "meetings.idea.cancelled": "Proposal creation cancelled.",
        "meetings.admin.card": (
            "Proposal #{proposal_id}\n"
            "Author: {author_id}\n"
            "Date: {created_at}\n\n"
            "Title: {title}\n"
            "Description: {description}\n"
            "Goal: {goal}\n"
            "Shariah basis: {shariah}\n"
            "Conditions: {conditions}\n"
            "Terms: {terms}"
        ),
        "meetings.admin.approve": "✅ Approve for voting",
        "meetings.admin.revise": "✏️ Request revision",
        "meetings.admin.reject": "❌ Reject",
        "meetings.admin.denied": "Admins only.",
        "meetings.admin.none": "No proposals for review.",
        "meetings.admin.error": "Request failed.",
        "meetings.admin.approved": "Proposal approved for voting.",
        "meetings.admin.revision.prompt": "Enter a revision comment.",
        "meetings.admin.revision.error": "Comment is required.",
        "meetings.admin.revision.sent": "Revision request sent.",
        "meetings.admin.reject.prompt": "Enter the rejection reason.",
        "meetings.admin.reject.error": "Reason is required.",
        "meetings.admin.rejected": "Proposal rejected.",
        "meetings.admin.notify.revision": "Your proposal needs revision: {comment}",
        "meetings.admin.notify.rejected": "Your proposal was rejected: {reason}",
        "meetings.vote.card": (
            "Proposal #{proposal_id}\n"
            "Title: {title}\n"
            "Short description: {description}\n"
            "Shariah basis: {shariah}\n"
            "Conditions: {conditions}\n"
            "Voting ends: {ends_at}"
        ),
        "meetings.vote.for": "👍 For",
        "meetings.vote.against": "👎 Against",
        "meetings.vote.abstain": "⚪ Abstain",
        "meetings.vote.none": "No active votes.",
        "meetings.vote.invalid": "Voting is not available.",
        "meetings.vote.closed": "Voting is closed.",
        "meetings.vote.already": "You already voted on this proposal.",
        "meetings.vote.saved": "Your vote has been recorded.",
        "meetings.execution.card": (
            "Execution #{execution_id}\n"
            "Decision ID: {proposal_id}\n"
            "Title: {title}\n"
            "Responsible: {responsible_id}\n"
            "Deadline: {deadline}\n"
            "Status: {status}\n"
            "Comment: {comment}\n"
            "Proof: {proof}\n"
            "Rejection reason: {rejected_reason}"
        ),
        "meetings.execution.status.in_progress": "In progress",
        "meetings.execution.status.completed": "Completed",
        "meetings.execution.status.failed": "Failed",
        "meetings.execution.proof.file": "File attached",
        "meetings.execution.none": "No execution cards yet.",
        "meetings.execution.report": "Add report",
        "meetings.execution.report.prompt": "Send a comment.",
        "meetings.execution.report.error": "Comment is required.",
        "meetings.execution.proof.prompt": "Send a file/link (or '-' to skip).",
        "meetings.execution.report.saved": "Report saved.",
        "meetings.execution.confirm": "✅ Confirm execution",
        "meetings.execution.reject": "❌ Reject",
        "meetings.execution.confirmed": "Execution confirmed.",
        "meetings.execution.reject.prompt": "Enter rejection reason.",
        "meetings.execution.reject.error": "Reason is required.",
        "meetings.execution.rejected": "Execution rejected.",
        "meetings.execution.error": "Execution card not found.",
    }
)

TEXTS_EN.update(
    {
        "menu.enforcement": "Shariah control",
        "menu.enforcement.title": "Shariah control and application review.",
        "button.good_deeds.list": "👍 Good deeds",
        "button.good_deeds.add": "➕ Add good deed",
        "button.good_deeds.needy": "🧍 People in need",
        "button.good_deeds.city": "🏙 Help in my city / country",
        "button.good_deeds.category": "💰 Zakat / Sadaqa / Fitr",
        "button.good_deeds.my": "📋 My good deeds",
        "good_deeds.list.empty": "No approved good deeds yet.",
        "good_deeds.my.empty": "You have no good deeds yet.",
        "good_deeds.prompt.location": "Enter a city or country to search.",
        "good_deeds.prompt.category": "Choose a category.",
        "good_deeds.prompt.title": "Enter the good deed title.",
        "good_deeds.prompt.description": "Describe the good deed in detail.",
        "good_deeds.prompt.city": "Enter the city.",
        "good_deeds.prompt.country": "Enter the country.",
        "good_deeds.prompt.type": "Choose the help type.",
        "good_deeds.prompt.amount": "Enter amount (or '-' if not applicable).",
        "good_deeds.prompt.comment": "Comment (optional, '-' to skip).",
        "good_deeds.prompt.confirm": "Review the details and send for review.",
        "good_deeds.created": "Good deed #{deed_id} sent for review.",
        "good_deeds.cancelled": "Action cancelled.",
        "good_deeds.needy.empty": "No approved needy entries yet.",
        "good_deeds.needy.add.prompt": "You can add a needy entry if needed.",
        "good_deeds.needy.prompt.type": "Choose the type of needy person.",
        "good_deeds.needy.prompt.city": "Enter the city.",
        "good_deeds.needy.prompt.country": "Enter the country.",
        "good_deeds.needy.prompt.reason": "Describe the reason for need.",
        "good_deeds.needy.prompt.zakat": "Eligible for zakat?",
        "good_deeds.needy.prompt.fitr": "Eligible for fitr?",
        "good_deeds.needy.prompt.comment": "Comment (optional, '-' to skip).",
        "good_deeds.needy.created": "Entry sent for review.",
        "good_deeds.confirm.not_allowed": "Confirmation is not available for this deed.",
        "good_deeds.confirm.prompt.text": "Describe the help you provided.",
        "good_deeds.confirm.prompt.attachment": "Attach photo/file/link (or '-' to skip).",
        "good_deeds.confirm.error": "Failed to save confirmation.",
        "good_deeds.confirm.saved": "Confirmation sent for review.",
        "good_deeds.clarify.prompt.text": "Provide clarifications for the deed.",
        "good_deeds.clarify.prompt.attachment": "Attach photo/file/link (or '-' to skip).",
        "good_deeds.clarify.saved": "Clarification sent.",
        "good_deeds.history.title": "Change history:",
        "shariah.menu.title": "Shariah control. Choose a section or submit an application.",
        "shariah.status.none": "No applications yet.",
        "shariah.status.current": "Application #{app_id} status: {status}.",
        "shariah.section.denied": "Section is not available.",
        "shariah.section.open": "Open the web panel for: {section}.",
        "shariah.section.no_url": "Web panel URL is not configured for {section}.",
        "shariah.apply.exists": "You already have an active application. Status: {status}.",
        "shariah.prompt.name": "Enter your full name.",
        "shariah.prompt.country": "Which country do you live in?",
        "shariah.prompt.country.custom": "Enter the country name.",
        "shariah.prompt.city": "Enter the city.",
        "shariah.prompt.education.place": "Where did you study Islamic knowledge?",
        "shariah.prompt.education.completed": "Do you have completed education?",
        "shariah.prompt.education.details": "Please specify what you completed.",
        "shariah.prompt.knowledge": "Which areas are you strongest in? (select multiple)",
        "shariah.prompt.experience": "Describe your experience (up to {limit} chars).",
        "shariah.prompt.experience.limit": "Too long. Maximum {limit} characters.",
        "shariah.prompt.responsibility": "Are you ready to take responsibility for decisions?",
        "shariah.submitted": "Application received. We will contact you for a meeting.",
        "shariah.auto_rejected": "Application closed without accepting responsibility.",
        "shariah.cancelled": "Action cancelled.",
    }
)

TEXTS: Dict[str, Dict[str, str]] = {
    "ru": TEXTS_RU,
    "en": TEXTS_EN,
    "ar": TEXTS_AR,
    "de": TEXTS_EN,
    "tr": TEXTS_EN,
}

LANGUAGE_LABELS: Dict[str, Dict[str, str]] = {
    "ru": {"ru": "Русский", "en": "English", "ar": "العربية", "de": "Немецкий", "tr": "Турецкий", "dev": "DEV"},
    "en": {"ru": "Russian", "en": "English", "ar": "Arabic", "de": "German", "tr": "Turkish", "dev": "DEV"},
    "ar": {"ru": "الروسية", "en": "الإنجليزية", "ar": "العربية", "de": "الألمانية", "tr": "التركية", "dev": "DEV"},
    "de": {"ru": "Russisch", "en": "Englisch", "ar": "Arabisch", "de": "Deutsch", "tr": "Türkisch", "dev": "DEV"},
    "tr": {"ru": "Rusça", "en": "İngilizce", "ar": "Arapça", "de": "Almanca", "tr": "Türkçe", "dev": "DEV"},
}


def resolve_language(*codes: Optional[str]) -> str:
    for code in codes:
        if not code:
            continue
        normalized = code.lower()
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return DEFAULT_LANGUAGE


def get_text(key: str, lang_code: str, **kwargs) -> str:
    language = (lang_code or DEFAULT_LANGUAGE).lower()
    # 1) DB-backed runtime translations
    if language != "dev":
        db_text = _RUNTIME_TEXTS.get(language, {}).get(key)
        if db_text is not None:
            try:
                return db_text.format(**kwargs) if kwargs else db_text
            except Exception:
                return db_text

    # 2) Built-in safe fallback
    if language == "dev":
        text = key
    else:
        text = TEXTS.get(language, {}).get(key)
        if text is None:
            text = (
                TEXTS.get("en", {}).get(key)
                or TEXTS.get(DEFAULT_LANGUAGE, {}).get(key)
                or key
            )
    try:
        return text.format(**kwargs) if kwargs else text
    except Exception:
        return text


def get_language_label(locale_code: str, viewer_language: str) -> str:
    viewer = (viewer_language or DEFAULT_LANGUAGE).lower()
    labels = LANGUAGE_LABELS.get(viewer, LANGUAGE_LABELS[DEFAULT_LANGUAGE])
    return labels.get(locale_code, locale_code.upper())
