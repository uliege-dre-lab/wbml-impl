from ..utils.verbose_utils import warn


class LanguageResolver:
    """
    A class to resolve language tags for labels and descriptions in Wikibase.
    """

    def __init__(self, language: str, valid_languages: list[str]) -> None:
        """
        Initialize the LanguageResolver.
        Inputs:
        - language: The default language to use.
        - valid_languages: A list of valid languages supported by the Wikibase instance.
        """
        self.language = language
        self.valid_languages = valid_languages
        self.unvalid_languages = set()

        self.check_default_language()

    def check_default_language(self) -> None:
        """
        Check if the default language is supported by the Wikibase instance.
        If not, raise a ValueError.
        """
        if self.language not in self.valid_languages:
            raise ValueError(
                f"Default language '{self.language}'"
                f" is not supported by the Wikibase instance. "
                f"Valid languages: {self.valid_languages}."
            )

    def resolve_language(self, raw_lang: str | None, context: str, verbose: int) -> str:
        """
        Resolve the language tag for a given label, alias, or description.
        If raw language tag is None, return the default language and log a warning.
        If raw language tag is not in the list of valid languages, raise a ValueError.
        Inputs:
        - raw_lang: The raw language tag to resolve.
        - context: A string describing the context (e.g., "label for Q123").
        - verbose: Verbosity level for logging.
         Outputs:
        - The resolved language tag to use for the label, alias, or description.
        """
        if raw_lang is None:
            warn(
                f"  No language tag found for {context}."
                f" Falling back to '{self.language}'.",
                verbose,
            )
            return self.language

        if raw_lang not in self.valid_languages:
            raise ValueError(
                f"Invalid language tag '{raw_lang}' for {context}. "
                f"Valid languages: {self.valid_languages}."
            )

        return raw_lang
