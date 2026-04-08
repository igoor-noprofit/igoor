"""
Biorecorder Plugin - Record biographical information through guided Q&A
"""
import json
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from version import __appname__
from plugins.baseplugin.baseplugin import Baseplugin
from plugin_manager import hookimpl
from utils import setup_logger, get_base_language_code


class Biorecorder(Baseplugin):
    """Plugin for recording biographical information through Q&A"""

    def __init__(self, plugin_name, pm):
        self.pm = pm
        super().__init__(plugin_name, pm)
        self.router = None
        self.questions: List[Dict] = []
        self.answers: Dict[str, Dict] = {}
        self._router_registered = False

    @hookimpl
    def startup(self):
        """Initialize plugin: load questions, setup storage, register routes"""
        self.logger = setup_logger(f'plugins.biorecorder', os.path.join(os.getenv('APPDATA'), __appname__), separate_plugin_log=False)


        # Load questions based on user language
        self._load_questions()

        # Load existing answers
        self._load_answers()

        # Setup FastAPI router
        self._ensure_router()

        # Register router with FastAPI app
        fastapi_app = getattr(self.pm, "fastapi_app", None)
        if fastapi_app and not self._router_registered:
            fastapi_app.include_router(self.router)
            self._router_registered = True
            self.logger.info("Biorecorder router registered")

        self.is_loaded = True
        self.mark_ready()
        self.logger.info(f"Biorecorder started with {len(self.questions)} questions, {len(self.answers)} answers")

    def _load_questions(self):
        """Load questions from locales folder based on user language"""
        lang_code = get_base_language_code(self.lang, default_lang="en")

        # Map language codes to locale folder names
        locale_map = {
            "en": "en_EN",
            "fr": "fr_FR",
            "it": "it_IT"
        }
        locale_folder = locale_map.get(lang_code, "en_EN")

        questions_path = Path(self._app_plugin_folder) / "locales" / locale_folder / f"questions_{locale_folder}.json"

        if not questions_path.exists():
            # Fallback to English
            questions_path = Path(self._app_plugin_folder) / "locales" / "en_EN" / "questions_en_EN.json"
            self.logger.warning(f"Questions file not found for {lang_code}, falling back to English")

        if questions_path.exists():
            with open(questions_path, 'r', encoding='utf-8') as f:
                raw_questions = json.load(f)

            # Flatten questions for indexing
            self.questions = []
            for category, questions in raw_questions.items():
                for q in questions:
                    self.questions.append({
                        "category": category,
                        "text": q["text"],
                        "mandatory": q.get("mandatory", False),
                        "instructions": q.get("instructions", "")
                    })
            self.logger.info(f"Loaded {len(self.questions)} questions from {locale_folder}")
        else:
            self.logger.error(f"Questions file not found: {questions_path}")
            self.questions = []

    def _load_answers(self):
        """Load existing answers from answers.json"""
        answers_file = Path(self.plugin_folder) / "answers.json"
        if answers_file.exists():
            try:
                with open(answers_file, 'r', encoding='utf-8') as f:
                    self.answers = json.load(f)
                self.logger.info(f"Loaded {len(self.answers)} existing answers")
            except Exception as e:
                self.logger.error(f"Error loading answers: {e}")
                self.answers = {}
        else:
            self.answers = {}

    def _save_answers(self):
        """Save answers to answers.json"""
        answers_file = Path(self.plugin_folder) / "answers.json"
        try:
            with open(answers_file, 'w', encoding='utf-8') as f:
                json.dump(self.answers, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"Saved {len(self.answers)} answers")
        except Exception as e:
            self.logger.error(f"Error saving answers: {e}")

    def _get_progress(self) -> Dict:
        """Get current progress"""
        answered = sum(1 for k in self.answers if self.answers[k].get("answer", "").strip())
        total = len(self.questions)
        return {
            "answered": answered,
            "total": total,
            "current_index": self._get_next_unanswered_index(),
            "can_generate": answered > 0
        }

    def _get_next_unanswered_index(self) -> int:
        """Find the index of the next unanswered question"""
        for i in range(len(self.questions)):
            key = str(i)
            if key not in self.answers or not self.answers.get(key, {}).get("answer", "").strip():
                return i
        return len(self.questions)  # All answered

    def _ensure_router(self):
        """Setup FastAPI routes"""
        if self.router:
            return

        self.router = APIRouter(prefix="/api/plugins/biorecorder", tags=["biorecorder"])

        @self.router.get("/data")
        async def get_data():
            return await self._get_data()

        @self.router.post("/answer")
        async def save_answer(data: dict):
            return await self._save_answer(data)

        @self.router.post("/voice_answer")
        async def save_voice_answer(index: int, audio_file: UploadFile = File(...)):
            return await self._save_voice_answer(index, audio_file)

        @self.router.get("/progress")
        async def get_progress():
            return self._get_progress()

        @self.router.post("/generate_bio")
        async def generate_bio():
            return await self._generate_bio()

        @self.router.get("/bio")
        async def get_bio():
            return await self._get_bio_content()

        @self.router.post("/reset")
        async def reset_biography():
            return await self._reset_biography()

    async def _get_data(self) -> Dict:
        result = []
        for i in range(len(self.questions)):
            q = self.questions[i]
            answer_data = self.answers.get(str(i), {})
            result.append({
                "index": i,
                "category": q["category"],
                "text": q["text"],
                "mandatory": q["mandatory"],
                "instructions": q["instructions"],
                "answer": answer_data.get("answer", ""),
                "has_audio": answer_data.get("audio_file") is not None
            })

        progress = self._get_progress()
        return {
            "questions": result,
            "progress": progress
        }

    async def _save_answer(self, data: dict):
        index = data.get("index")
        answer = data.get("answer", "").strip()

        if not isinstance(index, int) or not (0 <= index < len(self.questions)):
            raise HTTPException(status_code=400, detail="Invalid question index")

        q = self.questions[index]
        self.answers[str(index)] = {
            "question": q["text"],
            "answer": answer,
            "audio_file": None
        }
        self._save_answers()

        return {
            "status": "saved",
            "progress": self._get_progress()
        }

    async def _save_voice_answer(self, index: int, audio_file: UploadFile = File(...)):
        if not (0 <= index < len(self.questions)):
            raise HTTPException(status_code=400, detail="Invalid question index")

        # Save audio to temp file
        temp_path = Path(self.plugin_folder) / f"temp_{int(time.time())}.webm"
        try:
            audio_bytes = await audio_file.read()
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)

            # Transcribe via asrjs plugin
            text = await self._transcribe_audio(temp_path)

            # Save audio via recorder plugin
            audio_id = await self._save_audio_to_recorder(temp_path)

            # Clean up temp file
            try:
                temp_path.unlink()
            except:
                pass

            # Save answer
            q = self.questions[index]
            self.answers[str(index)] = {
                "question": q["text"],
                "answer": text,
                "audio_file": f"audio/biorecorder/{audio_id}.wav" if audio_id else None
            }
            self._save_answers()

            return {
                "status": "saved",
                "text": text,
                "audio_id": audio_id,
                "progress": self._get_progress()
            }

        except Exception as e:
            self.logger.error(f"Error in voice_answer: {e}")
            # Clean up temp file on error
            try:
                temp_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=str(e))

    async def _generate_bio(self) -> Dict:
        answered = sum(1 for k in self.answers if self.answers[k].get("answer", "").strip())
        if answered == 0:
            raise HTTPException(status_code=400, detail="No questions answered yet")

        try:
            result = await self._run_bio_generation()
            return result
        except Exception as e:
            self.logger.error(f"Error generating bio: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_bio_content(self) -> Dict:
        bio_path = Path(self.plugin_folder) / "bio.md"
        if bio_path.exists():
            return {"exists": True, "content": bio_path.read_text(encoding='utf-8')}
        return {"exists": False, "content": ""}

    async def _reset_biography(self) -> Dict:
        """Reset all biography data"""
        try:
            # Delete answers file
            answers_path = Path(self.plugin_folder) / "answers.json"
            if answers_path.exists():
                answers_path.unlink()

            # Delete bio file
            bio_path = Path(self.plugin_folder) / "bio.md"
            if bio_path.exists():
                bio_path.unlink()

            # Clear in-memory data
            self.answers = {}

            return {"status": "reset", "message": "Biography data reset successfully"}
        except Exception as e:
            self.logger.error(f"Error resetting biography: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _transcribe_audio(self, audio_path: Path) -> str:
        """Transcribe audio using asrjs plugin in the user's language"""
        asrjs = next((p for p in self.pm.plugins if getattr(p, 'plugin_name', None) == "asrjs"), None)
        if not asrjs:
            raise Exception("ASR plugin not available")

        # Save original state
        original_temp = asrjs.temp_audio_file
        original_lang = getattr(asrjs, 'lang_code', None)

        # Force user's language for transcription
        user_lang = get_base_language_code(self.lang, default_lang="en")
        asrjs.lang_code = user_lang
        asrjs.temp_audio_file = str(audio_path)

        # Temporarily clear interlocutor language override from translator
        # so transcription uses the user's own language, not the interlocutor's
        translator_settings = self.settings_manager.get_plugin_settings("translator")
        saved_interlocutor = translator_settings.get("interlocutor_language", "")
        if saved_interlocutor:
            translator_settings["interlocutor_language"] = ""

        try:
            text = await asrjs.transcribe_audio()
            return text or ""
        finally:
            # Restore original state
            if original_temp:
                asrjs.temp_audio_file = original_temp
            if original_lang:
                asrjs.lang_code = original_lang
            if saved_interlocutor:
                translator_settings["interlocutor_language"] = saved_interlocutor

    async def _save_audio_to_recorder(self, audio_path: Path) -> Optional[str]:
        """Save audio file via recorder plugin REST API"""
        try:
            import httpx

            recorder = next((p for p in self.pm.plugins if getattr(p, 'plugin_name', None) == "recorder"), None)
            if not recorder:
                self.logger.warning("Recorder plugin not available, audio not saved")
                return None

            audio_bytes = audio_path.read_bytes()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:9714/api/plugins/recorder/audio",
                    data={"plugin": "biorecorder"},
                    files={"file": ("biorecorder.webm", audio_bytes, "audio/webm")},
                    timeout=30.0
                )

            if response.status_code == 200:
                result = response.json()
                audio_id = result.get("id")
                self.logger.info(f"Audio saved to recorder, id={audio_id}, file={result.get('filename')}")
                return str(audio_id)
            else:
                self.logger.error(f"Recorder API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Error saving audio to recorder: {e}")
            return None

    async def _run_bio_generation(self) -> Dict:
        """Run the 4-step LLM process"""
        import asyncio
        from llm_manager import LLMManager

        loop = asyncio.get_event_loop()

        # Get AI settings from onboarding
        ai = self.settings_manager.get_nested(["plugins", "onboarding", "ai"], default={})
        bio = self.settings_manager.get_bio()
        bio_name = bio.get("name", "the user")

        provider = ai.get("provider")
        api_key = ai.get("api_key")
        model_name = ai.get("model_name")

        if not all([provider, api_key, model_name]):
            raise Exception("AI settings not configured in onboarding")

        # Get prompts
        prompts = self.get_my_prompts()

        # Build answers text
        answers_text = "\n\n".join(
            f"Question: {data['question']}\nAnswer: {data.get('answer', 'Not answered')}"
            for idx in sorted(self.answers.keys(), key=int)
            for data in [self.answers[idx]]
        )
        llm = LLMManager(provider, api_key, model_name, temperature=0.3)

        # Step 1: 3rd person narrative
        self.logger.info("Step 1/4: Converting to narrative...")
        narrative = await loop.run_in_executor(
            None, llm.invoke, prompts.get("narrative_conversion", {}).get("system", ""),
            f"Name: {bio_name}\n\n{answers_text}"
        )
        narrative_text = narrative.content if hasattr(narrative, 'content') else str(narrative)

        # Step 2: Structure into chapters
        self.logger.info("Step 2/4: Structuring into chapters...")
        structured = await loop.run_in_executor(
            None, llm.invoke, prompts.get("chapter_structure", {}).get("system", ""),
            narrative_text
        )
        structured_text = structured.content if hasattr(structured, 'content') else str(structured)

        # Step 3: Verify completeness
        self.logger.info("Step 3/4: Verifying completeness...")
        verified = await loop.run_in_executor(
            None, llm.invoke, prompts.get("verification", {}).get("system", ""),
            f"Original:\n{answers_text}\n\nStructured:\n{structured_text}"
        )
        bio_content = verified.content if hasattr(verified, 'content') else str(verified)

        # Save bio.md
        bio_path = Path(self.plugin_folder) / "bio.md"
        bio_path.write_text(bio_content, encoding='utf-8')
        self.logger.info(f"Step 3/4 complete. Bio saved to {bio_path}")

        # Step 4: Extract and merge style
        self.logger.info("Step 4/4: Extracting style...")
        style_result = await loop.run_in_executor(
            None, llm.invoke, prompts.get("style_extraction", {}).get("system", ""),
            answers_text
        )
        new_style = style_result.content.strip() if hasattr(style_result, 'content') else str(style_result).strip()

        # Merge with existing style
        existing_style = bio.get("style", "")
        if new_style:
            merged_style = f"{existing_style}\n{new_style}" if existing_style else new_style

            # Update onboarding settings
            self.settings_manager.update_plugin_settings("onboarding", {
                "bio": {"style": merged_style}
            }, self.pm)
            self.logger.info("Style updated in onboarding settings")

        return {
            "status": "complete",
            "bio_file": str(bio_path),
            "style_updated": bool(new_style)
        }
