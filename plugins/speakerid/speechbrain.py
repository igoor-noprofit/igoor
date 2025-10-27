import os
# MUST be set BEFORE importing speechbrain
os.environ['SPEECHBRAIN_CACHE_STRATEGY'] = 'COPY'

import pickle
import numpy as np
from pathlib import Path
import torch
import faiss
import warnings
import webrtcvad
import pyaudio
import collections
import time
from array import array

# Suppress warnings
warnings.filterwarnings('ignore')

# Patch SpeechBrain to use COPY strategy before importing
import speechbrain.utils.fetching as fetching
from speechbrain.utils.fetching import LocalStrategy

# Force COPY strategy
original_link = fetching.link_with_strategy

def patched_link(src, dst, strategy=None):
    # Always use COPY on Windows to avoid symlink issues
    return original_link(src, dst, LocalStrategy.COPY)

fetching.link_with_strategy = patched_link

# Now import the classifier
from speechbrain.inference.speaker import EncoderClassifier

class SpeakerIdentificationSystem:
    def __init__(self, voices_dir="./voices", embeddings_file="speaker_embeddings.pkl", model_name="speechbrain/spkrec-ecapa-voxceleb", plugin_dir=None):
        self.voices_dir = Path(voices_dir)
        self.embeddings_file = embeddings_file
        self.model_name = model_name
        
        if plugin_dir is not None:
                model_save_dir = os.path.join(plugin_dir, "pretrained_models", "spkrec-ecapa-voxceleb")
        else:
            plugin_dir = os.path.dirname(os.path.dirname(__file__))
            model_save_dir = os.path.join(plugin_dir, "pretrained_models", "spkrec-ecapa-voxceleb")
        
        # Load the SpeechBrain model
        print("Loading speaker recognition model...")
        self.classifier = EncoderClassifier.from_hparams(
            source=model_name,
            # Use passed plugin_dir or calculate from file if not provided            
            savedir=model_save_dir,
            run_opts={"device": "cpu"}
        )
        
        # Initialize storage
        self.speaker_names = []
        self.embeddings = None
        self.index = None
        self.embedding_dim = None  # Will be set after first embedding
        
        # Load existing embeddings or create new
        self.load_or_create_embeddings()
    
    def load_or_create_embeddings(self):
        """Load existing embeddings or scan voices folder to create new ones"""
        """TODO: add connection with the new database"""
        if os.path.exists(self.embeddings_file):
            print(f"Loading existing embeddings from {self.embeddings_file}...")
            self.load_embeddings()
            print(f"Loaded {len(self.speaker_names)} enrolled speakers")
        else:
            print("No existing embeddings found. Creating new enrollment...")
            self.speaker_names = []
            self.embeddings = None  # Will initialize with first embedding
        
        # Scan voices directory and enroll new speakers
        if self.voices_dir.exists():
            print(f"Scanning voices directory: {self.voices_dir}")
            self.scan_and_enroll()
        else:
            print(f"Warning: Voices directory '{self.voices_dir}' not found!")
            print("Please create it and add speaker subfolders with WAV files.")
        
        # Build FAISS index
        print("Building FAISS index...")
        self.build_index()
    
    def scan_and_enroll(self):
        """Scan voices directory and enroll any new speakers"""
        print(f"\nScanning {self.voices_dir} for speakers...")
        
        # Get all speaker directories
        speaker_dirs = [d for d in self.voices_dir.iterdir() if d.is_dir()]
        
        if not speaker_dirs:
            print("No speaker folders found in voices directory!")
            return
        
        for speaker_dir in speaker_dirs:
            speaker_name = speaker_dir.name
            
            # Check if already enrolled
            if speaker_name in self.speaker_names:
                print(f"  ✓ {speaker_name} - already enrolled, skipping")
                continue
            
            # Find WAV files
            wav_files = list(speaker_dir.glob("*.wav")) + list(speaker_dir.glob("*.WAV"))
            
            if not wav_files:
                print(f"  ✗ {speaker_name} - no WAV files found, skipping")
                continue
            
            print(f"  → {speaker_name} - enrolling with {len(wav_files)} sample(s)...")
            
            # Extract embeddings from all samples and average them
            embeddings_list = []
            for wav_file in wav_files:
                try:
                    print(f"    Processing {wav_file.name}...")
                    embedding = self.extract_embedding(str(wav_file))
                    if embedding is not None:
                        embeddings_list.append(embedding)
                        print(f"    ✓ {wav_file.name} - embedding extracted")
                    else:
                        print(f"    ✗ {wav_file.name} - failed to extract embedding")
                except Exception as e:
                    print(f"    Warning: Failed to process {wav_file.name}: {e}")
            
            if embeddings_list:
                # Average all embeddings for this speaker
                avg_embedding = np.mean(embeddings_list, axis=0)
                
                # Set embedding dimension from first enrollment
                if self.embedding_dim is None:
                    self.embedding_dim = len(avg_embedding)
                    self.embeddings = np.empty((0, self.embedding_dim), dtype=np.float32)
                    print(f"    Detected embedding dimension: {self.embedding_dim}")
                
                # Add to our database
                self.speaker_names.append(speaker_name)
                self.embeddings = np.vstack([self.embeddings, avg_embedding.reshape(1, -1)])
                print(f"  ✓ {speaker_name} - enrolled successfully!")
            else:
                print(f"  ✗ {speaker_name} - failed to enroll (no valid samples)")
        
        # Save updated embeddings
        if len(self.speaker_names) > 0:
            self.save_embeddings()
    
    def extract_embedding(self, audio_path):
        """Extract embedding from audio file"""
        import torchaudio
        
        # Load audio file
        waveform, sample_rate = torchaudio.load(str(audio_path))
        
        # Convert to mono if stereo
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Resample if needed (model expects 16kHz)
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(sample_rate, 16000)
            waveform = resampler(waveform)
        
        # Add batch dimension if needed
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        
        # Encode to get embedding - returns shape [batch, time, features]
        with torch.no_grad():
            embeddings = self.classifier.encode_batch(waveform)
            # Average over time dimension if needed
            if embeddings.dim() == 3:
                embeddings = embeddings.mean(dim=1)
            embedding = embeddings.squeeze()
        
        return embedding.cpu().numpy().astype(np.float32)
    
    def extract_embedding_from_audio(self, audio_data, sample_rate=16000):
        """Extract embedding from raw audio data (numpy array)"""
        # Convert to tensor
        waveform = torch.from_numpy(audio_data).float()
        
        # Ensure mono and add batch dimension
        if waveform.dim() == 1:
            waveform = waveform.unsqueeze(0)
        elif waveform.dim() == 2:
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)
        else:
            waveform = waveform.reshape(1, -1)
        
        # Encode to get embedding
        with torch.no_grad():
            embeddings = self.classifier.encode_batch(waveform)
            if embeddings.dim() == 3:
                embeddings = embeddings.mean(dim=1)
            embedding = embeddings.squeeze()
        
        return embedding.cpu().numpy().astype(np.float32)
    
    def build_index(self):
        """Build FAISS index for fast similarity search"""
        if self.embeddings is None or len(self.embeddings) == 0:
            print("\nNo speakers enrolled. Index not created.")
            self.index = None
            return
        
        print(f"\nBuilding FAISS index for {len(self.speaker_names)} speakers...")
        print(f"Embeddings shape: {self.embeddings.shape}")
        print(f"Embedding dimension: {self.embedding_dim}")
        
        # For small datasets, use simple L2 index
        # Normalize embeddings for cosine similarity
        embeddings_normalized = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        
        print(f"Normalized embeddings shape: {embeddings_normalized.shape}")
        
        self.index = faiss.IndexFlatIP(self.embedding_dim)  # Inner Product = cosine similarity with normalized vectors
        self.index.add(embeddings_normalized)
        print(f"FAISS index built successfully! Added {self.index.ntotal} embeddings to index")
    
    def identify_speaker(self, audio_data, sample_rate=16000, threshold=0.5, top_k=3):
        """
        Identify speaker from audio data
        
        Args:
            audio_data: numpy array of audio samples
            sample_rate: sample rate of audio
            threshold: Minimum similarity score (0-1) to consider a match
            top_k: Return top K matches
        
        Returns:
            tuple: (best_match_name, similarity_score, top_k_results)
        """
        if self.index is None or len(self.speaker_names) == 0:
            return None, 0.0, []
        
        # Extract embedding
        test_embedding = self.extract_embedding_from_audio(audio_data, sample_rate)
        test_embedding_normalized = test_embedding / np.linalg.norm(test_embedding)
        
        # Search in FAISS index
        similarities, indices = self.index.search(
            test_embedding_normalized.reshape(1, -1), 
            min(top_k, len(self.speaker_names))
        )
        
        # Prepare results
        results = []
        for sim, idx in zip(similarities[0], indices[0]):
            results.append((self.speaker_names[idx], float(sim)))
        
        # Best match
        best_match = results[0][0] if results[0][1] >= threshold else None
        best_score = results[0][1] if results else 0.0
        
        return best_match, best_score, results
    
    def save_embeddings(self):
        """Save embeddings and speaker names to disk"""
        data = {
            'speaker_names': self.speaker_names,
            'embeddings': self.embeddings,
            'embedding_dim': self.embedding_dim
        }
        with open(self.embeddings_file, 'wb') as f:
            pickle.dump(data, f)
        print(f"Embeddings saved to {self.embeddings_file}")
    
    def load_embeddings(self):
        """Load embeddings and speaker names from disk"""
        with open(self.embeddings_file, 'rb') as f:
            data = pickle.load(f)
        self.speaker_names = data['speaker_names']
        self.embeddings = data['embeddings']
        self.embedding_dim = data['embedding_dim']
    
    def list_speakers(self):
        """Print all enrolled speakers"""
        print(f"\nEnrolled speakers ({len(self.speaker_names)}):")
        for i, name in enumerate(self.speaker_names, 1):
            print(f"  {i}. {name}")


