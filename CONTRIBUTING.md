# Contributing to IGOOR

Thank you for your interest in contributing to **IGOOR** — an open, free, and human-centered conversational application designed for people with neurodegenerative diseases or paralysis.

This document outlines how to contribute **safely and respectfully** during the project’s **private development phase**.

---

## ⚠️ Notice of Confidential Development

IGOOR is currently under **private development**.
While the final version of the software **will be released** as free/libre under the **GPLv3 License**, the **current codebase is confidential**.

By accessing this repository, you agree to the following terms:

1. **Confidentiality:**
   You must **not share, distribute, or disclose** any code, documentation, or materials related to IGOOR outside the development team.

2. **Access Purpose:**
   Your access is granted **solely for contributing to IGOOR’s development**. Do not use the codebase or data for any other purpose.

3. **Contribution Licensing:**
   All contributions (code, documentation, assets, etc.) will be automatically licensed under **GPLv3** upon the public release of the software.

4. **Breach of Terms:**
   Any breach of confidentiality may result in **immediate removal** from the project and potential legal or administrative action.

---

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
* If your PR involves LLM interaction or RAG improvements, verify JSON logging in:

  ```
  IGOOR_FOLDER/logs/llm_invocations/
  ```

---

## 📘 Contribution Review

All pull requests will be reviewed by **Carlo Giordano**, the project maintainer.

A PR may be:

* Accepted as-is
* Accepted after requested changes
* Declined with feedback

Please be patient and open to review discussions.

---

## 🌐 Future Open Source Transition

Once IGOOR’s private phase is complete:

* The repository will become public under **GPLv3**.
* Contributors will be fully credited.
* All prior contributions will be automatically covered under GPLv3.

---

## ❤️ Acknowledgments

IGOOR is authored by **Carlo Giordano**, based on a concept by **Igor Novitzki**.
Original UX/UI by **Zenoid**.

Thank you for helping shape IGOOR into a powerful, ethical, and inclusive tool.