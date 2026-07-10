from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl


class Translator(Baseplugin):
    """Translator plugin.

    Owns the translation settings (interlocutor_language, translate_incoming,
    translate_outgoing, translation_model_name).

    The actual translation logic lives in Baseplugin.translate_for_interlocutor()
    which is inherited by all TTS and ASR plugins.  They read this plugin's
    settings via SettingsManager.get_plugin_settings("translator") — so when
    this plugin is not activated those settings don't exist and translation is
    completely skipped with zero overhead.
    """

    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)

    @hookimpl
    def startup(self):
        self.settings = self.get_my_settings()
        self.mark_ready()

    @hookimpl
    def settings_updated(self, plugin_name, new_settings):
        if plugin_name == self.plugin_name:
            self.settings = self.get_my_settings()
