/**
 * Fixate Audio Player — Alpine.js component for noise + ambient soundscapes.
 *
 * Drop this into any page with:
 *   <div x-data="audioPlayer()" x-init="init()"> ... </div>
 *
 * Requires:
 *   - NoisePlayer (from noise.js) for generated noise
 *   - FONT_REGISTRY/theme system (already in base.html)
 *   - /api/reader/tracks/ endpoint
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('audioPlayer', () => ({
        // ── State ──
        tracks: { noise: [], ambient: [] },
        activeTrack: null,      // currently playing track object, or null
        isPlaying: false,
        volume: 0.4,
        showPanel: false,       // toggle the audio panel open/closed
        noisePlayer: null,      // NoisePlayer instance (lazy init)
        ambientAudio: null,     // HTML5 Audio element for ambient tracks (lazy init)
        calibrating: false,       // true during calibration playback
        showCustomize: false,     // toggle customization panel
        customLfoSpeed: 0.18,
        customLfoDepth: 0.03,
        customBrightness: 0.0,
        presets: [],              // [{name, settings}]

        // Bilateral stimulation
        bilateralOn: false,
        bilateralPreset: 'alpha',
        _bilateral: null,         // BilateralStimulation instance

        // ── Init ──
        async init() {
            // Restore saved volume
            const saved = localStorage.getItem('fixate-noise-volume');
            if (saved) this.volume = parseFloat(saved);

            // Fetch tracks
            try {
                const resp = await fetch('/api/reader/tracks/', {
                    headers: { 'X-CSRFToken': this._csrf() }
                });
                const data = await resp.json();
                this.tracks = data;

                // Restore last track
                const lastSlug = localStorage.getItem('fixate-noise-track');
                if (lastSlug) {
                    const track = data.all.find(t => t.slug === lastSlug);
                    if (track) this.activeTrack = track;
                }
            } catch (e) {
                console.warn('Failed to load audio tracks:', e);
            }

            // Restore bilateral settings
            const bs = JSON.parse(localStorage.getItem('fixate-bilateral') || '{}');
            if (bs.on) this.bilateralOn = bs.on;
            if (bs.preset) this.bilateralPreset = bs.preset;
            if (this.bilateralOn) this._startBilateral();
        },

        // ── Actions ──

        /** Toggle audio panel visibility. */
        togglePanel() {
            this.showPanel = !this.showPanel;
        },

        /** Play a track.
         *  @param {object} track - from API (has category, noise_type, audio_url, etc.)
         */
        play(track) {
            // Stop current
            this.stop();

            this.activeTrack = track;
            localStorage.setItem('fixate-noise-track', track.slug);

            if (track.category === 'noise') {
                this._playNoise(track.noise_type);
            } else if (track.audio_url) {
                this._playAmbient(track.audio_url);
            } else {
                console.warn('Ambient track has no audio_url:', track.slug);
                this.activeTrack = null;
                return;
            }

            this.isPlaying = true;

            // Load saved custom settings for this noise type
            this.$nextTick(() => this.loadCustomSettings());
        },

        /** Toggle play/pause for current track. */
        toggle() {
            if (this.isPlaying) {
                this.pause();
            } else if (this.activeTrack) {
                this.resume();
            }
        },

        /** Pause playback. */
        pause() {
            if (this.noisePlayer && this.activeTrack?.category === 'noise') {
                this.noisePlayer.pause();
            }
            if (this.ambientAudio) {
                this.ambientAudio.pause();
            }
            this.isPlaying = false;
        },

        /** Resume playback. */
        resume() {
            if (this.noisePlayer && this.activeTrack?.category === 'noise') {
                this.noisePlayer.resume();
                this.isPlaying = true;
            } else if (this.ambientAudio) {
                this.ambientAudio.play().then(() => {
                    this.isPlaying = true;
                }).catch(() => {
                    // User hasn't interacted yet — ok
                });
            } else if (this.activeTrack) {
                // Re-initialize
                this.play(this.activeTrack);
            }
        },

        /** Stop and reset. */
        stop() {
            if (this.noisePlayer) {
                this.noisePlayer.stop();
                this.noisePlayer = null;
            }
            if (this.ambientAudio) {
                this.ambientAudio.pause();
                this.ambientAudio.currentTime = 0;
                this.ambientAudio = null;
            }
            this.isPlaying = false;
            this.activeTrack = null;
            localStorage.removeItem('fixate-noise-track');
        },

        /** Calibrate: play 5 seconds at current volume for user to adjust. */
        calibrate() {
            if (!this.activeTrack) return;
            this.calibrating = true;

            // Play briefly
            if (this.activeTrack.category === 'noise') {
                if (!this.noisePlayer) {
                    this.noisePlayer = new NoisePlayer();
                }
                this.noisePlayer.play(this.activeTrack.noise_type, 100);
                this.noisePlayer.setVolume(this.volume, 50);
            } else if (this.activeTrack.audio_url && this.ambientAudio) {
                this.ambientAudio.play();
            }

            setTimeout(() => {
                this.calibrating = false;
                if (this.noisePlayer) this.noisePlayer.setVolume(this.volume, 200);
            }, 5000);
        },

        /** Volume change handler (from slider).
         *  @param {Event} e
         */
        onVolumeChange(e) {
            this.volume = parseFloat(e.target.value);
            localStorage.setItem('fixate-noise-volume', this.volume);

            if (this.noisePlayer) {
                this.noisePlayer.setVolume(this.volume, 50);
            }
            if (this.ambientAudio) {
                this.ambientAudio.volume = this.volume;
            }
        },

        /** Check if a track has an audio source available. */
        canPlay(track) {
            return track.category === 'noise' || !!track.audio_url;
        },

        /** Get track label for aria/display. */
        trackLabel(track) {
            return `${track.icon} ${track.name}${!this.canPlay(track) ? ' (coming soon)' : ''}`;
        },

        // ── Customization ──

        /** Load saved custom settings for the current noise type. */
        loadCustomSettings() {
            if (!this.activeTrack || this.activeTrack.category !== 'noise') return;
            const key = `fixate-noise-custom-${this.activeTrack.noise_type}`;
            const saved = localStorage.getItem(key);
            if (saved) {
                try {
                    const s = JSON.parse(saved);
                    this.customLfoSpeed = s.lfoSpeed || 0.18;
                    this.customLfoDepth = s.lfoDepth || 0.03;
                    this.customBrightness = s.brightness || 0.0;
                    if (this.noisePlayer) {
                        this.noisePlayer.applySettings(s);
                    }
                } catch(e) {}
            }
            this._loadPresets();
        },

        /** LFO speed change. */
        onLfoSpeedChange(e) {
            this.customLfoSpeed = parseFloat(e.target.value);
            if (this.noisePlayer) {
                this.noisePlayer.setLFO(this.customLfoSpeed, this.customLfoDepth);
            }
            this._saveCustomSettings();
        },

        /** LFO depth change. */
        onLfoDepthChange(e) {
            this.customLfoDepth = parseFloat(e.target.value);
            if (this.noisePlayer) {
                this.noisePlayer.setLFO(this.customLfoSpeed, this.customLfoDepth);
            }
            this._saveCustomSettings();
        },

        /** Brightness change. */
        onBrightnessChange(e) {
            this.customBrightness = parseFloat(e.target.value);
            if (this.noisePlayer) {
                this.noisePlayer.setBrightness(this.customBrightness);
            }
            this._saveCustomSettings();
        },

        /** Reset customization to defaults. */
        resetCustom() {
            this.customLfoSpeed = 0.18;
            this.customLfoDepth = 0.03;
            this.customBrightness = 0.0;
            if (this.noisePlayer) {
                this.noisePlayer.setLFO(0.18, 0.03);
                this.noisePlayer.setBrightness(0.0);
            }
            this._saveCustomSettings();
        },

        // ── Presets ──

        /** Save current settings as a named preset. */
        savePreset() {
            const name = prompt('Name this preset:');
            if (!name || !name.trim()) return;
            this._loadPresets();
            // Remove existing preset with same name
            this.presets = this.presets.filter(p => p.name !== name.trim());
            this.presets.push({
                name: name.trim(),
                noiseType: this.activeTrack?.noise_type || 'white',
                settings: {
                    lfoSpeed: this.customLfoSpeed,
                    lfoDepth: this.customLfoDepth,
                    brightness: this.customBrightness,
                    volume: this.volume,
                },
            });
            this._savePresets();
        },

        /** Load a named preset. */
        loadPreset(preset) {
            this.customLfoSpeed = preset.settings.lfoSpeed;
            this.customLfoDepth = preset.settings.lfoDepth;
            this.customBrightness = preset.settings.brightness;
            this.volume = preset.settings.volume;
            if (this.noisePlayer) {
                this.noisePlayer.applySettings(preset.settings);
            }
            this._saveCustomSettings();
        },

        /** Delete a named preset. */
        deletePreset(name) {
            this.presets = this.presets.filter(p => p.name !== name);
            this._savePresets();
        },

        // ── Internal ──

        _playNoise(type) {
            if (!NoisePlayer.isSupported()) {
                console.warn('Web Audio API not supported');
                return;
            }
            this.noisePlayer = new NoisePlayer();
            this.noisePlayer.setVolume(this.volume, 100);
            this.noisePlayer.play(type, { fadeMs: 200, scheduledFadeSecs: 120 });
        },

        _playAmbient(url) {
            this.ambientAudio = new Audio(url);
            this.ambientAudio.loop = true;
            this.ambientAudio.volume = this.volume;
            this.ambientAudio.play().catch(e => {
                console.warn('Ambient audio autoplay blocked:', e);
                // Browser requires user gesture — fine, user can click play
            });
        },

        _csrf() {
            return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
        },

        _saveCustomSettings() {
            if (!this.activeTrack || this.activeTrack.category !== 'noise') return;
            const key = `fixate-noise-custom-${this.activeTrack.noise_type}`;
            localStorage.setItem(key, JSON.stringify({
                lfoSpeed: this.customLfoSpeed,
                lfoDepth: this.customLfoDepth,
                brightness: this.customBrightness,
                volume: this.volume,
            }));
        },

        _savePresets() {
            localStorage.setItem('fixate-noise-presets', JSON.stringify(this.presets));
        },

        _loadPresets() {
            const saved = localStorage.getItem('fixate-noise-presets');
            if (saved) {
                try { this.presets = JSON.parse(saved); } catch(e) { this.presets = []; }
            }
        },

        // ── Bilateral Stimulation ──

        _startBilateral() {
            if (!this._bilateral) {
                this._bilateral = new BilateralStimulation({ preset: this.bilateralPreset });
            }
            this._bilateral.setPreset(this.bilateralPreset);
            this._bilateral.start();
        },

        _stopBilateral() {
            if (this._bilateral) {
                this._bilateral.stop();
                this._bilateral = null;
            }
        },

        onBilateralToggle() {
            if (this.bilateralOn) {
                this._startBilateral();
            } else {
                this._stopBilateral();
            }
            localStorage.setItem('fixate-bilateral', JSON.stringify({
                on: this.bilateralOn,
                preset: this.bilateralPreset,
            }));
        },

        onBilateralPresetChange() {
            if (this._bilateral) {
                this._bilateral.setPreset(this.bilateralPreset);
            }
            localStorage.setItem('fixate-bilateral', JSON.stringify({
                on: this.bilateralOn,
                preset: this.bilateralPreset,
            }));
        },

        // ── Cleanup ──
        destroy() {
            this._stopBilateral();
            if (this.noisePlayer) this.noisePlayer.destroy();
            if (this.ambientAudio) {
                this.ambientAudio.pause();
                this.ambientAudio = null;
            }
        }
    }));
});
