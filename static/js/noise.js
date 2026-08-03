/**
 * Fixate Noise Generator — Web Audio API client-side noise generation.
 *
 * Three noise types (research-backed):
 *   - White: equal energy at all frequencies. Most studied for ADHD (g=0.249).
 *   - Pink:   -3dB/octave. Rain-like. Good for sustained attention.
 *   - Brown:  -6dB/octave. Deep rumble. Popular but zero studies.
 *
 * Audio chain:
 *   source → eqNode → gainNode → destination
 *   lfoNode → lfoGainNode → gainNode.gain (modulation)
 *
 * User-customizable parameters (per noise type):
 *   - lfoSpeed:   0.05 – 1.0 Hz (default 0.18) — modulation speed
 *   - lfoDepth:   0.01 – 0.10    (default 0.03) — modulation intensity
 *   - brightness: -1.0 – +1.0    (default 0.0)  — EQ tilt (negative = darker)
 *   - volume:     0.0 – 1.0      (default 0.4)  — base volume
 *
 * Usage:
 *   const player = new NoisePlayer();
 *   player.play('pink');
 *   player.setLFO(0.3, 0.06);    // faster, deeper modulation
 *   player.setBrightness(-0.5);   // darker (cut highs)
 *   player.setVolume(0.5);
 *   player.getSettings();         // { lfoSpeed, lfoDepth, brightness, volume, type }
 *   player.applySettings(settings); // restore saved settings
 */

class NoisePlayer {
    constructor() {
        this.ctx = null;
        this.currentType = null;
        this.currentNode = null;   // AudioBufferSourceNode
        this.gainNode = null;      // GainNode (volume + fade)
        this.eqNode = null;        // BiquadFilterNode (brightness)
        this.lfoNode = null;       // OscillatorNode (LFO)
        this.lfoGainNode = null;   // GainNode (LFO depth)
        this.volume = 0.4;
        this.lfoSpeed = 0.18;
        this.lfoDepth = 0.03;
        this.brightness = 0.0;     // -1.0 (dark) to +1.0 (bright)
        this.isPlaying = false;
        this.fadeTimer = null;
    }

    /** Ensure AudioContext exists (must be called from user gesture). */
    _ensureContext() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();

            // ── EQ node (brightness/darkness) ──
            // Low-shelf filter: cut/boost everything below 2000 Hz
            // Positive brightness = cut lows (makes it brighter/thinner)
            // Negative brightness = boost lows (makes it darker/warmer)
            this.eqNode = this.ctx.createBiquadFilter();
            this.eqNode.type = 'lowshelf';
            this.eqNode.frequency.value = 1500;
            this.eqNode.gain.value = 0; // neutral

            // ── Gain node (volume + fade) ──
            this.gainNode = this.ctx.createGain();
            this.gainNode.gain.value = 0; // start silent

            // ── LFO modulation (prevents habituation) ──
            this.lfoNode = this.ctx.createOscillator();
            this.lfoGainNode = this.ctx.createGain();
            this.lfoNode.frequency.value = this.lfoSpeed;
            this.lfoGainNode.gain.value = this.lfoDepth;
            this.lfoNode.connect(this.lfoGainNode);
            this.lfoGainNode.connect(this.gainNode.gain);
            this.lfoNode.start();

