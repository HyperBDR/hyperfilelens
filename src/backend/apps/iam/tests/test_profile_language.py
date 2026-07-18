from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from apps.iam.profile_models import Profile


class ProfileLanguageTests(SimpleTestCase):
    def test_profile_uses_locale_neutral_english_defaults(self) -> None:
        profile = Profile()

        self.assertEqual(profile.language, "en")
        self.assertEqual(profile.timezone, "UTC")

    @override_settings(LANGUAGES=(("en", "English"), ("fr", "French")))
    def test_installed_language_pack_locale_is_valid(self) -> None:
        profile = Profile(language="fr")

        profile.clean()

    @override_settings(LANGUAGES=(("en", "English"),))
    def test_uninstalled_language_pack_locale_is_rejected(self) -> None:
        profile = Profile(language="fr")

        with self.assertRaisesMessage(ValidationError, "Language 'fr' is not installed"):
            profile.clean()
