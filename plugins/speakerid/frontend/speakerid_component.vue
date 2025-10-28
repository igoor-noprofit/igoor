<template>
    <div class="speakerid-topbar">
        <span class="ready-indicator" :class="getReadyStatusClass()" :title="getReadyStatusText()">
            {{ getReadyStatusIcon() }}
        </span>
        <span class="speaker-icon">🎤</span>
        <span class="speaker-name" :class="currentSpeaker.name ? 'speaker-known' : 'speaker-unknown'">{{ currentSpeaker.name || 'Unknown' }}</span>
        <span class="confidence" :class="getConfidenceClass()">{{ Math.round(currentSpeaker.confidence * 100) }}%</span>
        <span class="status-dot" :class="getStatusClass()"></span>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
export default {
    name: 'SpeakerID',
    mixins: [BasePluginComponent],
    props: {
        msg: Object
    },
    data() {
        return {
            currentSpeaker: {
                name: 'unknown',
                confidence: 0.0,
                status: 'unknown'
            },
            isListening: true,
            voiceLevels: new Array(20).fill(0),
            pluginStatus: 'loading',
            speakerCount: 0,
            statusMessage: 'Initializing...'
        };
    },
    async mounted() {
        // Initialize voice level visualization
        this.startVoiceAnimation();
        
        // Fetch initial status from backend
        await this.fetchStatus();
        
        // If not ready, poll every 2 seconds until ready
        if (this.pluginStatus !== 'ready') {
            const pollInterval = setInterval(async () => {
                await this.fetchStatus();
                
                // Stop polling once ready
                if (this.pluginStatus === 'ready' || this.pluginStatus === 'error') {
                    clearInterval(pollInterval);
                }
            }, 2000);
        }
    },
    
    methods: {
        async fetchStatus() {
            try {
                const response = await fetch('/api/plugins/speakerid/status', {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin'
                });
                
                if (response.ok) {
                    const statusData = await response.json();
                    this.pluginStatus = statusData.status;
                    this.statusMessage = statusData.message || '';
                    
                    if (statusData.speaker_count !== undefined) {
                        this.speakerCount = statusData.speaker_count;
                    }
                } else {
                    console.warn('Failed to fetch speakerid status:', response.status);
                }
            } catch (error) {
                console.warn('Error fetching speakerid status:', error);
            }
        },
    
    getStatusClass() {
            if (this.currentSpeaker.status === 'confirmed') {
                return 'status-confirmed';
            } else if (this.currentSpeaker.status === 'partial') {
                return 'status-partial';
            } else {
                return 'status-unknown';
            }
        },
        
        getStatusIcon() {
            if (this.currentSpeaker.status === 'confirmed') {
                return '✓';
            } else if (this.currentSpeaker.status === 'partial') {
                return '≈';
            } else {
                return '❌';
            }
        },
        
        getStatusText() {
            if (this.currentSpeaker.status === 'confirmed') {
                return 'Speaker Confirmed';
            } else if (this.currentSpeaker.status === 'partial') {
                return 'Speaker Partially Identified';
            } else {
                return 'Listening...';
            }
        },
        
        getConfidenceClass() {
            if (this.currentSpeaker.confidence >= 0.7) {
                return 'confidence-score high';
            } else if (this.currentSpeaker.confidence >= 0.5) {
                return 'confidence-score medium';
            } else {
                return 'confidence-score low';
            }
        },
        
        getReadyStatusClass() {
            if (this.pluginStatus === 'ready') {
                return 'ready-yes';
            } else if (this.pluginStatus === 'loading') {
                return 'ready-loading';
            } else if (this.pluginStatus === 'error') {
                return 'ready-error';
            } else {
                return 'ready-no';
            }
        },
        
        getReadyStatusIcon() {
            if (this.pluginStatus === 'ready') {
                return '✓';
            } else if (this.pluginStatus === 'loading') {
                return '⏳';
            } else if (this.pluginStatus === 'error') {
                return '⚠';
            } else {
                return '✗';
            }
        },
        
        getReadyStatusText() {
            if (this.pluginStatus === 'ready') {
                return `SpeakerID Ready (${this.speakerCount} speakers enrolled)`;
            } else if (this.pluginStatus === 'loading') {
                return 'SpeakerID: Loading...';
            } else if (this.pluginStatus === 'error') {
                return 'SpeakerID: Error initializing';
            } else {
                return 'SpeakerID: Not ready';
            }
        },
        
        getVoiceBarHeight(level) {
            return `${Math.max(2, level * 25)}%`;
        },
        
        startVoiceAnimation() {
            setInterval(() => {
                // Animate voice levels
                for (let i = 0; i < this.voiceLevels.length; i++) {
                    // Random walk for natural effect
                    const walk = Math.random() * 3;
                    const currentLevel = this.voiceLevels[i];
                    const newLevel = Math.max(0, currentLevel - walk + (Math.random() - 0.5));
                    
                    if (newLevel !== currentLevel) {
                        this.voiceLevels[i] = newLevel;
                    } else {
                        // Decay when not processing
                        this.voiceLevels[i] = currentLevel * 0.95;
                    }
                }
            }, 100);
        }
    },
    
    watch: {
        '$plugin.msg'(newVal) {
            if (newVal) {
                if (newVal.type === 'speaker_identification') {
                    // Update current speaker information
                    this.currentSpeaker = {
                        name: newVal.speaker?.name || 'unknown',
                        confidence: newVal.speaker?.confidence || 0.0,
                        status: newVal.speaker?.status || 'unknown',
                        timestamp: newVal.speaker?.timestamp || Date.now()
                    };
                    
                    // Update voice levels when speech detected
                    if (newVal.speaker && newVal.speaker.confidence > 0) {
                        // Simulate voice activity during identification
                        for (let i = 0; i < 10; i++) {
                            const level = Math.random() * 0.8 + Math.random() * 0.2;
                            this.voiceLevels[i] = level;
                        }
                    }
                    
                    // Reset voice levels after a moment
                    setTimeout(() => {
                        for (let i = 0; i < this.voiceLevels.length; i++) {
                            this.voiceLevels[i] = this.voiceLevels[i] * 0.8;
                        }
                    }, 500);
                } else if (newVal.type === 'speakerid_status') {
                    // Handle plugin status updates
                    this.pluginStatus = newVal.status;
                    this.statusMessage = newVal.message || '';
                    
                    if (newVal.speaker_count !== undefined) {
                        this.speakerCount = newVal.speaker_count;
                    }
                }
            }
        }
    }
};
</script>
// CSS styling
<style scoped>
.speakerid-topbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    font-family: "FontLight", sans-serif;
    font-size: 14px;
    color: var(--color-text);
    background: var(--color-bgheader);
    border-radius: 8px;
    white-space: nowrap;
}

