from ..utils.verbose_utils import warn


class LanguageResolver:
    def __init__(
        self, language: str, valid_languages: list[str], verbose: int = 0
    ) -> None:
        self.language = language
        self.valid_languages = valid_languages
        self.unvalid_languages = set()

        self.check_default_language(verbose=verbose)

    def check_default_language(self, verbose: int) -> None:
        if self.language not in self.valid_languages:
            warn(
                f"Default language '{self.language}' is not in"
                f" valid_languages={self.valid_languages}. "
                f"Falling back to 'en'.",
                verbose,
            )
            self.language = "en"

    def resolve_language(self, raw_lang: str | None, context: str, verbose: int) -> str:
        if raw_lang is None:
            warn(
                f"  No language tag found for {context}."
                f" Falling back to '{self.language}'.",
                verbose,
            )
            return self.language

        if raw_lang not in self.valid_languages:
            if raw_lang not in self.unvalid_languages:
                warn(
                    f"  Language '{raw_lang}' is not in"
                    f" valid_languages={self.valid_languages} "
                    f"({context}). Falling back to '{self.language}'.",
                    verbose,
                )
                self.unvalid_languages.add(raw_lang)
            return self.language

        return raw_lang
