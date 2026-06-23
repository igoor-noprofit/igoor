<template>
    <div class="meteo-plugin-settings form-grid">
        <!-- Attribution (CC BY 4.0) -->
        <div class="form-label"></div>
        <div class="form-input">
            <a href="https://open-meteo.com/" target="_blank" class="signup-link">
                {{ t('Weather data by Open-Meteo') }}
            </a>
        </div>
        <div class="form-note"></div>

        <!-- Home Address -->
        <div class="form-label">{{ t('Home address') }}</div>
        <div class="form-input" style="display: flex; align-items: center; gap: 8px;">
            <input
                type="text"
                v-model="formData.home_address"
                :class="{'input-error': addressError}"
                :placeholder="t('ex. 1600 Amphitheatre Parkway, Mountain View, CA')"
                :disabled="isGeocoding"
            />
            <span v-if="isGeocoding" class="geocoding-indicator">{{ t('Geocoding...') }}</span>
        </div>
        <div class="form-note" :style="{color: addressError ? '#ff6666' : undefined}">
            {{ addressError ? (addressErrorMessage || t('Geocoding failed')) : '' }}
        </div>

        <!-- Geocoded Location (shown only when geocoding succeeds) -->
        <div class="form-label" v-if="geocodedLat !== null && geocodedLon !== null && !addressError">
            {{ t('Geocoded location') }}
        </div>
        <div class="form-input" v-if="geocodedLat !== null && geocodedLon !== null && !addressError">
            <input
                type="text"
                :value="`${geocodedLat.toFixed(6)}, ${geocodedLon.toFixed(6)}`"
                readonly
                class="readonly-input"
            />
        </div>
        <div class="form-note" v-if="geocodedPlaceName && !addressError">
            {{ geocodedPlaceName }}
        </div>

        <!-- Manual Latitude/Longitude fields (shown when geocoding fails or hasn't happened) -->
        <div class="form-label" v-if="shouldShowManualCoords">
            {{ t('Latitude') }}
        </div>
        <div class="form-input" v-if="shouldShowManualCoords">
            <input
                type="text"
                v-model="formData.lat_home"
                :placeholder="t('ex. 13.12292393')"
            />
        </div>
        <div class="form-note"></div>

        <div class="form-label" v-if="shouldShowManualCoords">
            {{ t('Longitude') }}
        </div>
        <div class="form-input" v-if="shouldShowManualCoords">
            <input
                type="text"
                v-model="formData.lng_home"
                :placeholder="t('ex. 1.848349')"
            />
        </div>
        <div class="form-note"></div>

        <!-- Save Button (spans all columns) -->
        <div class="form-label"></div>
        <div class="form-input">
            <SaveSettingsButton
                :hasChanges="hasUnsavedChanges"
                :loading="isSaving"
                :t="t"
                :lang="lang"
                @save="checkBeforeUpdating"
                @cancel="resetSettings"
            />
        </div>
        <div class="form-note"></div>
    </div>
</template>

<script>
import BasePluginComponent from '/js/BasePluginComponent.js';
import SaveSettingsButton from '/js/SaveSettingsButton.vue';

export default {
    name: "meteoSettings",
    props: {
        initialSettings: Object
    },
    mixins: [BasePluginComponent],
    components: {
        SaveSettingsButton
    },
    data() {
        return {
            formData: {
                lat_home: '',
                lng_home: '',
                always_home: false,
                home_address: ''
            },
            isSaving: false,
            // Geocoding properties
            geocodedLat: null,
            geocodedLon: null,
            geocodedPlaceName: null,
            addressError: false,
            addressErrorMessage: '',
            isGeocoding: false,
            geocodingDebounce: null
        };
    },
    computed: {
        hasUnsavedChanges() {
            if (!this.originalSettings || !this.formData) return false;
            return JSON.stringify(this.formData) !== JSON.stringify(this.originalSettings);
        },
        shouldShowManualCoords() {
            // Show manual input when:
            // 1. Geocoding hasn't happened yet (null values), OR
            // 2. Geocoding failed with "Address not found" error
            if (this.geocodedLat === null || this.geocodedLon === null) {
                return true;
            }
            return this.addressError && this.addressErrorMessage?.includes('Address not found');
        }
    },
    watch: {
        initialSettings: {
            handler(newVal) {
                console.log('initialSettings watcher triggered, newVal:', newVal);
                if (newVal) {
                    // First set originalSettings (to track what we started with)
                    // Then update formData with actual values (not defaults)
                    this.$nextTick(() => {
                        this.setOriginalSettings(newVal);
                        this.formData = { ...newVal };
                        console.log('formData after initialization:', this.formData);
                    });
                }
            },
            immediate: true,
            deep: true
        },
        'formData.home_address'(newValue) {
            // Debounce address geocoding
            if (this.geocodingDebounce) {
                clearTimeout(this.geocodingDebounce);
            }
            if (newValue && newValue.trim()) {
                this.geocodingDebounce = setTimeout(() => {
                    this.geocodeAddress();
                }, 800);
            } else {
                this.addressError = false;
                this.addressErrorMessage = '';
                this.geocodedLat = null;
                this.geocodedLon = null;
                this.geocodedPlaceName = null;
            }
        },
        originalSettings: {
            handler(newVal) {
                console.log('originalSettings watcher triggered, newVal:', newVal);
                console.log('  settingsLoaded:', this.settingsLoaded);
                console.log('  Current formData:', this.formData);
                if (newVal) {
                    // Mark that settings have been loaded from backend
                    this.settingsLoaded = true;

                    // Check if formData is a simple object (not a proxy yet)
                    // If formData is still empty defaults, merge with backend settings
                    const needsMerge = !this.formData.lat_home &&
                                      !this.formData.lng_home && !this.formData.home_address;

                    console.log('  needsMerge:', needsMerge);

                    if (needsMerge) {
                        // Merge backend settings with defaults
                        this.formData = {
                            lat_home: newVal.lat_home || '',
                            lng_home: newVal.lng_home || '',
                            always_home: newVal.always_home !== undefined ? newVal.always_home : false,
                            home_address: newVal.home_address || ''
                        };
                        console.log('formData after merge:', this.formData);
                    } else {
                        // Settings already loaded via BasePluginComponent,
                        // just ensure we have the values
                        if (newVal.lat_home) this.formData.lat_home = newVal.lat_home;
                        if (newVal.lng_home) this.formData.lng_home = newVal.lng_home;
                        if (newVal.home_address) this.formData.home_address = newVal.home_address;
                        console.log('formData after direct update:', this.formData);
                    }
                }
            },
            deep: true
        },
        hasUnsavedChanges(newVal) {
            console.log('hasUnsavedChanges changed to:', newVal);
        }
    },
    methods: {
        async geocodeAddress() {
            if (!this.formData.home_address || !this.formData.home_address.trim()) {
                this.addressError = false;
                this.addressErrorMessage = '';
                this.geocodedLat = null;
                this.geocodedLon = null;
                this.geocodedPlaceName = null;
                return;
            }

            this.isGeocoding = true;
            this.addressError = false;
            this.addressErrorMessage = '';

            try {
                const response = await fetch(
                    `/api/plugins/meteo/geocode_address?address=${encodeURIComponent(this.formData.home_address)}`
                );
                const data = await response.json();

                if (response.ok) {
                    // Success: set coordinates in formData
                    this.formData.lat_home = String(data.lat);
                    this.formData.lng_home = String(data.lon);
                    this.geocodedLat = data.lat;
                    this.geocodedLon = data.lon;
                    this.geocodedPlaceName = data.name + (data.country ? `, ${data.country}` : '');
                    this.addressError = false;
                    this.addressErrorMessage = '';
                } else {
                    this.addressError = true;
                    this.addressErrorMessage = data.detail || this.t('Geocoding failed');
                    // Only clear geocoded display values, keep existing lat/lng for manual entry
                    this.geocodedLat = null;
                    this.geocodedLon = null;
                    this.geocodedPlaceName = null;
                }
            } catch (error) {
                console.error('Address geocoding error:', error);
                this.addressError = true;
                this.addressErrorMessage = this.t('Geocoding failed');
                this.geocodedLat = null;
                this.geocodedLon = null;
                this.geocodedPlaceName = null;
            } finally {
                this.isGeocoding = false;
            }
        },

        checkBeforeUpdating() {
            console.log('checkBeforeUpdating called');
            console.log('  formData:', this.formData);

            // No API key required anymore (Open-Meteo is key-free). Just save.
            this.isSaving = true;
            this.saveSettings().finally(() => {
                this.isSaving = false;
            });
        }
    },
    created() {
        console.log('meteoSettings created hook called');
        // Don't initialize formData here - wait for settings from backend
        // formData will be set in originalSettings watcher with defaults merged
    },
    beforeDestroy() {
        if (this.geocodingDebounce) {
            clearTimeout(this.geocodingDebounce);
        }
    }
};
</script>

<style scoped>
.meteo-plugin-settings.form-grid {
    display: grid;
    grid-template-columns: 200px 1fr 2fr;
    gap: 12px 18px;
    align-items: start;
    background: none;
    padding: 18px 0;
}

.form-label {
    font-weight: 500;
    padding-top: 6px;
    color: #e0e0e0;
    text-align: right;
}

.form-input {
    display: flex;
    align-items: center;
    gap: 8px;
}

.form-note {
    font-size: 0.97em;
    color: #aaa;
    line-height: 1.4;
    padding-top: 2px;
    text-align: left;
}

select, input[type="text"], input[type="password"], input[type="url"] {
    background: #222;
    color: #fff;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 1em;
    width: 100%;
}

.readonly-input {
    background: #333;
    color: #ccc;
    cursor: not-allowed;
}

.geocoding-indicator {
    color: #3ca23c;
    font-size: 0.9em;
    font-style: italic;
}

.signup-link {
    color: #3ca23c;
    text-decoration: none;
    font-weight: 500;
}

.signup-link:hover {
    text-decoration: underline;
}

.input-error {
    border-color: #ff6666;
    background: #2a1818;
}

.input-success {
    border-color: #3ca23c;
}

.valid-icon {
    color: #3ca23c;
    font-size: 1.2em;
    font-weight: bold;
    margin-left: 8px;
}

button {
    background: #3ca23c;
    color: #fff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s;
}

button:hover {
    background: #338a33;
}

button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}
</style>