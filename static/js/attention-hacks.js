/**
 * Fixate Attention Hack Engine — Neuroscience-informed TTS Transitions
 *
 * Uses prediction error (auditory oddball paradigm) to trigger orienting
 * responses that snap wandering attention back to the task. When two audio
 * streams overlap unexpectedly, the auditory cortex flags a salience event
 * → P300-like response → task-positive network re-engages.
 *
 * Research basis:
 *   - Prediction error → orienting response (Correa et al., 2006)
 *   - Oddball P300: unexpected stimulus = automatic attention capture
 *   - Phonological loop interference: concurrent speech streams overload
 *     working memory → brain must reallocate attention (Baddeley, 2007)
 *   - DMN disrupted by salient external stimuli → frontoparietal control
 *     network activates (Seeley et al., 2007)
 *
 * Five hack modes (selectable per user):
 *
 *   1. overlap-bridge  — Sound cue fades in over last 3 words of segment A,
 *                         continues through silence, fades during first words
 *                         of segment B. Creates perceptual overlap without
 *                         requiring dual TTS streams.
 *
 *   2. cut-and-surprise — Hard-cancel TTS 2 words before segment end, fire
 *                          jarring 0.3s cue (glitch/scrape/pop), restart next
 *                          segment. Maximally disruptive → strongest re-engage.
 *
 *   3. voice-switch     — Switch to a different voice for first 3 words of new
 *                          segment, then revert. Voice identity mismatch triggers
 *                          speaker-normalization re-engagement.
 *
 *   4. speed-ramp       — Gradually increase rate to 1.4x over last 5 words,
 *                          creating urgency, then snap back to normal rate on
 *                          new segment. Temporal expectation violation.
 *
 *   5. stutter          — Three micro pause/resume cycles (60ms each) at
 *                          transition boundary. Simulated dysfluency forces
 *                          phonological loop to re-lock onto the stream.
 *
 * Intensity 0.0–1.0 controls how aggressively the hack is applied:
 *   - 0.0: Gentle (quieter cues, slower ramp, subtle voice change)
 *   - 0.5: Moderate (default)
 *   - 1.0: Aggressive (loud cues, fast ramp, maximally different voice)
 *
 * Usage:
 *   const hacks = new AttentionHackEngine({
 *       tts: window.__fixateTTS,
 *       soundCues: soundCueEngine,
 *       mode: 'overlap-bridge',
 *       intensity: 0.5,
 *   });
 *   hacks.startReading(paragraphs);
 */

class AttentionHackEngine {
    /**
     * @param {object} opts
     * @param {FixateTTS} opts.tts — TTS engine instance
     * @param {SoundCueEngine} opts.soundCues — sound cue engine
     * @param {string} [opts.mode='overlap-bridge'] — hack mode
     * @param {number} [opts.intensity=0.5] — aggression 0.0–1.0
     * @param {function} [opts.onSegmentChange] — called when segment advances
     */
    constructor(opts = {}) {
        this.tts = opts.tts;
        this.soundCues = opts.soundCues;
        this.mode = opts.mode || 'overlap-bridge';
        this.intensity = Math.max(0, Math.min(1, opts.intensity ?? 0.5));
        this.onSegmentChange = opts.onSegmentChange || null;

        this._segments = [];
        this._currentIdx = -1;
        this._active = false;
        this._paused = false;
        this._wordCount = 0;
        this._wordPos = 0;
        this._transitioning = false;
        this._originalVoice = null;
        this._originalRate = null;
    }

    /** Available modes with descriptions. */
    static get MODES() {
        return [
            { id: 'overlap-bridge',  label: 'Overlap Bridge',  desc: 'Sound cue crossfades between segments' },
            { id: 'cut-and-surprise', label: 'Cut & Surprise',  desc: 'Abrupt stop + jarring cue between segments' },
            { id: 'voice-switch',     label: 'Voice Switch',    desc: 'Different voice for transition words' },
            { id: 'speed-ramp',       label: 'Speed Ramp',      desc: 'Urgency ramp at end, snap back on next' },
            { id: 'stutter',          label: 'Stutter',         desc: 'Micro-pauses force re-locking attention' },
        ];
    }

