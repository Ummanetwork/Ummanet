-- Minimal seed for Russian texts
INSERT INTO prompts(key, lang, text) VALUES
('menu.start_button','ru','🌟 Начать работу') ON CONFLICT (key, lang) DO NOTHING;
INSERT INTO prompts(key, lang, text) VALUES
('menu.title','ru','Выберите раздел:') ON CONFLICT (key, lang) DO NOTHING;
INSERT INTO prompts(key, lang, text) VALUES
('menu.btn.contracts','ru','📝 Договоры') ON CONFLICT (key, lang) DO NOTHING;
INSERT INTO prompts(key, lang, text) VALUES
('menu.btn.ask_scholars','ru','❔ Обратиться к учёным') ON CONFLICT (key, lang) DO NOTHING;
INSERT INTO prompts(key, lang, text) VALUES
('menu.btn.ready_doc','ru','📃 Получить готовый документ') ON CONFLICT (key, lang) DO NOTHING;
INSERT INTO prompts(key, lang, text) VALUES
('menu.btn.court','ru','✍️ Подать в суд') ON CONFLICT (key, lang) DO NOTHING;
