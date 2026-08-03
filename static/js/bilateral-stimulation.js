/**
 * Fixate Bilateral Stimulation Engine — EMDR-Inspired Hemispheric Focus
 *
 * Generates sustained alternating left-right audio tones using the Web Audio API.
 * Originally the engine behind EMDR therapy (trauma processing), bilateral
 * stimulation has since been studied for ADHD attention improvement. The
 * alternating sensory input engages both brain hemispheres simultaneously,
 * which research suggests improves executive function and sustained attention
 * (PMC12641405, 2025; ADDitude Magazine, 2024).
 *
 * How it works:
 *   - A soft tone is panned left → right → left → right at a configurable frequency
 *   - Uses StereoPannerNode for true left/right separation (not just gain difference)
 *   - Can be layered UNDER existing background noise (independent AudioContext nodes)
 *   - The rhythm creates an orienting response that the brain can't fully habituate to
 *
 * Frequency bands (based on neural entrainment research):
 *   - theta (4-7 Hz)   — relaxed focus, creative flow, meditation-like
 *   - alpha (8-12 Hz)  — alert calm, ideal for reading, the "ready" state
 *   - beta  (13-30 Hz) — intense focus, active concentration, problem-solving
 *   - low   (0.5-4 Hz) — very slow alternation, almost like a breathing guide
 *
 * Tone types:
 *   - soft-tick   — brief percussive click, non-intrusive
 *   - sine-pulse  — smooth sine wave pulse, melodic
 *   - noise-sweep — filtered noise sweep, subtle
 *   - chime       — short bell-like ping, pleasant
 *
 * Usage:
 *   const bs = new BilateralStimulation({
 *       frequency: 10,      // 10 Hz alpha
 *       type: 'soft-tick',
 *       volume: 0.15,
 *   });
 *   bs.start();
 *   bs.stop();
 *   bs.setFrequency(14);   // switch to beta mid-session
 */

class BilateralStimulation {
    /**
     * @param {object} opts
     * @param {number} [opts.frequency=10] — alternation rate in Hz (0.5-30)
     * @param {string} [opts.type='soft-tick'] — tone type
     * @param {number} [opts.volume=0.12] — master volume 0-1 (HARD CAPPED at 0.2)
     * @param {string} [opts.preset='alpha'] — preset name (theta/alpha/beta/low)
     */
    constructor(opts = {}) {
        this.type = opts.type || 'soft-tick';
        this._volume = Math.min(opts.volume ?? 0.12, 0.2); // hard cap 20%

        // Apply preset if given, then override with explicit frequency
        if (opts.preset && BilateralStimulation.PRESETS[opts.preset]) {
            const p = BilateralStimulation.PRESETS[opts.preset];
            this._frequency = p.frequency;
            this.type = p.type;
        } else {
            this._frequency = opts.frequency || 10;
        }

        if (opts.frequency) this._frequency = opts.frequency;
        if (opts.type) this.type = opts.type;

        this._ctx = null;
        this._running = false;
        this._panner = null;
        this._gain = null;
        this._interval = null;
        this._side = 'left'; // alternates left/right
        this._loadSettings();
    }

    /** Presets mapped to common focus states. */
    static get PRESETS() {
        return {
            theta: { frequency: 6, type: 'sine-pulse', label: 'Theta — Deep Focus', desc: '4-7 Hz: meditative flow, creative work' },
            alpha: { frequency: 10, type: 'soft-tick', label: 'Alpha — Alert Calm', desc: '8-12 Hz: ideal for reading, relaxed alertness' },
            beta:  { frequency: 18, type: 'soft-tick', label: 'Beta — Intense Focus', desc: '13-30 Hz: active concentration, problem-solving' },
            low:   { frequency: 2, type: 'sine-pulse', label: 'Slow — Breathing Pace', desc: '0.5-4 Hz: almost like a breathing guide' },
        };
    }

    /** Available tone types. */
    static get TYPES() {
        return [
            { id: 'soft-tick', label: 'Soft Tick', desc: 'Brief percussion, barely there' },
            { id: 'sine-pulse', label: 'Sine Pulse', desc: 'Smooth melodic pulse' },
            { id: 'noise-sweep', label: 'Noise Sweep', desc: 'Filtered noise, subtle' },
            { id: 'chime', label: 'Chime', desc: 'Short bell-like ping' },
        ];
    }