    /** Sound cue categories best suited for each mode. */
    static get MODE_CUES() {
        return {
            'overlap-bridge':  ['whoosh', 'reverse', 'chord', 'twinkle', 'ding'],
            'cut-and-surprise': ['glitch', 'scrape', 'pop', 'buzz', 'alert'],
            'voice-switch':     ['ding', 'subtle', 'woodblock', 'drop'],
            'speed-ramp':       ['whoosh', 'ding', 'subtle'],  // subtle — ramp does the work
            'stutter':          ['glitch', 'buzz', 'pop', 'scrape'],
        };
    }

    /**
     * Split text into segments and start reading with attention hacks.
     * Segments are paragraphs; very long paragraphs get split further.
     * @param {string} fullText
     */
    startReading(fullText) {
        this.stop();

        // Split into paragraphs, then split long paragraphs by sentence count
        const rawSegments = fullText.split(/\n\n+/).filter(s => s.trim().length > 0);
        this._segments = [];
        for (const seg of rawSegments) {
            const sentences = seg.match(/[^.!?]+[.!?]+/g) || [seg];
            if (sentences.length <= 6) {
                this._segments.push(seg.trim());
            } else {
                // Split long paragraphs into chunks of ~4 sentences
                for (let i = 0; i < sentences.length; i += 4) {
                    this._segments.push(sentences.slice(i, i + 4).join(' ').trim());
                }
            }
        }

        if (this._segments.length === 0) return;

        this._active = true;
        this._currentIdx = -1;
        this._originalVoice = this.tts.preferredVoice;
        this._originalRate = this.tts.rate;

        this._readNext();
    }

    /** Pause between segments. */
    pause() {
        this._paused = true;
        this.tts.pause();
    }

    /** Resume from paused state. */
    resume() {
        this._paused = false;
        if (this._transitioning) {
            // Mid-transition — restart current segment
            this._currentIdx--;
            this._readNext();
        } else {
            this.tts.resume();
        }
    }

    /** Stop entirely. */
    stop() {
        this._active = false;
        this._paused = false;
        this._transitioning = false;
        this.tts.stop();

        // Restore original voice/rate if voice-switch mode modified them
        if (this._originalVoice) this.tts.setVoice(this._originalVoice);
        if (this._originalRate) this.tts.setRate(this._originalRate);
    }

    get isActive() { return this._active; }
    get isPaused() { return this._paused; }
    get currentSegment() { return this._currentIdx + 1; }
    get totalSegments() { return this._segments.length; }

    // ── Internal ──

    _readNext() {
        if (!this._active || this._paused) return;
        this._currentIdx++;

        if (this._currentIdx >= this._segments.length) {
            // Done — restore original settings
            this._active = false;
            if (this._originalVoice) this.tts.setVoice(this._originalVoice);
            if (this._originalRate) this.tts.setRate(this._originalRate);
            if (this.onSegmentChange) this.onSegmentChange({ done: true });
            return;
        }

        const segment = this._segments[this._currentIdx];
        if (!segment.trim()) {
            this._readNext();
            return;
        }

        if (this.onSegmentChange) {
            this.onSegmentChange({
                current: this._currentIdx + 1,
                total: this._segments.length,
            });
        }

        // Count words for boundary tracking
        this._wordCount = segment.split(/\s+/).filter(w => w.length > 0).length;
        this._wordPos = 0;

        // Apply mode-specific pre-reading setup
        this._applyModeSetup(segment);

        // Speak with boundary tracking for overlap/transition detection
        this.tts.speakWithBoundary(segment, (pos) => {
            this._wordPos = pos;

            if (this.mode === 'overlap-bridge' || this.mode === 'cut-and-surprise') {
                this._checkOverlapTrigger();
            } else if (this.mode === 'speed-ramp') {
                this._checkSpeedRamp();
            }
        }, () => {
            // onEnd — segment finished naturally
            if (this.mode === 'overlap-bridge') {
                // Cue already playing from _checkOverlapTrigger
                // Start next segment — the cue provides the bridge
                this._transitioning = true;
                setTimeout(() => {
                    this._transitioning = false;
                    this._readNext();
                }, 150); // tiny gap to let cue breathe
            } else if (this.mode === 'cut-and-surprise') {
                // Nothing extra — cut already happened in _checkOverlapTrigger
                // Next segment started there
            } else if (this.mode === 'voice-switch') {
                this._applyVoiceSwitchTransition();
            } else if (this.mode === 'stutter') {
                this._applyStutterTransition();
            } else {
                // speed-ramp or default: just continue
                this._readNext();
            }
        });
    }

