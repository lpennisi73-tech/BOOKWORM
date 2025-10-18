"""
Internationalization (i18n) system for KernelCustom Manager
"""

import json
import os
from pathlib import Path
import locale


class I18n:
    """Translation manager"""

    def __init__(self):
        self.config_file = Path.home() / ".config" / "kernelcustom-manager" / "language.conf"
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.current_lang = self._load_saved_language() or self._detect_language()
        self.translations = {}
        self.load_translations()

    def _detect_language(self):
        """Detect system language"""
        try:
            # Try to get system locale
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                lang = system_locale.split('_')[0].lower()
                # Support only French and English for now
                return 'fr' if lang == 'fr' else 'en'
        except:
            pass

        # Check environment variable
        lang = os.environ.get('LANG', '').lower()
        if lang.startswith('fr'):
            return 'fr'

        # Default to English
        return 'en'

    def load_translations(self):
        """Load translation files"""
        translations_dir = Path(__file__).parent.parent / "translations"
        translations_dir.mkdir(exist_ok=True)

        for lang_file in translations_dir.glob("*.json"):
            lang_code = lang_file.stem
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang_code] = json.load(f)
            except Exception as e:
                print(f"Error loading translation {lang_code}: {e}")

    def _load_saved_language(self):
        """Load saved language preference"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return f.read().strip()
        except:
            pass
        return None

    def _save_language(self, lang_code):
        """Save language preference"""
        try:
            with open(self.config_file, 'w') as f:
                f.write(lang_code)
        except:
            pass

    def set_language(self, lang_code):
        """Set current language"""
        if lang_code in self.translations:
            self.current_lang = lang_code
            self._save_language(lang_code)
            return True
        return False

    def get_language(self):
        """Get current language"""
        return self.current_lang

    def _(self, key, **kwargs):
        """Translate a key"""
        # Get translation for current language
        translation = self.translations.get(self.current_lang, {})

        # Navigate through nested keys (e.g., "tab.kernels")
        keys = key.split('.')
        for k in keys:
            if isinstance(translation, dict):
                translation = translation.get(k)
                if translation is None:
                    return key  # Return key if not found
            else:
                return key

        # Replace placeholders if provided
        if kwargs and isinstance(translation, str):
            try:
                translation = translation.format(**kwargs)
            except KeyError:
                pass

        return translation if translation is not None else key

    def get_available_languages(self):
        """Get list of available languages"""
        return list(self.translations.keys())


# Global instance
_i18n_instance = None

def get_i18n():
    """Get global i18n instance"""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance

def _(key, **kwargs):
    """Shortcut for translation"""
    return get_i18n()._(key, **kwargs)
