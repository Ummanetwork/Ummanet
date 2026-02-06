from app.services.i18n.localization import get_language_label


def get_lang_buttons(
    locales: list[str], viewer_lang: str
) -> list[tuple[str, str]]:
    buttons = []
    for index, locale in enumerate(locales, start=1):
        buttons.append((get_language_label(locale, viewer_lang), str(index)))
    return buttons