    /**
     * Set up TTS rate/voice for the start of a segment based on current mode.
     */
    _applyModeSetup(segment) {
        // Store original rate for restoration
        this._originalRate = this.tts.rate;

        if (this.mode === 'speed-ramp') {
            // Start at normal rate; ramp will accelerate near end
            // No setup needed — normal rate is fine
        } else if (this.mode === 'voice-switch') {
            // First words of NEW segment get a different voice (applied in transition)
            // No pre-setup needed; transition handles it
        }
    }

    /**
     * Overlap bridge: fire a cue 3 words before segment end.
     * The cue plays over the last words, bridges the silence, and fades
     * into the next segment's opening.
     */
    _checkOverlapTrigger() {
        const overlapWords = this.mode === 'cut-and-surprise' ? 2 : 3;
        const triggerPos = this._wordCount - overlapWords;

        if (this._wordPos >= triggerPos && !this._transitioning) {
            this._transitioning = true;

            // Choose cue based on mode
            const pool = AttentionHackEngine.MODE_CUES[this.mode];
            const cueCategory = pool[Math.floor(Math.random() * pool.length)];

            // Volume scales with intensity
            const vol = 0.15 + this.intensity * 0.15; // 0.15–0.30

            if (this.mode === 'cut-and-surprise') {
                // Hard cut TTS, fire jarring cue, then start next
                this.tts.stop();
                this.soundCues.playCategory(cueCategory);

                // Start next segment after cue (short delay for max jarring)
                const delay = 200 + (1 - this.intensity) * 200; // 200–400ms
                setTimeout(() => {
                    this._transitioning = false;
                    this._readNext();
                }, delay);
            } else {
                // overlap-bridge: cue plays NOW over the last words
                this.soundCues.playCategory(cueCategory);
                // onEnd callback above handles starting next segment
            }
        }
    }

    /**
     * Speed ramp: gradually accelerate TTS rate as we approach segment end,
     * then snap back to normal rate for next segment.
     */
    _checkSpeedRamp() {
        const rampWords = 5; // last 5 words get accelerated
        const rampStart = this._wordCount - rampWords;

        if (this._wordPos >= rampStart && this._wordPos < this._wordCount) {
            // Linearly ramp from normal to 1.4x (scaled by intensity)
            const progress = (this._wordPos - rampStart) / rampWords;
            const maxRate = 1.0 + this.intensity * 0.5; // 1.0–1.5x
            const currentRate = 1.0 + progress * (maxRate - 1.0);

            // Update TTS rate dynamically (speechSynthesis handles mid-utterance changes)
            this.tts.setRate(currentRate);
        }
    }