.ready-indicator {
    font-weight: bold;
    font-size: 16px;
    margin-right: 4px;
    padding: 2px 6px;
    border-radius: 12px;
    transition: all 0.3s ease;
}

.ready-yes {
    color: var(--basecolor-accent-700);
    background: var(--basecolor-accent-100);
}

.ready-loading {
    color: var(--basecolor-secondary-500);
    background: var(--basecolor-secondary-100);
}

.ready-error {
    color: var(--basecolor-warning-500);
    background: var(--basecolor-warning-100);
}

.ready-no {
    color: var(--basecolor-gray-400);
    background: var(--basecolor-gray-100);
}

.speaker-icon {
    font-size: 16px;
    margin-right: 4px;
}

.speaker-name {
    flex: 1;
    font-weight: 600;
    color: var(--color-text);
}

.speaker-known {
    color: var(--basecolor-accent-100);
    font-weight: 700;
}

.speaker-unknown {
    color: var(--basecolor-gray-100);
    font-style: italic;
}

.confidence {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    min-width: 45px;
    text-align: center;
}

.confidence.high {
    background: var(--basecolor-accent-100);
    color: var(--basecolor-accent-700);
}

.confidence.medium {
    background: var(--basecolor-secondary-100);
    color: var(--basecolor-secondary-500);
}

.confidence.low {
    background: var(--basecolor-warning-100);
    color: var(--basecolor-warning-500);
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--basecolor-gray-100);
}

.status-confirmed {
    background: var(--basecolor-accent-100);
}

.status-partial {
    background: var(--basecolor-secondary-100);
}

.status-unknown {
    background: var(--basecolor-warning-100);
}

/* Remove all old styles that are no longer needed */

.speakerid-header h3 {
    margin: 0 0 20px 0;
    color: #333;
    font-size: 24px;
    display: flex;
    align-items: center;
}

.speakerid-status {
    display: flex;
    justify-content: center;
    margin-bottom: 20px;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 20px;
    border-radius: 25px;
    background: #f8f9fa;
    border: 2px solid #dee2e6;
    transition: all 0.3s ease;
}

.status-confirmed {
    background: #d4edda;
    border-color: #c3e6cb;
}

.status-partial {
    background: #fff3cd;
    border-color: #ffc107;
}

.status-unknown {
    background: #f8d7da;
    border-color: #f5c6cb;
}

.status-icon {
    font-size: 24px;
    font-weight: bold;
}

.status-text {
    font-size: 14px;
    font-weight: 500;
}

.speakerid-main {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 20px;
}

.speaker-info {
    display: flex;
    align-items: center;
    gap: 15px;
    padding: 20px;
    border-radius: 15px;
    background: #f8f9fa;
    border: 1px solid #e9ecef;
    transition: all 0.3s ease;
}

.speaker-info:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.speaker-avatar {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: #6c757d;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 24px;
    font-weight: bold;
}

.speaker-avatar {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: #6c757d;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 24px;
    font-weight: bold;
}

.speaker-details {
    flex: 1;
}

.speaker-name {
    font-size: 18px;
    font-weight: 600;
    color: #333;
    margin-bottom: 5px;
}

.confidence-score {
    padding: 8px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    text-align: center;
}

.confidence-score.high {
    background: #d4edda;
    color: #155724;
}

.confidence-score.medium {
    background: #fff3cd;
    color: #856404;
}

.confidence-score.low {
    background: #f8d7da;
    color: #721c24;
}

.confidence-score.unknown {
    background: #e9ecef;
    color: #6c757d;
}

.speaker-info.unknown {
    opacity: 0.6;
}

.voice-meter {
    background: #343a40;
    border-radius: 15px;
    padding: 20px;
}

.voice-level-bars {
    display: flex;
    gap: 3px;
    align-items: end;
    height: 100px;
}

.voice-bar {
    width: 8px;
    background: #4caf50;
    border-radius: 4px;
    transition: height 0.2s ease;
}

.voice-level-text {
    color: white;
    text-align: center;
    margin-top: 10px;
    font-size: 12px;
}
</style>