    /** Lazy-init AudioContext (must be called after user gesture). */
    _getCtx() {
        if (!this._ctx || this._ctx.state === 'closed') {
            this._ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (this._ctx.state === 'suspended') {
            this._ctx.resume();
        }
        return this._ctx;
    }

    /** Start bilateral stimulation. */
    start() {
        if (this._running) return;
        this._running = true;
        this._side = 'left';
        this._tick();
    }

    /** Stop and clean up. */
    stop() {
        this._running = false;
        if (this._interval) clearInterval(this._interval);
        this._interval = null;
        if (this._ctx && this._ctx.state !== 'closed') {
            this._ctx.close().catch(() => {});
            this._ctx = null;
        }
    }

    /** Pause (keep state but stop ticks). */
    pause() {
        this._running = false;
        if (this._interval) clearInterval(this._interval);
    }

    /** Resume from paused. */
    resume() {
        if (this._running) return;
        this._running = true;
        this._tick();
    }

    /** Set alternation frequency at runtime. */
    setFrequency(hz) {
        this._frequency = Math.max(0.5, Math.min(30, hz));
        // Restart the interval with new rate
        if (this._running) {
            if (this._interval) clearInterval(this._interval);
            this._tick();
        }
    }

    /** Set tone type at runtime. */
    setType(type) {
        this.type = type;
    }

    /** Change volume at runtime. */
    setVolume(vol) {
        this._volume = Math.min(vol, 0.2);
    }

    /** Apply a preset. */
    setPreset(name) {
        const p = BilateralStimulation.PRESETS[name];
        if (!p) return;
        this.setFrequency(p.frequency);
        this.setType(p.type);
    }

    get isRunning() { return this._running; }
    get frequency() { return this._frequency; }

    // ── Internal ──

    /**
     * Single tick: play tone on one side, switch sides for next.
     * The interval between ticks is 1/frequency divided by 2
     * (since one full cycle = left + right).
     */
    _tick() {
        if (!this._running) return;

        const ctx = this._getCtx();
        const now = ctx.currentTime;

        // Create short tone
        this._playTone(ctx, now, this._side);

        // Switch side for next tick
        this._side = this._side === 'left' ? 'right' : 'left';

        // Schedule next tick: half the cycle period
        const halfPeriod = (1 / this._frequency) * 1000 / 2;
        this._interval = setTimeout(() => this._tick(), halfPeriod);
    }

    /**
     * Play a short tone panned to one side.
     */
    _playTone(ctx, startTime, side) {
        const panValue = side === 'left' ? -0.8 : 0.8;
        const duration = Math.min(0.08, (1 / this._frequency) * 0.3); // 30% of half-cycle, max 80ms

        let source;

        switch (this.type) {
            case 'sine-pulse':
                source = this._makeSinePulse(ctx, duration);
                break;
            case 'noise-sweep':
                source = this._makeNoiseSweep(ctx, duration);
                break;
            case 'chime':
                source = this._makeChime(ctx, duration);
                break;
            case 'soft-tick':
            default:
                source = this._makeSoftTick(ctx, duration);
                break;
        }

        // Pan
        const panner = ctx.createStereoPanner();
        panner.pan.value = panValue;

        // Gain envelope: quick attack, quick decay
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(this._volume, startTime + 0.005);
        gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration);

        source.connect(panner);
        panner.connect(gain);
        gain.connect(ctx.destination);

        source.start(startTime);
        source.stop(startTime + duration + 0.01);
    }

    /** Soft percussive tick — noise burst with bandpass. */
    _makeSoftTick(ctx, duration) {
        const bufferSize = Math.floor(ctx.sampleRate * 0.05);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = (Math.random() * 2 - 1) * Math.exp(-i / (bufferSize * 0.3));
        }

        const source = ctx.createBufferSource();
        source.buffer = buffer;

        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.value = 1200; // soft midrange click
        filter.Q.value = 1.5;

        source.connect(filter);
        return { start: (t) => source.start(t), stop: (t) => source.stop(t), connect: (n) => filter.connect(n) };
    }

    /** Smooth sine pulse — pitched tone. */
    _makeSinePulse(ctx, duration) {
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = 440; // A4 — pleasant, not piercing

        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 800;
        filter.Q.value = 0.7;

        osc.connect(filter);
        return { start: (t) => osc.start(t), stop: (t) => osc.stop(t), connect: (n) => filter.connect(n) };
    }

    /** Filtered noise sweep — broadband noise with moving bandpass. */
    _makeNoiseSweep(ctx, duration) {
        const bufferSize = Math.floor(ctx.sampleRate * 0.1);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);
        for (let i = 0; i < bufferSize; i++) {
            data[i] = (Math.random() * 2 - 1) * 0.5;
        }

        const source = ctx.createBufferSource();
        source.buffer = buffer;

        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(600, ctx.currentTime);
        filter.frequency.linearRampToValueAtTime(2000, ctx.currentTime + duration);
        filter.Q.value = 2;

        source.connect(filter);
        return { start: (t) => source.start(t), stop: (t) => source.stop(t), connect: (n) => filter.connect(n) };
    }

    /** Short bell-like chime — two harmonics for pleasant ring. */
    _makeChime(ctx, duration) {
        const osc1 = ctx.createOscillator();
        osc1.type = 'sine';
        osc1.frequency.value = 880; // A5

        const osc2 = ctx.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.value = 1320; // E6 — fifth above

        const merger = ctx.createGain();
        merger.gain.value = 0.5;

        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.value = 2000;
        filter.Q.value = 0.5;

        osc1.connect(merger);
        osc2.connect(merger);
        merger.connect(filter);

        return {
            start: (t) => { osc1.start(t); osc2.start(t); },
            stop: (t) => { osc1.stop(t); osc2.stop(t); },
            connect: (n) => filter.connect(n),
        };
    }

    _saveSettings() {
        // Settings saved by the noise player component that wraps this
    }

    _loadSettings() {
        try {
            const saved = JSON.parse(localStorage.getItem('fixate-bilateral') || '{}');
            if (saved.frequency) this._frequency = saved.frequency;
            if (saved.type) this.type = saved.type;
            if (saved.volume !== undefined) this._volume = Math.min(saved.volume, 0.2);
        } catch (e) {}
    }
}
