/**
 * Fixate TTS Engine — Reader Text-to-Speech via Web Speech API
 *
 * Wraps the browser's built-in speechSynthesis with voice selection,
 * rate/volume control, and persistence. Paused automatically when
 * DMN disruption sound cues fire (via window.__fixateTTS hook).
 *
 * Usage:
 *   const tts = new FixateTTS({ rate: 1.0, volume: 0.8 });
 *   tts.speak("Hello world");
 *   tts.pause();
 *   tts.resume();
 *   tts.stop();
 *   tts.getVoices(); // [{name, lang, default}]
 */

class FixateTTS {
    /**
     * @param {object} opts
     * @param {number} [opts.rate=1.0] — speech rate (0.1-3.0)
     * @param {number} [opts.volume=0.8] — volume (0-1)
     * @param {string} [opts.voiceName] — preferred voice name (fuzzy match)
     * @param {function} [opts.onBoundary] — called on word boundary with {charIndex, charLength}
     * @param {function} [opts.onEnd] — called when utterance finishes
     * @param {function} [opts.onError] — called on error
     */
    constructor(opts = {}) {
        this.rate = opts.rate ?? 1.0;
        this.volume = opts.volume ?? 0.8;
        this.preferredVoice = opts.voiceName || null;
        this.onBoundary = opts.onBoundary || null;
        this.onEnd = opts.onEnd || null;
        this.onError = opts.onError || null;

        this._synth = window.speechSynthesis;
        this._speaking = false;
        this._paused = false;
        this._currentUtterance = null;
        this._voicesLoaded = false;

        // Register global hook so sound cues can pause us
        window.__fixateTTS = this;

        // Load voices (async on some browsers)
        this._loadVoices();

        // Restore saved settings
        this._loadSettings();
    }

    /** Get available voices. Returns [] until voices load (use getVoicesAsync). */
    getVoices() {
        return this._synth.getVoices().map(v => ({
            name: v.name,
            lang: v.lang,
            default: v.default,
            localService: v.localService,
        }));
    }

    /** Get voices, waiting for load if needed. Returns Promise<Voice[]>. */
    async getVoicesAsync() {
        await this._waitForVoices();
        return this.getVoices();
    }

    /** Speak text from current position. If already speaking, replaces. */
    speak(text) {
        if (!text) return;
        this.stop();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = this.rate;
        utterance.volume = this.volume;

        // Set preferred voice if available
        if (this.preferredVoice) {
            const voices = this._synth.getVoices();
            const match = voices.find(v =>
                v.name.includes(this.preferredVoice) ||
                this.preferredVoice.includes(v.name)
            );
            if (match) utterance.voice = match;
        }

        // Word boundary callback (for highlighting)
        if (this.onBoundary) {
            utterance.onboundary = (event) => {
                if (event.name === 'word') {
                    this.onBoundary({
                        charIndex: event.charIndex,
                        charLength: event.charLength || 5,
                    });
                }
            };
        }

        utterance.onend = () => {
            this._speaking = false;
            this._paused = false;
            this._currentUtterance = null;
            if (this.onEnd) this.onEnd();
        };

        utterance.onerror = (e) => {
            this._speaking = false;
            this._currentUtterance = null;
            if (this.onError) this.onError(e);
        };

        this._currentUtterance = utterance;
        this._synth.speak(utterance);
        this._speaking = true;
        this._paused = false;
    }

    /**
     * Speak text with per-word boundary tracking and segment-end callback.
     * Designed for the AttentionHackEngine to detect transition points.
     *
     * @param {string} text — text to speak
     * @param {function} onWord — called with word position {wordIndex, wordCount}
     * @param {function} onSegmentEnd — called when speech finishes naturally
     */
    speakWithBoundary(text, onWord, onSegmentEnd) {
        if (!text) return;
        this.stop();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = this.rate;
        utterance.volume = this.volume;

        if (this.preferredVoice) {
            const voices = this._synth.getVoices();
            const match = voices.find(v =>
                v.name.includes(this.preferredVoice) ||
                this.preferredVoice.includes(v.name)
            );
            if (match) utterance.voice = match;
        }

        let wordPos = 0;
        utterance.onboundary = (event) => {
            if (event.name === 'word') {
                wordPos++;
                if (onWord) onWord(wordPos);
                // Also fire the original onBoundary if set (for highlighting)
                if (this.onBoundary) {
                    this.onBoundary({
                        charIndex: event.charIndex,
                        charLength: event.charLength || 5,
                    });
                }
            }
        };

        utterance.onend = () => {
            this._speaking = false;
            this._paused = false;
            this._currentUtterance = null;
            if (onSegmentEnd) onSegmentEnd();
            if (this.onEnd) this.onEnd();
        };

        utterance.onerror = (e) => {
            this._speaking = false;
            this._currentUtterance = null;
            if (this.onError) this.onError(e);
        };

        this._currentUtterance = utterance;
        this._synth.speak(utterance);
        this._speaking = true;
        this._paused = false;
    }

    /** Pause current speech. */
    pause() {
        if (this._speaking && !this._paused) {
            this._synth.pause();
            this._paused = true;
        }
    }

    /** Resume paused speech. */
    resume() {
        if (this._paused) {
            this._synth.resume();
            this._paused = false;
        }
    }

    /** Stop speech entirely (cannot resume after this). */
    stop() {
        this._synth.cancel();
        this._speaking = false;
        this._paused = false;
        this._currentUtterance = null;
    }

    /** Set speech rate and persist. */
    setRate(rate) {
        this.rate = Math.max(0.1, Math.min(3.0, rate));
        this._saveSettings();
    }

    /** Set volume and persist. */
    setVolume(vol) {
        this.volume = Math.max(0, Math.min(1, vol));
        this._saveSettings();
    }

    /** Set preferred voice by name and persist. */
    setVoice(voiceName) {
        this.preferredVoice = voiceName;
        this._saveSettings();
    }

    get isSpeaking() { return this._speaking; }
    get isPaused() { return this._paused; }

    // ── Internal ──

    _loadVoices() {
        const voices = this._synth.getVoices();
        if (voices.length > 0) {
            this._voicesLoaded = true;
            return;
        }
        // Chrome loads voices asynchronously
        this._synth.onvoiceschanged = () => {
            this._voicesLoaded = true;
        };
    }

    async _waitForVoices() {
        if (this._voicesLoaded) return;
        return new Promise(resolve => {
            const check = () => {
                if (this._synth.getVoices().length > 0) {
                    this._voicesLoaded = true;
                    resolve();
                } else {
                    setTimeout(check, 100);
                }
            };
            check();
        });
    }

    _saveSettings() {
        localStorage.setItem('fixate-tts', JSON.stringify({
            rate: this.rate,
            volume: this.volume,
            voiceName: this.preferredVoice,
        }));
    }

    _loadSettings() {
        try {
            const saved = JSON.parse(localStorage.getItem('fixate-tts') || '{}');
            if (saved.rate) this.rate = saved.rate;
            if (saved.volume !== undefined) this.volume = saved.volume;
            if (saved.voiceName) this.preferredVoice = saved.voiceName;
        } catch (e) {}
    }

    /** Clean up global hook. */
    destroy() {
        this.stop();
        if (window.__fixateTTS === this) {
            window.__fixateTTS = null;
        }
    }
}