class RealtimeSpeakerRecognizer:
    """Real-time speaker recognition using microphone with VAD"""
    
    def __init__(self, speaker_system, 
                 sample_rate=16000,
                 frame_duration_ms=30,
                 vad_aggressiveness=3,
                 buffer_duration_sec=2.0,
                 min_speech_duration_sec=1.0):
        """
        Initialize real-time recognizer
        
        Args:
            speaker_system: SpeakerIdentificationSystem instance
            sample_rate: Audio sample rate (16000 Hz for WebRTC VAD)
            frame_duration_ms: VAD frame duration (10, 20, or 30 ms)
            vad_aggressiveness: VAD aggressiveness (0-3, higher = more aggressive)
            buffer_duration_sec: How long to buffer speech before recognition
            min_speech_duration_sec: Minimum speech duration to trigger recognition
        """
        self.speaker_system = speaker_system
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.vad_aggressiveness = vad_aggressiveness
        self.buffer_duration_sec = buffer_duration_sec
        self.min_speech_duration_sec = min_speech_duration_sec
        
        # Initialize VAD
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        
        # Audio configuration
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.chunk_size = self.frame_size
        
        # Buffers
        self.ring_buffer = collections.deque(maxlen=int(buffer_duration_sec * sample_rate / self.frame_size))
        self.triggered = False
        self.voiced_frames = []
        
        # PyAudio setup
        self.audio = pyaudio.PyAudio()
        self.stream = None
        
        # Stats
        self.last_recognition_time = 0
        self.recognition_cooldown = 2.0  # seconds between recognitions
    
    def start(self):
        """Start listening from microphone"""
        print("\n" + "="*60)
        print("REAL-TIME SPEAKER RECOGNITION")
        print("="*60)
        print(f"Sample rate: {self.sample_rate} Hz")
        print(f"VAD aggressiveness: {self.vad_aggressiveness}")
        print(f"Minimum speech duration: {self.min_speech_duration_sec}s")
        print(f"Recognition threshold: 0.5")
        print("\nListening... Speak into the microphone!")
        print("Press Ctrl+C to stop\n")
        
        try:
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            while True:
                # Read audio chunk
                frame = self.stream.read(self.chunk_size, exception_on_overflow=False)
                
                # Check if frame contains speech
                is_speech = self.vad.is_speech(frame, self.sample_rate)
                
                if not self.triggered:
                    # Not currently in speech
                    self.ring_buffer.append((frame, is_speech))
                    num_voiced = len([f for f, speech in self.ring_buffer if speech])
                    
                    # Trigger if enough voiced frames
                    if num_voiced > 0.8 * self.ring_buffer.maxlen:
                        self.triggered = True
                        self.voiced_frames = [f for f, s in self.ring_buffer]
                        self.ring_buffer.clear()
                        print("🎤 Speech detected, recording...")
                else:
                    # Currently in speech
                    self.voiced_frames.append(frame)
                    self.ring_buffer.append((frame, is_speech))
                    num_unvoiced = len([f for f, speech in self.ring_buffer if not speech])
                    
                    # End of speech?
                    if num_unvoiced > 0.8 * self.ring_buffer.maxlen:
                        self.triggered = False
                        
                        # Check if we have enough speech
                        speech_duration = len(self.voiced_frames) * self.frame_duration_ms / 1000.0
                        
                        if speech_duration >= self.min_speech_duration_sec:
                            # Check cooldown
                            current_time = time.time()
                            if current_time - self.last_recognition_time >= self.recognition_cooldown:
                                self.process_speech(self.voiced_frames)
                                self.last_recognition_time = current_time
                            else:
                                print(f"⏳ Too soon, waiting {self.recognition_cooldown}s between recognitions")
                        else:
                            print(f"⚠️  Speech too short ({speech_duration:.1f}s), need at least {self.min_speech_duration_sec}s")
                        
                        self.voiced_frames = []
                        self.ring_buffer.clear()
                        print("🎧 Listening...")
        
        except KeyboardInterrupt:
            print("\n\nStopping...")
        finally:
            self.stop()
    
    def process_speech(self, frames):
        """Process detected speech and identify speaker"""
        print("🔍 Processing speech...")
        
        # Convert frames to numpy array
        audio_data = b''.join(frames)
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        try:
            # Identify speaker
            match, score, top_3 = self.speaker_system.identify_speaker(
                audio_array, 
                sample_rate=self.sample_rate,
                threshold=0.5,
                top_k=3
            )
            
            if match:
                print(f"✅ Speaker identified: {match.upper()} (confidence: {score:.2f})")
            else:
                print(f"❌ Unknown speaker (best score: {score:.2f})")
            
            # Show top 3
            print("   Top matches:")
            for name, s in top_3:
                bar = "█" * int(s * 20)
                print(f"     {name:15s} {s:.2f} {bar}")
            print()
            
        except Exception as e:
            print(f"❌ Error during recognition: {e}\n")
    
    def stop(self):
        """Stop listening and cleanup"""
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.audio.terminate()
        print("Microphone closed.")