            // ── Chain ──
            // source → eqNode → gainNode → destination
            this.eqNode.connect(this.gainNode);
            this.gainNode.connect(this.ctx.destination);
        }
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    /**
     * Generate a buffer of noise samples.
     * @param {string} type - 'white', 'pink', or 'brown'
     * @returns {AudioBuffer}
     */
    _generateBuffer(type) {
        const sampleRate = this.ctx.sampleRate;
        const duration = 2;
        const length = sampleRate * duration;
        const buffer = this.ctx.createBuffer(1, length, sampleRate);
        const data = buffer.getChannelData(0);

        switch (type) {
        case 'white':
            for (let i = 0; i < length; i++) {
                data[i] = Math.random() * 2 - 1;
            }
            break;

        case 'pink':
            let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
            for (let i = 0; i < length; i++) {
                const white = Math.random() * 2 - 1;
                b0 = 0.99886 * b0 + white * 0.0555179;
                b1 = 0.99332 * b1 + white * 0.0750759;
                b2 = 0.96900 * b2 + white * 0.1538520;
                b3 = 0.86650 * b3 + white * 0.3104856;
                b4 = 0.55000 * b4 + white * 0.5329522;
                b5 = -0.7616 * b5 - white * 0.0168980;
                data[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362) * 0.11;
                b6 = white * 0.115926;
            }
            break;

        case 'brown':
            let last = 0;
            for (let i = 0; i < length; i++) {
                const white = Math.random() * 2 - 1;
                last = (last + (0.02 * white)) / 1.02;
                data[i] = last * 3.5;
            }
            break;

        default:
            console.warn('Unknown noise type:', type, 'falling back to white');
            return this._generateBuffer('white');
        }

        return buffer;
    }

    // ── Playback ──

    /** Start playing a noise type.
     *  @param {string} type - 'white', 'pink', 'brown'
     *  @param {number|object} [opts=300] - fadeMs number, or options object { fadeMs, scheduledFadeSecs }
     */
    play(type, opts = {}) {
        const fadeMs = typeof opts === 'number' ? opts : (opts.fadeMs || 300);
        const scheduledFadeSecs = typeof opts === 'object' ? (opts.scheduledFadeSecs || 0) : 0;

        this._ensureContext();

        if (this.currentNode) {
            this._stopSource();
        }

        // Clear any existing scheduler
        if (this._schedulerTimer) {
            clearInterval(this._schedulerTimer);
            this._schedulerTimer = null;
        }

        this.currentType = type;
        const buffer = this._generateBuffer(type);
        const source = this.ctx.createBufferSource();
        source.buffer = buffer;
        source.loop = true;
        source.connect(this.eqNode);
        source.start(0);
        this.currentNode = source;
        this.isPlaying = true;

        // Noise scheduler: start loud, fade to maintenance over N seconds
        if (scheduledFadeSecs > 0) {
            const startVol = Math.min(this.volume * 1.6, 0.7); // peak at 70% max
            const targetVol = this.volume;
            const steps = Math.ceil(scheduledFadeSecs * 10); // update every 100ms
            const volDrop = (startVol - targetVol) / steps;
            let currentVol = startVol;

            this._fadeGain(currentVol, 200); // quick ramp to peak

            this._schedulerTimer = setInterval(() => {
                currentVol = Math.max(targetVol, currentVol - volDrop);
                if (this.gainNode && this.ctx) {
                    this._fadeGain(currentVol, 80); // smooth 80ms ramps
                }
                if (currentVol <= targetVol) {
                    clearInterval(this._schedulerTimer);
                    this._schedulerTimer = null;
                }
            }, 100);
        } else {
            this._fadeGain(this.volume, fadeMs);
        }
    }

    /** Crossfade to a different noise type.
     *  @param {string} type
     *  @param {number} [crossfadeMs=500]
     */
    fadeTo(type, crossfadeMs = 500) {
        if (type === this.currentType) return;

        const half = crossfadeMs / 2;
        this._fadeGain(0, half);

        clearTimeout(this.fadeTimer);
        this.fadeTimer = setTimeout(() => {
            if (this.currentNode) this._stopSource();
            this._ensureContext();
            const buffer = this._generateBuffer(type);
            const source = this.ctx.createBufferSource();
            source.buffer = buffer;
            source.loop = true;
            source.connect(this.eqNode);
            source.start(0);
            this.currentNode = source;
            this.currentType = type;
            this._fadeGain(this.volume, half);
        }, half);
    }

    setVolume(v, rampMs = 100) {
        this.volume = Math.max(0, Math.min(1, v));
        if (this.gainNode && this.ctx) {
            this._fadeGain(this.volume, rampMs);
        }
    }

    stop(fadeMs = 200) {
        if (!this.isPlaying) return;
        // Clear scheduler if active
        if (this._schedulerTimer) {
            clearInterval(this._schedulerTimer);
            this._schedulerTimer = null;
        }
        this._fadeGain(0, fadeMs);
        clearTimeout(this.fadeTimer);
        this.fadeTimer = setTimeout(() => this._stopSource(), fadeMs + 50);
    }

    pause() {
        if (this.ctx && this.ctx.state === 'running') this.ctx.suspend();
    }

    resume() {
        if (this.ctx && this.ctx.state === 'suspended') this.ctx.resume();
    }

    destroy() {
        clearTimeout(this.fadeTimer);
        this._stopSource();
        if (this.lfoNode) {
            try { this.lfoNode.stop(); } catch(e) {}
            this.lfoNode = null;
        }
        if (this.ctx) {
            this.ctx.close();
            this.ctx = null;
            this.gainNode = null;
            this.eqNode = null;
            this.lfoGainNode = null;
        }
        this.isPlaying = false;
    }

    static isSupported() {
        return !!(window.AudioContext || window.webkitAudioContext);
    }

    // ── Customization API ──

    /**
     * Set LFO modulation parameters.
     * @param {number} speed — Hz, 0.05 to 1.0 (default 0.18)
     * @param {number} depth — 0.01 to 0.10 (default 0.03)
     */
    setLFO(speed, depth) {
        this.lfoSpeed = Math.max(0.05, Math.min(1.0, speed));
        this.lfoDepth = Math.max(0.01, Math.min(0.10, depth));
        if (this.lfoNode) {
            this.lfoNode.frequency.value = this.lfoSpeed;
        }
        if (this.lfoGainNode) {
            this.lfoGainNode.gain.value = this.lfoDepth;
        }
    }

    /**
     * Set brightness/darkness via EQ tilt.
     * @param {number} val — -1.0 (dark, bassy) to +1.0 (bright, airy). 0 = neutral.
     *
     * Maps to low-shelf gain: negative = darker (boost lows), positive = brighter (cut lows).
     * Range: -15 dB to +15 dB on the low shelf.
     */
    setBrightness(val) {
        this.brightness = Math.max(-1.0, Math.min(1.0, val));
        if (this.eqNode) {
            // Map [-1, 1] to [-12, 12] dB
            this.eqNode.gain.value = this.brightness * -12;
        }
    }

    /**
     * Get current settings as a serializable object.
     * Use with applySettings() to restore saved state.
     * @returns {{type, volume, lfoSpeed, lfoDepth, brightness}}
     */
    getSettings() {
        return {
            type: this.currentType,
            volume: this.volume,
            lfoSpeed: this.lfoSpeed,
            lfoDepth: this.lfoDepth,
            brightness: this.brightness,
        };
    }

    /**
     * Apply a previously-saved settings object.
     * @param {object} s — from getSettings()
     */
    applySettings(s) {
        if (!s) return;
        this.setLFO(s.lfoSpeed || 0.18, s.lfoDepth || 0.03);
        this.setBrightness(s.brightness || 0.0);
        this.setVolume(s.volume || 0.4);
    }

    // ── Internal ──

    _stopSource() {
        try {
            if (this.currentNode) {
                this.currentNode.stop();
                this.currentNode.disconnect();
            }
        } catch (e) { /* already stopped */ }
        this.currentNode = null;
        this.isPlaying = false;
    }

    _fadeGain(targetValue, durationMs) {
        if (!this.gainNode || !this.ctx) return;
        const now = this.ctx.currentTime;
        this.gainNode.gain.cancelScheduledValues(now);
        this.gainNode.gain.setValueAtTime(this.gainNode.gain.value, now);
        this.gainNode.gain.linearRampToValueAtTime(targetValue, now + durationMs / 1000);
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NoisePlayer };
}