    /**
     * Voice switch: after segment A ends, switch to a maximally different voice
     * for first 3 words of segment B, then switch back.
     */
    _applyVoiceSwitchTransition() {
        const voices = this.tts.getVoices();

        // Find a voice maximally different from current
        const currentName = this.tts.preferredVoice || '';
        let altVoice = null;

        // Prefer different-gender voice for maximum contrast
        const isFemaleLike = /female|woman|zira|samantha|moira|fiona|karen|veena/i;
        const isMaleLike = /male|man|david|mark|guy|daniel|alex|tom/i;

        const currentIsFemale = isFemaleLike.test(currentName);
        const currentIsMale = isMaleLike.test(currentName);

        for (const v of voices) {
            if (v.name === currentName) continue;
            if (currentIsFemale && isMaleLike.test(v.name)) { altVoice = v; break; }
            if (currentIsMale && isFemaleLike.test(v.name)) { altVoice = v; break; }
        }

        // Fallback: any voice that's not current
        if (!altVoice) {
            altVoice = voices.find(v => v.name !== currentName) || voices[0];
        }

        if (altVoice) {
            this.tts.setVoice(altVoice.name);
        }

        // Start next segment with alt voice, then revert on first boundary
        const nextSegment = this._segments[this._currentIdx + 1];
        const words = (nextSegment || '').split(/\s+/).filter(w => w.length > 0);
        const switchBackAfter = Math.min(3, Math.floor(words.length / 2)); // first 3 words or half

        let wordCountInSegment = 0;
        const originalOnBoundary = this.tts.onBoundary;

        this.tts.onBoundary = (boundary) => {
            wordCountInSegment++;
            if (wordCountInSegment >= switchBackAfter && this.tts.preferredVoice !== this._originalVoice) {
                this.tts.setVoice(this._originalVoice);
                this.tts.onBoundary = originalOnBoundary; // restore
            }
            if (originalOnBoundary) originalOnBoundary(boundary);
        };

        this._readNext();
    }

    /**
     * Stutter: three micro pause/resume cycles at transition boundary.
     * Simulated dysfluency forces phonological loop to re-lock.
     */
    _applyStutterTransition() {
        const nextSegment = this._segments[this._currentIdx + 1];
        if (!nextSegment) {
            this._active = false;
            return;
        }

        // Speak the first word, pause, resume, pause, resume — stutter effect
        const words = nextSegment.split(/\s+/).filter(w => w.length > 0);
        if (words.length === 0) { this._readNext(); return; }

        // Use a very short chunk (~first 2 words) for the stutter
        const chunk = words.slice(0, Math.min(2, words.length)).join(' ');
        const rest = words.slice(Math.min(2, words.length)).join(' ');

        // Fire a subtle stutter cue
        const pool = AttentionHackEngine.MODE_CUES['stutter'];
        const cue = pool[Math.floor(Math.random() * pool.length)];

        // Stutter sequence: speak chunk → pause → cue → resume chunk → pause → continue
        const stutterGap = 60 + (1 - this.intensity) * 40; // 60–100ms

        this.tts.speak(chunk);
        setTimeout(() => {
            this.tts.pause();
            this.soundCues.playCategory(cue);
            setTimeout(() => {
                this.tts.resume();
                setTimeout(() => {
                    this.tts.pause();
                    setTimeout(() => {
                        this.tts.resume();
                        // Now continue with the full segment
                        this._transitioning = true;
                        this._transitioning = false;
                        // Read the full segment from current position
                        this._continueWithRemaining(nextSegment);
                    }, stutterGap);
                }, stutterGap * 2);
            }, stutterGap);
        }, 300);
    }

    /**
     * After stutter transition, continue reading from a specific segment.
     */
    _continueWithRemaining(segment) {
        // Reset word tracking for this segment
        this._wordCount = segment.split(/\s+/).filter(w => w.length > 0).length;
        this._wordPos = 0;

        this.tts.speakWithBoundary(segment, (pos) => {
            this._wordPos = pos;
        }, () => {
            this._readNext();
        });
    }

    /**
     * Update mode at runtime.
     */
    setMode(mode) {
        if (AttentionHackEngine.MODES.find(m => m.id === mode)) {
            this.mode = mode;
        }
    }

    /**
     * Update intensity at runtime.
     */
    setIntensity(val) {
        this.intensity = Math.max(0, Math.min(1, val));
    }
}
