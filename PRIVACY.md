# IGOOR Privacy Policy

_Last updated: 2026-09-04_

IGOOR is a free, open-source assistive communication application for people
with neurodegenerative diseases and paralysis. It is developed by the
**Association loi 1901 IGOOR** (the "Association"). This policy explains, in
plain language, what happens to your data when you use IGOOR.

**The short version:** your data lives on your computer. IGOOR contains no
telemetry, no analytics, no advertising and no tracking of any kind. We
operate no servers and never receive your data. Information leaves your
computer **only** if you deliberately enable and configure optional cloud
AI services with your own account and API keys.

## 1. Data stored on your device

IGOOR stores the following on your computer (in your user profile folder),
and nowhere else:

- **Your profile** — the name, preferred language, communication style and
  optional personal background you provide during onboarding. This may
  include health-related information you choose to enter (for example, your
  diagnosis), because it helps the assistant communicate better with you.
- **Conversations** — your conversation history.
- **Memory** — long- and short-term memory the assistant builds from your
  conversations to remember what matters to you.
- **Your documents** — if you use the document assistant (RAG) feature, the
  texts you add are indexed on your device.
- **Settings and API keys** — your preferences and the API keys you enter
  for optional cloud services.
- **Local logs** — technical logs and a local history of AI requests, used
  for troubleshooting.
- **Temporary voice recordings** — short audio clips captured for speech
  recognition are deleted automatically.

**Uninstalling IGOOR does not delete your data — this is deliberate.** Some
of what IGOOR stores, such as a cloned voice created from recordings of a
person who can no longer speak, can never be recreated. To protect you from
accidental loss, uninstalling the app always leaves your data in place, so
you can reinstall and find everything exactly as it was.

If you want to erase everything, do both of the following:

1. uninstall IGOOR, then
2. delete the folder `igoor` in your user profile (`%APPDATA%\igoor`).

Because we never receive this data, no request to us is necessary to
exercise your data-protection rights: deleting that folder on your device
is complete deletion.

## 2. Data processed on your device

When you use the local (default) AI options, the following never leaves your
computer: speech recognition, text-to-speech, memory and document indexing,
and all AI-driven interface features that run with local models.

Wake-word detection ("hey IGOOR") is **always** processed locally on your
device, whatever settings you choose.

## 3. Optional cloud services (only if you enable them)

IGOOR can use external AI services **if you choose to** and configure them
with your own API keys:

- **Cloud language models** (for example Mistral, Groq, OpenAI) to generate
  replies. When enabled, your messages — and relevant parts of your profile
  and memory, so the assistant stays personal — are sent to the provider you
  chose.
- **Cloud speech recognition** (for example Whisper via Groq, Voxtral via
  Mistral). When enabled, your voice audio is sent to that provider for
  transcription.
- **Cloud text-to-speech** (for example ElevenLabs, Speechify). When enabled,
  the text to be spoken is sent to that provider.
- **Weather information**, if you use it: the location you provide is sent
  to a weather service.

These transfers are governed by the respective providers' privacy policies.
We do not see, receive or store anything you send to them. You can switch
every one of these features off or replace them with local alternatives at
any time in the settings.

## 4. Eye tracking and other input devices

IGOOR receives input events (from eye trackers, switches or other
accessibility devices) exactly like keyboard and mouse input. The app does
not record, store or transmit gaze data. Eye-tracker software and drivers
are provided by their manufacturers under their own privacy policies.

## 5. What IGOOR does not do

- No telemetry, analytics, crash reporting or usage statistics.
- No advertising or tracking.
- No accounts, no sign-up, no data collection by the Association.
- No access to your contacts, files or other applications beyond the
  documents you explicitly add.

## 6. Installation and updates

If you installed IGOOR from the Microsoft Store, installation and updates
are handled by Microsoft under the
[Microsoft Privacy Statement](https://privacy.microsoft.com/). If you
installed IGOOR from our GitHub releases, no information is sent to us.

## 7. Changes to this policy

If this policy changes, the updated version ships with the app and is
published in the IGOOR source repository
(<https://github.com/igoor-noprofit/igoor>), where the complete source code
is available under the GNU AGPL v3 license.

## 8. Contact

Questions about this policy or about IGOOR and privacy:
**[support@igoor.org](mailto:support@igoor.org)**
