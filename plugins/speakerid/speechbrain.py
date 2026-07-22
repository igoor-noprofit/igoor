import os

import pickle
import numpy as np
from pathlib import Path
import threading
import torch
import faiss
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# SpeechBrain 1.0+ uses new import path
from speechbrain.inference.speaker import SpeakerRecognition

class SpeakerIdentificationSystem:
    def __init__(self, voices_dir="./voices", embeddings_file="speaker_embeddings.pkl", model_name="speechbrain/spkrec-ecapa-voxceleb", plugin_dir=None):
        self.voices_dir = Path(voices_dir)
        self.embeddings_file = embeddings_file
        self.model_name = model_name
        self.plugin_dir = plugin_dir

        # Load the SpeechBrain model - savedir is optional in 1.0+, uses HF cache directly
        print("Loading speaker recognition model...")
        self.classifier = SpeakerRecognition.from_hparams(
            source=model_name,
            run_opts={"device": "cpu"}
        )
        
        # Initialize storage
        self.speaker_names = []
        self.embeddings = None
        self.index = None
        self.embedding_dim = None  # Will be set after first embedding

        # Guards speaker_names/embeddings/index so a rebuild() can't race an
        # in-flight identify_speaker() (which would read a half-rebuilt index).
        self._index_lock = threading.Lock()
        
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

    def rebuild(self):
        """Re-derive every speaker's embedding from ALL WAVs on disk, then rebuild the
        FAISS index and persist. Implements 'stack & improve': a folder may hold several
        samples and each speaker's embedding is the mean over all of them, so adding a
        WAV to an existing folder improves that speaker's embedding on the next rebuild.

        Unlike scan_and_enroll (which skips already-enrolled names), this starts from a
        clean slate so re-enrollment of an existing speaker actually takes effect. The
        whole body holds _index_lock so identify_speaker() never sees a half-built index.
        """
        with self._index_lock:
            self.speaker_names = []
            self.embeddings = None
            self.embedding_dim = None

            if self.voices_dir.exists():
                print(f"\nRebuilding embeddings from {self.voices_dir}...")
                for speaker_dir in [d for d in self.voices_dir.iterdir() if d.is_dir()]:
                    speaker_name = speaker_dir.name
                    wav_files = list(speaker_dir.glob("*.wav")) + list(speaker_dir.glob("*.WAV"))
                    if not wav_files:
                        continue

                    embeddings_list = []
                    for wav_file in wav_files:
                        try:
                            emb = self.extract_embedding(str(wav_file))
                            if emb is not None:
                                embeddings_list.append(emb)
                        except Exception as e:
                            print(f"  Warning: rebuild skipped {wav_file.name}: {e}")

                    if not embeddings_list:
                        continue

                    avg_embedding = np.mean(embeddings_list, axis=0)
                    if self.embedding_dim is None:
                        self.embedding_dim = len(avg_embedding)
                        self.embeddings = np.empty((0, self.embedding_dim), dtype=np.float32)

                    self.speaker_names.append(speaker_name)
                    self.embeddings = np.vstack([self.embeddings, avg_embedding.reshape(1, -1)])
                    print(f"  ✓ {speaker_name} - {len(embeddings_list)} sample(s)")

            if len(self.speaker_names) > 0:
                self.save_embeddings()
                self.build_index()
            else:
                self.index = None
                print("Rebuild complete: no enrolled speakers.")

    def rebuild_speaker(self, name):
        """Incremental enroll/delete: re-derive ONLY this speaker's embedding from their
        WAVs on disk, update their row in-place (append if new, drop if their folder is
        gone), and refresh the index.

        Used on save/delete so a Save doesn't re-process every other speaker — cost is
        O(this speaker's samples) instead of rebuild()'s O(all samples, all people).
        Holds _index_lock for the same reason rebuild() does.
        """
        with self._index_lock:
            new_emb = None
            speaker_dir = self.voices_dir / name
            wav_files = []
            if speaker_dir.exists():
                wav_files = list(speaker_dir.glob("*.wav")) + list(speaker_dir.glob("*.WAV"))

            if wav_files:
                embeddings_list = []
                for wav_file in wav_files:
                    try:
                        emb = self.extract_embedding(str(wav_file))
                        if emb is not None:
                            embeddings_list.append(emb)
                    except Exception as e:
                        print(f"  Warning: rebuild_speaker skipped {wav_file.name}: {e}")
                if embeddings_list:
                    new_emb = np.mean(embeddings_list, axis=0)
                    if self.embedding_dim is None:
                        self.embedding_dim = len(new_emb)
                        self.embeddings = np.empty((0, self.embedding_dim), dtype=np.float32)

            # Update the speaker's existing row, or append / drop it.
            if name in self.speaker_names:
                idx = self.speaker_names.index(name)
                if new_emb is not None:
                    self.embeddings[idx] = new_emb
                else:
                    # No valid samples left (e.g. folder removed on delete) → drop them.
                    self.speaker_names.pop(idx)
                    self.embeddings = np.delete(self.embeddings, idx, axis=0)
            elif new_emb is not None:
                self.speaker_names.append(name)
                self.embeddings = np.vstack([self.embeddings, new_emb.reshape(1, -1)])

            if len(self.speaker_names) > 0:
                self.save_embeddings()
                self.build_index()
            else:
                self.index = None
                print(f"rebuild_speaker('{name}'): no enrolled speakers left.")

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
        # Fast best-effort bail-out before the (expensive) embedding forward pass.
        if self.index is None or len(self.speaker_names) == 0:
            print("No speakers enrolled - returning empty results")
            return None, 0.0, []

        print(f"Identifying speaker from audio: {len(audio_data)} samples at {sample_rate} Hz")

        # Extract embedding (pure: only local state + the read-only self.classifier)
        test_embedding = self.extract_embedding_from_audio(audio_data, sample_rate)
        test_embedding_normalized = test_embedding / np.linalg.norm(test_embedding)

        # Search the index + read speaker_names under the lock, so a concurrent
        # rebuild() can't swap them mid-read (would IndexError on speaker_names[idx]).
        with self._index_lock:
            if self.index is None or len(self.speaker_names) == 0:
                print("No speakers enrolled - returning empty results")
                return None, 0.0, []
            similarities, indices = self.index.search(
                test_embedding_normalized.reshape(1, -1),
                min(top_k, len(self.speaker_names))
            )
            results = [(self.speaker_names[idx], float(sim))
                       for sim, idx in zip(similarities[0], indices[0])]
        
        # Best match
        best_match = results[0][0] if results[0][1] >= threshold else None
        best_score = results[0][1] if results else 0.0
        
        print(f"Speaker identification result: {best_match} (confidence: {best_score:.2f})")
        print(f"Top {len(results)} matches: {[(name, f'{score:.2f}') for name, score in results]}")

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
