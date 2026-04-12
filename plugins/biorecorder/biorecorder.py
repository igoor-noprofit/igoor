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
from fastapi.responses import JSONResponse, FileResponse

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

        @self.router.post("/update_bio")
        async def update_bio(data: dict):
            return await self._update_bio_content(data)

        @self.router.post("/reset")
        async def reset_biography():
            return await self._reset_biography()

        @self.router.get("/voice_sample")
        async def get_voice_sample():
            return self._get_voice_sample_info()

        @self.router.get("/voice_sample/file")
        async def get_voice_sample_file():
            return await self._get_voice_sample_file()

        @self.router.delete("/voice_sample")
        async def delete_voice_sample():
            return await self._delete_voice_sample()

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
            audio_result = await self._save_audio_to_recorder(temp_path)

            # Clean up temp file
            try:
                temp_path.unlink()
            except:
                pass

            # Save answer
            q = self.questions[index]
            audio_file_ref = audio_result.get("filename") if audio_result else None
            self.answers[str(index)] = {
                "question": q["text"],
                "answer": text,
                "audio_file": audio_file_ref
            }
            self._save_answers()

            return {
                "status": "saved",
                "text": text,
                "audio_id": audio_result.get("id") if audio_result else None,
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
            # Generate voice sample from recorded answers (non-critical)
            try:
                self._generate_voice_sample()
            except Exception as e:
                self.logger.warning(f"Voice sample generation failed (non-critical): {e}")
            return result
        except Exception as e:
            self.logger.error(f"Error generating bio: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def _get_bio_content(self) -> Dict:
        bio_path = Path(self.plugin_folder) / "bio.md"
        if bio_path.exists():
            return {"exists": True, "content": bio_path.read_text(encoding='utf-8')}
        return {"exists": False, "content": ""}

    async def _update_bio_content(self, data: dict) -> Dict:
        """Update the bio document with edited content from the frontend"""
        content = data.get("content", "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content cannot be empty")

        bio_path = Path(self.plugin_folder) / "bio.md"
        try:
            bio_path.write_text(content, encoding='utf-8')
            self.logger.info("Bio content updated via editor")
            return {"status": "updated", "message": "Biography updated successfully"}
        except Exception as e:
            self.logger.error(f"Error updating bio content: {e}")
            raise HTTPException(status_code=500, detail=str(e))

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

            # Delete voice sample file
            voice_sample_path = Path(self.plugin_folder) / "voice_sample.wav"
            if voice_sample_path.exists():
                voice_sample_path.unlink()

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

    async def _save_audio_to_recorder(self, audio_path: Path) -> Optional[Dict]:
        """Save audio file via recorder plugin REST API. Returns dict with id and filename."""
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
                filename = result.get("filename")
                self.logger.info(f"Audio saved to recorder, id={audio_id}, file={filename}")
                return {"id": str(audio_id), "filename": filename}
            else:
                self.logger.error(f"Recorder API error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Error saving audio to recorder: {e}")
            return None

    def _validate_llm_result(self, result, step_name: str) -> str:
        """Extract text from LLM result and validate it's non-empty. Returns the text."""
        text = result.content.strip() if hasattr(result, 'content') else str(result).strip()
        if not text:
            raise ValueError(f"{step_name} returned empty content")
        return text

    async def _run_llm_step_with_retry(self, llm, system_prompt: str, user_prompt: str, step_name: str, loop) -> str:
        """Run a single LLM step with one retry on empty result."""
        result = await loop.run_in_executor(
            None, llm.invoke, system_prompt, user_prompt
        )
        try:
            return self._validate_llm_result(result, step_name)
        except ValueError:
            self.logger.warning(f"{step_name} returned empty, retrying once...")
            result = await loop.run_in_executor(
                None, llm.invoke, system_prompt, user_prompt
            )
            return self._validate_llm_result(result, step_name)

    async def _run_bio_generation(self) -> Dict:
        """Run the 5-step LLM process with validation at each step"""
        import asyncio
        import json as json_module
        from llm_manager import LLMManager

        loop = asyncio.get_event_loop()

        # Get AI settings from onboarding
        ai = self.settings_manager.get_nested(["plugins", "onboarding", "ai"], default={})
        bio = self.settings_manager.get_bio()
        bio_name = bio.get("name", "the user")

        provider = ai.get("provider")
        api_key = ai.get("api_key")
        model_name = ai.get("model_name")

        # Override model with biorecorder-specific setting if available
        bio_settings = self.settings_manager.get_plugin_settings("biorecorder")
        if bio_settings and bio_settings.get("model_name"):
            model_name = bio_settings["model_name"]
            self.logger.info(f"Using biorecorder-specific model: {model_name}")

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
        self.logger.info("Step 1/5: Converting to narrative...")
        narrative_text = await self._run_llm_step_with_retry(
            llm,
            prompts.get("narrative_conversion", {}).get("system", ""),
            f"Name: {bio_name}\n\n{answers_text}",
            "Step 1 (narrative_conversion)",
            loop
        )

        # Step 2: Structure into chapters
        self.logger.info("Step 2/5: Structuring into chapters...")
        structured_text = await self._run_llm_step_with_retry(
            llm,
            prompts.get("chapter_structure", {}).get("system", ""),
            narrative_text,
            "Step 2 (chapter_structure)",
            loop
        )

        # Step 3+4: Verify completeness + completeness check (with retry loop)
        max_completeness_retries = 3
        bio_content = None

        for attempt in range(1, max_completeness_retries + 1):
            # Step 3: Verify completeness
            self.logger.info(f"Step 3/5: Verifying completeness (attempt {attempt}/{max_completeness_retries})...")
            bio_content = await self._run_llm_step_with_retry(
                llm,
                prompts.get("verification", {}).get("system", ""),
                f"Original:\n{answers_text}\n\nStructured:\n{structured_text}",
                f"Step 3 (verification, attempt {attempt})",
                loop
            )

            # Step 4: Completeness check (LLM validates all info is present)
            self.logger.info(f"Step 4/5: Checking document completeness (attempt {attempt}/{max_completeness_retries})...")
            completeness_prompt = prompts.get("completeness_check", {}).get("system", "")
            completeness_result = await loop.run_in_executor(
                None, llm.invoke, completeness_prompt,
                f"ANSWERS:\n{answers_text}\n\nDOCUMENT:\n{bio_content}"
            )
            completeness_raw = completeness_result.content if hasattr(completeness_result, 'content') else str(completeness_result)

            # Parse the JSON response
            try:
                json_str = completeness_raw.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()
                completeness_data = json_module.loads(json_str)
            except (json_module.JSONDecodeError, IndexError) as e:
                self.logger.warning(f"Could not parse completeness check JSON: {e}. Raw: {completeness_raw[:200]}")
                completeness_data = {"is_complete": False, "missing_topics": ["Completeness check could not be parsed"]}

            if completeness_data.get("is_complete", False):
                self.logger.info(f"Step 4/5 complete: Document is complete (attempt {attempt}).")
                break

            missing = completeness_data.get("missing_topics", [])
            self.logger.warning(f"Completeness check failed (attempt {attempt}/{max_completeness_retries}). Missing: {missing}")

            if attempt == max_completeness_retries:
                self.logger.error(f"Completeness check failed after {max_completeness_retries} attempts. Missing topics: {missing}")
                raise Exception(
                    f"Biography is incomplete after {max_completeness_retries} attempts. "
                    f"Missing information about: {', '.join(missing[:10])}. "
                    "Please try generating again."
                )

            # Feed missing info hint into next verification attempt
            structured_text = (
                f"{structured_text}\n\n"
                f"NOTE: The following information was missing and MUST be included: "
                f"{'; '.join(missing[:10])}"
            )
       

        # Save bio.md (only after all checks pass)
        bio_path = Path(self.plugin_folder) / "bio.md"
        bio_path.write_text(bio_content, encoding='utf-8')
        self.logger.info(f"Bio saved to {bio_path}")

        # Step 5: Extract and merge style
        self.logger.info("Step 5/5: Extracting style...")
        try:
            new_style = await self._run_llm_step_with_retry(
                llm,
                prompts.get("style_extraction", {}).get("system", ""),
                answers_text,
                "Step 5 (style_extraction)",
                loop
            )

            # Merge with existing style
            existing_style = bio.get("style", "")
            if new_style:
                merged_style = f"{existing_style}\n{new_style}" if existing_style else new_style

                # Update only the style field in onboarding bio, preserving name/health_state/etc.
                current_bio = self.settings_manager.get_nested(["plugins", "onboarding", "bio"], default={})
                current_bio["style"] = merged_style
                self.settings_manager.update_plugin_settings("onboarding", {
                    "bio": current_bio
                }, self.pm)
                self.logger.info("Style updated in onboarding settings")
        except Exception as e:
            self.logger.warning(f"Style extraction failed (non-critical): {e}")
            # Style extraction failure should not prevent the bio from being marked as generated

        return {
            "status": "complete",
            "bio_file": str(bio_path),
            "style_updated": True
        }

    def _generate_voice_sample(self):
        """Merge recorded voice answers into a single WAV with silence trimming"""
        from pydub import AudioSegment
        from pydub.silence import split_on_silence

        # Collect audio file paths from answers
        audio_paths = []
        recorder_plugin = next((p for p in self.pm.plugins if getattr(p, 'plugin_name', None) == "recorder"), None)
        if not recorder_plugin:
            self.logger.warning("Recorder plugin not available, cannot generate voice sample")
            return

        recorder_folder = recorder_plugin.plugin_folder

        for idx in sorted(self.answers.keys(), key=int):
            data = self.answers[idx]
            audio_ref = data.get("audio_file")
            if not audio_ref:
                continue
            # Try direct path first (audio_ref is relative to recorder plugin folder)
            audio_path = Path(recorder_folder) / audio_ref
            if audio_path.exists():
                audio_paths.append(audio_path)
                continue

            # If direct path doesn't exist, extract the record ID and resolve via recorder database
            # audio_ref format: "audio/biorecorder/{audio_id}.wav"
            try:
                audio_id = Path(audio_ref).stem
                rows = recorder_plugin.db_execute_sync(
                    "SELECT filename FROM records WHERE id = ?",
                    (int(audio_id),)
                )
                if rows and rows[0].get("filename"):
                    resolved_path = Path(recorder_folder) / rows[0]["filename"]
                    if resolved_path.exists():
                        audio_paths.append(resolved_path)
                    else:
                        self.logger.warning(f"Resolved audio file not found: {resolved_path}")
                else:
                    self.logger.warning(f"No recorder DB entry for audio_id={audio_id}")
            except (ValueError, Exception) as e:
                self.logger.warning(f"Could not resolve audio file {audio_ref}: {e}")

        if not audio_paths:
            self.logger.info("No voice recordings found, skipping voice sample generation")
            return

        self.logger.info(f"Generating voice sample from {len(audio_paths)} audio files...")

        try:
            # Load and concatenate all audio files
            combined = AudioSegment.empty()
            for audio_path in audio_paths:
                try:
                    segment = AudioSegment.from_file(str(audio_path))
                    combined += segment
                except Exception as e:
                    self.logger.warning(f"Could not load audio file {audio_path}: {e}")
                    continue

            if len(combined) == 0:
                self.logger.warning("All audio files were empty, skipping voice sample generation")
                return

            # Normalize: 44.1kHz, 16-bit, mono
            combined = combined.set_frame_rate(44100).set_sample_width(2).set_channels(1)

            # Split on silence and re-join with short gaps
            # silence_thresh: audio quieter than -40 dBFS is considered silence
            # min_silence_len: 500ms of continuous silence to trigger a split
            # keep_silence: keep 100ms of silence at edges for natural sound
            chunks = split_on_silence(
                combined,
                min_silence_len=500,
                silence_thresh=-40,
                keep_silence=100
            )

            if chunks:
                # Re-concatenate with 200ms gaps
                silence_gap = AudioSegment.silent(duration=200, frame_rate=44100)
                trimmed = chunks[0]
                for chunk in chunks[1:]:
                    trimmed += silence_gap + chunk
            else:
                # No silence detected, use original
                trimmed = combined

            # If longer than 2 minutes, cut at the next silence boundary after 2 min
            max_duration_ms = 2 * 60 * 1000  # 2 minutes
            if len(trimmed) > max_duration_ms:
                # Look for a silence gap after the 2-minute mark
                search_start = max_duration_ms
                search_end = min(len(trimmed), max_duration_ms + 10000)  # search up to 10s past 2 min
                best_cut = None

                # Scan for quiet sections (segments below -35 dBFS for at least 200ms)
                chunk_ms = 50
                for offset in range(search_start, search_end - 200, chunk_ms):
                    segment = trimmed[offset:offset + 200]
                    if segment.dBFS < -35:
                        best_cut = offset
                        break

                if best_cut:
                    trimmed = trimmed[:best_cut]
                else:
                    # No silence found, hard cut at 2 min
                    trimmed = trimmed[:max_duration_ms]

                self.logger.info(f"Voice sample trimmed to {len(trimmed)/1000:.1f}s")

            # Export
            output_path = Path(self.plugin_folder) / "voice_sample.wav"
            trimmed.export(str(output_path), format="wav")
            self.logger.info(f"Voice sample saved to {output_path} ({len(trimmed)/1000:.1f}s)")

        except Exception as e:
            self.logger.error(f"Error generating voice sample: {e}")

    def _get_voice_sample_info(self) -> Dict:
        """Get info about the generated voice sample"""
        sample_path = Path(self.plugin_folder) / "voice_sample.wav"
        if not sample_path.exists():
            return {"exists": False, "duration_seconds": 0}

        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(str(sample_path))
            return {
                "exists": True,
                "duration_seconds": len(audio) / 1000.0,
                "file_path": str(sample_path)
            }
        except Exception as e:
            self.logger.error(f"Error reading voice sample: {e}")
            return {"exists": False, "duration_seconds": 0}

    async def _get_voice_sample_file(self):
        """Serve the voice sample WAV file"""
        sample_path = Path(self.plugin_folder) / "voice_sample.wav"
        if not sample_path.exists():
            raise HTTPException(status_code=404, detail="Voice sample not found")
        return FileResponse(sample_path, media_type="audio/wav", filename="voice_sample.wav")

    async def _delete_voice_sample(self) -> Dict:
        """Delete the voice sample file"""
        sample_path = Path(self.plugin_folder) / "voice_sample.wav"
        try:
            if sample_path.exists():
                sample_path.unlink()
                self.logger.info("Voice sample deleted")
            return {"status": "deleted"}
        except Exception as e:
            self.logger.error(f"Error deleting voice sample: {e}")
            raise HTTPException(status_code=500, detail=str(e))
