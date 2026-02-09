# Contributing to IGOOR

Thank you for your interest in contributing to **IGOOR** — an open, free, and human-centered conversational application designed for people with neurodegenerative diseases or paralysis.

## 🧱 Development Setup

### Requirements

Please refer to the [`README.md`](./README.md) for detailed setup instructions, including:

* Supported OS: **Windows 10/11**
* **Python 3.10.6**
* **Microsoft Edge WebView2 Runtime**
* **Groq API Key** for AI inference
* **FFmpeg** (for TTS plugins)
* **Virtual environment setup**
* Required Python libraries (`requirements.txt`)

---

## 🧩 Repository Access and Workflow

### 1. Branch Protection

* The `main` branch is **protected**.
* You cannot push directly to it.
* All contributions must come via **feature branches** and **pull requests (PRs)**.

### 2. Workflow

1. **Create a new branch** for your work:

   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Make your changes** (follow the style and structure of existing code).
3. **Commit** with a clear, descriptive message:

   ```
   git commit -m "Add Vosk plugin improvements for French language"
   ```
4. **Push your branch**:

   ```bash
   git push origin feature/your-feature-name
   ```
5. **Open a Pull Request (PR)** to `main`.

---

## 🧪 Testing and Code Style

* Test your changes before submitting a PR.
* Ensure your code **does not break existing functionality**.
* Follow existing **naming conventions** and **file organization**.
* Keep commits **atomic and descriptive**.

If your contribution affects plugin behavior, include:

* A short **description** of the change.
* Any **dependencies or external tools** required.

---

## 🧠 Plugins

* Plugins are managed through the `settings.json` file in the user data folder.
* Follow the examples and directory structure shown in the README.
* For language or model-specific updates, verify:

  * Vosk / Whisper model support
  * TTS provider language availability
  * Proper embedding model compatibility for RAG

---

## 🧰 Debugging and Logs

* Logs are stored in:

  ```
  IGOOR_FOLDER/logs/
  ```
* Review logs for runtime errors or warnings before submitting code.
* If your PR involves LLM interaction or RAG improvements, verify JSON logging of llm_invocations in the same folder.

---

## 📘 Contribution Review

All pull requests will be reviewed by **Carlo Giordano**, the project maintainer.

A PR may be:

* Accepted as-is
* Accepted after requested changes
* Declined with feedback

Please be patient and open to review discussions.


## ❤️ Acknowledgments

IGOOR is authored by **Carlo Giordano**, based on a concept by **Igor Novitzki**.
Original UX/UI by **Zenoid**.