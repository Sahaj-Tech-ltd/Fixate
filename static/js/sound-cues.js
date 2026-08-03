/**
 * Fixate Sound Cue Engine — DMN Disruption via Programmatic Audio
 *
 * Generates short (0.2-2s) attention-reset sounds using the Web Audio API.
 * No downloads, no copyright, works fully offline. Integrated with HyperfocusEngine.
 *
 * Research basis:
 *   - DMN (Default Mode Network) gets disrupted by unexpected auditory stimuli
 *   - Salience network fires → attention snaps back to task
 *   - Habituation is the enemy: same sound + same interval = useless within 3 exposures
 *   - Solution: randomized category, pitch, duration, interval; 14 distinct sound families
 *
 * Categories (14 total, all <2s):
 *   alert     — sharp sine sweep, attention-grabbing (0.5-1.5s)
 *   perc      — noise burst + low thump, drum-like (0.3-1s)
 *   glitch    — short frequency glitch, digital zap (0.2-0.8s)
 *   subtle    — soft bell/ping, gentle nudge for ADHD-I (1-2s)
 *   water     — filtered noise splash, droplet-like (0.5-1s)
 *   scrape    — harsh filtered noise scrape, jarring reset (0.3-1s)
 *   pop       — quick impulse with envelope, snap-like (0.2-0.6s)
 *   balloon   — realistic balloon pop with body resonance (0.3-0.8s)
 *   chord     — short piano/music chord, stacked harmonics (1.2-2s)
 *   pluck     — Karplus-Strong string pluck, guitar-like (0.4-1s)
 *   woodblock — percussive wooden hit, hollow body (0.2-0.5s)
 *   whoosh    — filtered noise sweep, air movement (0.5-1.2s)
 *   ding      — clean single sine ding, notification-like (0.3-0.7s)
 *   reverse   — rising reverse cymbal, tension build (0.8-1.5s)
 *
 * Usage:
 *   const cues = new SoundCueEngine({ volume: 0.3, categories: ['alert','perc','glitch'] });
 *   cues.play();                           // play random cue
 *   cues.playCategory('alert');            // play specific category
 *   cues.playRandom({ exclude: 'subtle' }); // play random but skip a category
 */

class SoundCueEngine {
    /**
     * @param {object} opts
     * @param {number} [opts.volume=0.25] — master volume 0.0-1.0 (HARD CAPPED at 0.3)
     * @param {string[]} [opts.categories] — enabled categories (default: all 24)
     * @param {boolean} [opts.haasEffect=true] — stereo widening for immersion
     * @param {function} [opts.onPlay] — callback before playing (e.g. pause TTS)
     */
    constructor(opts = {}) {
        this.volume = Math.min(opts.volume ?? 0.25, 0.3); // HARD CAP: 30% max
        this.enabledCategories = opts.categories || [
            'alert', 'perc', 'glitch', 'subtle', 'water', 'scrape', 'pop',
            'balloon', 'chord', 'pluck', 'woodblock', 'whoosh', 'ding', 'reverse',
            'doorbell', 'phone', 'airplane', 'cashreg', 'typewriter', 'camera',
            'drop', 'twinkle', 'buzz', 'glass',
        ];
        this.useHaas = opts.haasEffect !== false;
        this._onPlay = opts.onPlay || null;

        // Audio context (lazy init)
        this._ctx = null;
        this._lastCategory = null;
        this._playCount = 0;
    }

    /** Get or create AudioContext (must be called after user gesture). */
    _getCtx() {
        if (!this._ctx || this._ctx.state === 'closed') {
            this._ctx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (this._ctx.state === 'suspended') {
            this._ctx.resume();
        }
        return this._ctx;
    }

    /** Play a random cue from enabled categories. Avoids repeating the same category back-to-back. */
    play(opts = {}) {
        const exclude = opts.exclude || this._lastCategory;
        const pool = this.enabledCategories.filter(c => c !== exclude);
        if (pool.length === 0) {
            // All categories excluded — play any
            const cat = this.enabledCategories[Math.floor(Math.random() * this.enabledCategories.length)];
            this.playCategory(cat, opts);
            return;
        }
        const category = pool[Math.floor(Math.random() * pool.length)];
        this.playCategory(category, opts);
    }

    /** Play a specific category. */
    playCategory(category, opts = {}) {
        if (this._onPlay) this._onPlay(category);
        const ctx = this._getCtx();
        const volume = (opts.volume ?? this.volume) * this._masterVolume();
        this._lastCategory = category;
        this._playCount++;

        switch (category) {
            case 'alert':     this._playAlert(ctx, volume); break;
            case 'perc':      this._playPercussive(ctx, volume); break;
            case 'glitch':    this._playGlitch(ctx, volume); break;
            case 'subtle':    this._playSubtle(ctx, volume); break;
            case 'water':     this._playWater(ctx, volume); break;
            case 'scrape':    this._playScrape(ctx, volume); break;
            case 'pop':       this._playPop(ctx, volume); break;
            case 'balloon':   this._playBalloon(ctx, volume); break;
            case 'chord':     this._playChord(ctx, volume); break;
            case 'pluck':     this._playPluck(ctx, volume); break;
            case 'woodblock': this._playWoodblock(ctx, volume); break;
            case 'whoosh':    this._playWhoosh(ctx, volume); break;
            case 'ding':      this._playDing(ctx, volume); break;
            case 'reverse':   this._playReverse(ctx, volume); break;
            case 'doorbell':  this._playDoorbell(ctx, volume); break;
            case 'phone':     this._playPhone(ctx, volume); break;
            case 'airplane':  this._playAirplane(ctx, volume); break;
            case 'cashreg':   this._playCashReg(ctx, volume); break;
            case 'typewriter':this._playTypewriter(ctx, volume); break;
            case 'camera':    this._playCamera(ctx, volume); break;
            case 'drop':      this._playDrop(ctx, volume); break;
            case 'twinkle':   this._playTwinkle(ctx, volume); break;
            case 'buzz':      this._playBuzz(ctx, volume); break;
            case 'glass':     this._playGlass(ctx, volume); break;
        }
    }

    /**
     * Schedule a random cue to play at semi-random intervals.
     * Use this for "background attention maintenance" mode.
     *
     * @param {object} opts
     * @param {number} [opts.minInterval=90000] — minimum ms between cues (default 90s)
     * @param {number} [opts.maxInterval=300000] — maximum ms between cues (default 5min)
     * @param {function} [opts.onSchedule] — called with {category, nextMs}
     * @returns {object} — { stop: () => void }
     */
    schedule(opts = {}) {
        const minMs = opts.minInterval || 90000;
        const maxMs = opts.maxInterval || 300000;
        const onSchedule = opts.onSchedule || (() => {});

        let timeout;
        let stopped = false;

        const scheduleNext = () => {
            if (stopped) return;
            const delay = minMs + Math.random() * (maxMs - minMs);
            const nextCategory = this.enabledCategories[
                Math.floor(Math.random() * this.enabledCategories.length)
            ];
            onSchedule({ category: nextCategory, nextMs: Math.round(delay) });

            timeout = setTimeout(() => {
                if (stopped) return;
                this.playCategory(nextCategory);
                scheduleNext();
            }, delay);
        };

        scheduleNext();

        return {
            stop: () => {
                stopped = true;
                clearTimeout(timeout);
            },
        };
    }

    // ── Internal: Sound Generators ──

    /** Sharp sine sweep — 800Hz→1200Hz over 0.6-1.2s. Like a gentle alarm ping. */
    _playAlert(ctx, volume) {
        const duration = 0.5 + Math.random() * 0.7;
        const startFreq = 600 + Math.random() * 400;
        const endFreq = startFreq + 200 + Math.random() * 600;

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(startFreq, ctx.currentTime);
        osc.frequency.linearRampToValueAtTime(endFreq, ctx.currentTime + duration * 0.7);
        osc.frequency.linearRampToValueAtTime(endFreq * 0.8, ctx.currentTime + duration);

        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        this._stereo(osc, gain, ctx);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.05);
    }

    /** White noise burst with low-frequency thump — drum-like snap. */
    _playPercussive(ctx, volume) {
        const duration = 0.25 + Math.random() * 0.6;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            const env = Math.exp(-t * 8); // fast decay envelope
            data[i] = (Math.random() * 2 - 1) * env;
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        // Low thump underneath
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(80 + Math.random() * 60, ctx.currentTime);

        const noiseGain = ctx.createGain();
        noiseGain.gain.setValueAtTime(volume * 0.7, ctx.currentTime);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        const oscGain = ctx.createGain();
        oscGain.gain.setValueAtTime(volume * 0.5, ctx.currentTime);
        oscGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);

        const merger = this._stereo(noise, noiseGain, ctx);
        osc.connect(oscGain);
        oscGain.connect(merger);

        noise.start(ctx.currentTime);
        osc.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
        osc.stop(ctx.currentTime + 0.2);
    }

    /** Frequency glitch — rapid random oscillation, sounds like a digital zap. */
    _playGlitch(ctx, volume) {
        const duration = 0.15 + Math.random() * 0.5;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'square';

        // Rapid random frequency jumps
        const steps = Math.floor(3 + Math.random() * 8);
        for (let i = 0; i < steps; i++) {
            const t = ctx.currentTime + (i / steps) * duration;
            osc.frequency.setValueAtTime(200 + Math.random() * 2000, t);
        }

        gain.gain.setValueAtTime(volume * 0.6, ctx.currentTime);
        gain.gain.setValueAtTime(volume * 0.6, ctx.currentTime + duration * 0.5);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        this._stereo(osc, gain, ctx);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.05);
    }

    /** Soft bell-like ping — gentle nudge for sensory-sensitive / ADHD-I. */
    _playSubtle(ctx, volume) {
        const duration = 1.0 + Math.random() * 0.8;
        const baseFreq = 400 + Math.random() * 600;

        // Two slightly detuned sine waves for bell-like beating
        [baseFreq, baseFreq * 1.002].forEach(freq => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, ctx.currentTime);

            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(volume * 0.4, ctx.currentTime + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

            this._stereo(osc, gain, ctx);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + duration + 0.05);
        });
    }

    /** Filtered noise splash — sounds like a water droplet or splash. */
    _playWater(ctx, volume) {
        const duration = 0.4 + Math.random() * 0.5;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            const env = Math.exp(-t * 4) * Math.sin(t * 20); // rippling envelope
            data[i] = (Math.random() * 2 - 1) * env;
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        // Bandpass filter for splash character
        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(2000 + Math.random() * 3000, ctx.currentTime);
        filter.Q.setValueAtTime(0.5, ctx.currentTime);

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(volume * 0.5, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        noise.connect(filter);
        filter.connect(gain);
        this._stereoNode(gain, ctx);

        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Harsh filtered noise scrape — jarring attention reset. Like metal scrape or vinyl scratch. */
    _playScrape(ctx, volume) {
        const duration = 0.25 + Math.random() * 0.6;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            const env = Math.exp(-t * 3);
            // Add harsh harmonics
            data[i] = (Math.random() * 2 - 1) * env * (1 + Math.sin(t * 100) * 0.5);
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        // High shelf filter for brightness
        const filter = ctx.createBiquadFilter();
        filter.type = 'highshelf';
        filter.frequency.setValueAtTime(3000, ctx.currentTime);
        filter.gain.setValueAtTime(10, ctx.currentTime);

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(volume * 0.55, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        noise.connect(filter);
        filter.connect(gain);
        this._stereoNode(gain, ctx);

        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Quick impulse with envelope — balloon pop or finger snap. */
    _playPop(ctx, volume) {
        const duration = 0.15 + Math.random() * 0.35;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            // Very fast attack + quick decay
            const env = t < 0.01 ? t / 0.01 : Math.exp(-t * 20);
            data[i] = (Math.random() * 2 - 1) * env;
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(volume * 0.6, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        this._stereoNode(gain, ctx);
        noise.connect(gain);
        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Realistic balloon pop — noise burst shaped through a resonant bandpass filter
     *  to create the hollow body "pop" resonance. 0.3-0.8s. */
    _playBalloon(ctx, volume) {
        const duration = 0.25 + Math.random() * 0.5;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        // Body resonance frequency varies per balloon
        const bodyFreq = 200 + Math.random() * 300;

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            // Very fast attack (<5ms), then resonant decay
            const env = t < 0.005 ? t / 0.005 : Math.exp(-t * 8);
            // Add body resonance
            data[i] = (Math.random() * 2 - 1) * env * (1 + 0.6 * Math.sin(2 * Math.PI * bodyFreq * t));
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        filter.frequency.setValueAtTime(bodyFreq, ctx.currentTime);
        filter.Q.setValueAtTime(2 + Math.random() * 3, ctx.currentTime);

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(volume * 0.7, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        noise.connect(filter);
        filter.connect(gain);
        this._stereoNode(gain, ctx);
        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Short piano-like chord — stacked sine waves at harmonic intervals.
     *  Root + major third + fifth, each with its own decay. 1.2-2s. */
    _playChord(ctx, volume) {
        const duration = 1.0 + Math.random() * 0.8;

        // Random root note between C3 and C5
        const rootFreq = 130 + Math.random() * 400;
        // Chord types: major, minor, sus4, maj7
        const chordTypes = [
            [1, 5/4, 3/2],          // major
            [1, 6/5, 3/2],          // minor
            [1, 4/3, 3/2],          // sus4
            [1, 5/4, 3/2, 15/8],    // maj7
        ];
        const ratios = chordTypes[Math.floor(Math.random() * chordTypes.length)];

        ratios.forEach((ratio, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            // Mix waveform for richer tone
            osc.type = ['sine', 'triangle', 'sine', 'triangle'][i % 4];
            osc.frequency.setValueAtTime(rootFreq * ratio, ctx.currentTime);

            // Staggered attack like a strum
            const attackTime = 0.01 + i * 0.03;
            const noteVol = volume * 0.25 * (1 - i * 0.15);
            gain.gain.setValueAtTime(0, ctx.currentTime);
            gain.gain.linearRampToValueAtTime(noteVol, ctx.currentTime + attackTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

            this._stereo(osc, gain, ctx);
            osc.start(ctx.currentTime);
            osc.stop(ctx.currentTime + duration + 0.05);
        });
    }

    /** Karplus-Strong string pluck — sounds like a guitar or harp string.
     *  Uses a short delay line with feedback for physical modeling. 0.4-1s. */
    _playPluck(ctx, volume) {
        const freq = 150 + Math.random() * 500;
        const duration = 0.35 + Math.random() * 0.5;
        const delayTime = 1 / freq;
        const sampleRate = ctx.sampleRate;

        // Create initial noise burst
        const burstLen = Math.floor(sampleRate * delayTime);
        const burst = ctx.createBuffer(1, burstLen, sampleRate);
        const burstData = burst.getChannelData(0);
        for (let i = 0; i < burstLen; i++) {
            burstData[i] = (Math.random() * 2 - 1) * (1 - i / burstLen);
        }

        const burstSrc = ctx.createBufferSource();
        burstSrc.buffer = burst;

        // Delay line with feedback (Karplus-Strong core)
        const delay = ctx.createDelay(delayTime * 2);
        delay.delayTime.value = delayTime;

        const feedback = ctx.createGain();
        feedback.gain.value = 0.85 + Math.random() * 0.1; // slight variation

        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(freq * 3, ctx.currentTime);

        const outGain = ctx.createGain();
        outGain.gain.setValueAtTime(volume * 0.4, ctx.currentTime);

        // Route: burst → delay → filter → feedback → delay (loop)
        //        delay → outGain → destination
        burstSrc.connect(delay);
        delay.connect(filter);
        filter.connect(feedback);
        feedback.connect(delay);
        filter.connect(outGain);

        this._stereoNode(outGain, ctx);
        burstSrc.start(ctx.currentTime);
        burstSrc.stop(ctx.currentTime + delayTime);

        // Kill after duration
        setTimeout(() => {
            feedback.gain.value = 0;
        }, duration * 1000);
    }

    /** Wooden percussive hit — short, dry, resonant body. Sounds like a woodblock or claves. 0.2-0.5s. */
    _playWoodblock(ctx, volume) {
        const duration = 0.15 + Math.random() * 0.3;
        const bodyFreq = 600 + Math.random() * 800;
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gain = ctx.createGain();

        // Two slightly detuned oscillators for woody texture
        osc1.type = 'triangle';
        osc2.type = 'square';
        osc1.frequency.setValueAtTime(bodyFreq, ctx.currentTime);
        osc2.frequency.setValueAtTime(bodyFreq * 0.998, ctx.currentTime);

        // Very fast decay — wood doesn't sustain
        gain.gain.setValueAtTime(volume * 0.5, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration * 0.3);
        gain.gain.setValueAtTime(0.001, ctx.currentTime + duration);

        const merger = ctx.createChannelMerger(2);
        osc1.connect(gain);
        osc2.connect(gain);
        const pan = (Math.random() - 0.5) * 0.6;
        const lGain = ctx.createGain(); lGain.gain.value = Math.max(0, 1 - pan);
        const rGain = ctx.createGain(); rGain.gain.value = Math.max(0, 1 + pan);
        gain.connect(lGain); gain.connect(rGain);
        lGain.connect(merger, 0, 0); rGain.connect(merger, 0, 1);
        merger.connect(ctx.destination);

        osc1.start(ctx.currentTime);
        osc2.start(ctx.currentTime);
        osc1.stop(ctx.currentTime + duration + 0.05);
        osc2.stop(ctx.currentTime + duration + 0.05);
    }

    /** Air whoosh — filtered noise sweep, sounds like moving air or a quick exhale. 0.5-1.2s. */
    _playWhoosh(ctx, volume) {
        const duration = 0.4 + Math.random() * 0.7;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            // Smooth rise and fall
            const env = t < duration * 0.2 ? t / (duration * 0.2) : Math.exp(-(t - duration * 0.2) * 4);
            data[i] = (Math.random() * 2 - 1) * env;
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        // Bandpass filter that sweeps down (like air passing)
        const filter = ctx.createBiquadFilter();
        filter.type = 'bandpass';
        const startFreq = 1000 + Math.random() * 3000;
        const endFreq = 200 + Math.random() * 300;
        filter.frequency.setValueAtTime(startFreq, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(endFreq, ctx.currentTime + duration);
        filter.Q.setValueAtTime(0.3, ctx.currentTime);

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(volume * 0.4, ctx.currentTime + duration * 0.15);
        gain.gain.linearRampToValueAtTime(volume * 0.4, ctx.currentTime + duration * 0.6);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        noise.connect(filter);
        filter.connect(gain);
        this._stereoNode(gain, ctx);
        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Clean sine ding — like a notification or elevator chime. Single clear tone. 0.3-0.7s. */
    _playDing(ctx, volume) {
        const duration = 0.25 + Math.random() * 0.4;
        const freq = 600 + Math.random() * 800;

        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);

        // Bell-like envelope: quick attack, medium decay
        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(volume * 0.5, ctx.currentTime + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        // Add a slight overtone for brightness
        const overtone = ctx.createOscillator();
        overtone.type = 'sine';
        overtone.frequency.setValueAtTime(freq * 2.5, ctx.currentTime);
        const overtoneGain = ctx.createGain();
        overtoneGain.gain.setValueAtTime(0, ctx.currentTime);
        overtoneGain.gain.linearRampToValueAtTime(volume * 0.15, ctx.currentTime + 0.01);
        overtoneGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration * 0.5);

        const merger = ctx.createChannelMerger(2);
        osc.connect(gain);
        overtone.connect(overtoneGain);
        const pan = (Math.random() - 0.5) * 0.6;
        const lG = ctx.createGain(); lG.gain.value = Math.max(0, 1 - pan);
        const rG = ctx.createGain(); rG.gain.value = Math.max(0, 1 + pan);
        gain.connect(lG); gain.connect(rG);
        overtoneGain.connect(lG); overtoneGain.connect(rG);
        lG.connect(merger, 0, 0); rG.connect(merger, 0, 1);
        merger.connect(ctx.destination);

        osc.start(ctx.currentTime);
        overtone.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.05);
        overtone.stop(ctx.currentTime + duration + 0.05);
    }

    /** Reverse cymbal — rising filtered noise, builds tension. Like a reverse crash.
     *  Great as an "attention build" before a reward. 0.8-1.5s. */
    _playReverse(ctx, volume) {
        const duration = 0.7 + Math.random() * 0.7;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            // Rising envelope (reverse of normal decay)
            const env = Math.pow(t / duration, 2);
            data[i] = (Math.random() * 2 - 1) * env;
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        // Highpass filter sweep up — classic reverse cymbal effect
        const filter = ctx.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.setValueAtTime(200, ctx.currentTime);
        filter.frequency.exponentialRampToValueAtTime(8000, ctx.currentTime + duration);

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0, ctx.currentTime);
        gain.gain.linearRampToValueAtTime(volume * 0.5, ctx.currentTime + duration * 0.7);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

        noise.connect(filter);
        filter.connect(gain);
        this._stereoNode(gain, ctx);
        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Doorbell — two alternating tones (ding-dong). Classic house doorbell. 1-2s. */
    _playDoorbell(ctx, volume) {
        const freq1 = 700 + Math.random() * 200;
        const freq2 = freq1 * 0.75; // lower second tone
        const noteLen = 0.2 + Math.random() * 0.3;

        [freq1, freq2].forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, ctx.currentTime);
            const start = ctx.currentTime + i * noteLen;
            gain.gain.setValueAtTime(0, start);
            gain.gain.linearRampToValueAtTime(volume * 0.4, start + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.001, start + noteLen);
            this._stereo(osc, gain, ctx);
            osc.start(start);
            osc.stop(start + noteLen + 0.05);
        });
    }

    /** Old-school phone ring — two alternating high tones (classic ring-ring). 1-2s. */
    _playPhone(ctx, volume) {
        const freq = 800 + Math.random() * 200;
        const ringLen = 0.25;
        const pauseLen = 0.15;
        const rings = 2 + Math.floor(Math.random() * 2);

        for (let i = 0; i < rings; i++) {
            const start = ctx.currentTime + i * (ringLen + pauseLen);
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(freq, start);
            gain.gain.setValueAtTime(0, start);
            gain.gain.linearRampToValueAtTime(volume * 0.25, start + 0.01);
            gain.gain.linearRampToValueAtTime(volume * 0.25, start + ringLen * 0.5);
            gain.gain.exponentialRampToValueAtTime(0.001, start + ringLen);
            this._stereo(osc, gain, ctx);
            osc.start(start);
            osc.stop(start + ringLen + 0.05);
        }
    }

    /** Airplane cabin chime — the classic "bing-bong" you hear on flights. 0.8-1.5s. */
    _playAirplane(ctx, volume) {
        const notes = [587, 784]; // D5, G5 — classic airplane chime
        notes.forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, ctx.currentTime);
            const start = ctx.currentTime + i * 0.3;
            gain.gain.setValueAtTime(0, start);
            gain.gain.linearRampToValueAtTime(volume * 0.3, start + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.001, start + 0.4);
            this._stereo(osc, gain, ctx);
            osc.start(start);
            osc.stop(start + 0.45);
        });
    }

    /** Cash register / shop bell — the classic "cha-ching" coin sound. 0.5-1s. */
    _playCashReg(ctx, volume) {
        const baseFreq = 1200 + Math.random() * 600;
        const numTinks = 3 + Math.floor(Math.random() * 3);

        for (let i = 0; i < numTinks; i++) {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(baseFreq * (0.9 + i * 0.15), ctx.currentTime);
            const start = ctx.currentTime + i * 0.06;
            gain.gain.setValueAtTime(0, start);
            gain.gain.linearRampToValueAtTime(volume * 0.3, start + 0.005);
            gain.gain.exponentialRampToValueAtTime(0.001, start + 0.15);
            this._stereo(osc, gain, ctx);
            osc.start(start);
            osc.stop(start + 0.2);
        }
    }

    /** Typewriter key clack — sharp mechanical impact. 0.2-0.5s. */
    _playTypewriter(ctx, volume) {
        const duration = 0.1 + Math.random() * 0.3;
        const bufferSize = Math.floor(ctx.sampleRate * duration);
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        for (let i = 0; i < bufferSize; i++) {
            const t = i / ctx.sampleRate;
            const env = Math.exp(-t * 30);
            data[i] = (Math.random() * 2 - 1) * env;
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;
        const filter = ctx.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.setValueAtTime(2000 + Math.random() * 1000, ctx.currentTime);
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(volume * 0.35, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        noise.connect(filter);
        filter.connect(gain);
        this._stereoNode(gain, ctx);
        noise.start(ctx.currentTime);
        noise.stop(ctx.currentTime + duration + 0.05);
    }

    /** Camera shutter — short mechanical click-whirr. 0.3-0.6s. */
    _playCamera(ctx, volume) {
        // First click
        const osc1 = ctx.createOscillator();
        const g1 = ctx.createGain();
        osc1.type = 'square';
        osc1.frequency.setValueAtTime(200, ctx.currentTime);
        g1.gain.setValueAtTime(volume * 0.3, ctx.currentTime);
        g1.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
        this._stereo(osc1, g1, ctx);
        osc1.start(ctx.currentTime);
        osc1.stop(ctx.currentTime + 0.1);

        // Whirr sound after
        const duration = 0.2 + Math.random() * 0.2;
        const bufSize = Math.floor(ctx.sampleRate * duration);
        const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
        const bufData = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) {
            const t = i / ctx.sampleRate;
            bufData[i] = (Math.random() * 2 - 1) * Math.exp(-t * 15);
        }
        const whirr = ctx.createBufferSource();
        whirr.buffer = buf;
        const g2 = ctx.createGain();
        g2.gain.setValueAtTime(volume * 0.2, ctx.currentTime + 0.05);
        g2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05 + duration);
        whirr.connect(g2);
        this._stereoNode(g2, ctx);
        whirr.start(ctx.currentTime + 0.05);
        whirr.stop(ctx.currentTime + 0.05 + duration + 0.05);
    }

    /** Deep water droplet — low-pitched resonant plop. 0.4-0.8s. */
    _playDrop(ctx, volume) {
        const freq = 200 + Math.random() * 200;
        const duration = 0.3 + Math.random() * 0.4;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq * 1.5, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(freq, ctx.currentTime + 0.05);
        gain.gain.setValueAtTime(volume * 0.4, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        this._stereo(osc, gain, ctx);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.05);
    }

    /** Magical twinkle — ascending sequence of short bell tones. 1-2s. */
    _playTwinkle(ctx, volume) {
        const baseFreq = 500 + Math.random() * 400;
        const notes = [1, 1.25, 1.5, 2]; // ascending arpeggio
        notes.forEach((ratio, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(baseFreq * ratio, ctx.currentTime);
            const start = ctx.currentTime + i * 0.12;
            gain.gain.setValueAtTime(0, start);
            gain.gain.linearRampToValueAtTime(volume * 0.25, start + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.001, start + 0.25);
            this._stereo(osc, gain, ctx);
            osc.start(start);
            osc.stop(start + 0.3);
        });
    }

    /** Electric buzzer — harsh square wave, like a game show wrong answer. 0.3-0.7s. */
    _playBuzz(ctx, volume) {
        const duration = 0.2 + Math.random() * 0.4;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'square';
        osc.frequency.setValueAtTime(80 + Math.random() * 60, ctx.currentTime);
        gain.gain.setValueAtTime(volume * 0.25, ctx.currentTime);
        gain.gain.setValueAtTime(volume * 0.25, ctx.currentTime + duration * 0.7);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        this._stereo(osc, gain, ctx);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.05);
    }

    /** Wine glass ping — resonant high-pitched ring, like tapping a crystal glass. 1-2s. */
    _playGlass(ctx, volume) {
        const freq = 1000 + Math.random() * 800;
        const duration = 1.0 + Math.random() * 0.8;
        const osc = ctx.createOscillator();
        const overtone = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        overtone.type = 'sine';
        osc.frequency.setValueAtTime(freq, ctx.currentTime);
        overtone.frequency.setValueAtTime(freq * 2.01, ctx.currentTime);
        gain.gain.setValueAtTime(volume * 0.35, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        const overtoneGain = ctx.createGain();
        overtoneGain.gain.setValueAtTime(volume * 0.15, ctx.currentTime);
        overtoneGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration * 0.5);
        const merger = ctx.createChannelMerger(2);
        osc.connect(gain); overtone.connect(overtoneGain);
        const pan = (Math.random() - 0.5) * 0.6;
        const l = ctx.createGain(); l.gain.value = Math.max(0, 1 - pan);
        const r = ctx.createGain(); r.gain.value = Math.max(0, 1 + pan);
        gain.connect(l); gain.connect(r);
        overtoneGain.connect(l); overtoneGain.connect(r);
        l.connect(merger, 0, 0); r.connect(merger, 0, 1);
        merger.connect(ctx.destination);
        osc.start(ctx.currentTime); overtone.start(ctx.currentTime);
        osc.stop(ctx.currentTime + duration + 0.05);
        overtone.stop(ctx.currentTime + duration + 0.05);
    }

    // ── Internal: Stereo / Haas Effect ──

    /** Apply Haas-effect stereo widening. Randomizes pan for variety. */
    _stereo(source, gain, ctx) {
        const merger = ctx.createChannelMerger(2);
        const splitter = ctx.createChannelSplitter(2);

        source.connect(gain);

        const pan = (Math.random() - 0.5) * 0.8; // random pan per cue
        const leftGain = ctx.createGain();
        const rightGain = ctx.createGain();
        leftGain.gain.value = Math.max(0, 1 - pan);
        rightGain.gain.value = Math.max(0, 1 + pan);

        gain.connect(leftGain);
        gain.connect(rightGain);

        if (this.useHaas) {
            // Add slight delay to one channel for spatial widening
            const delay = ctx.createDelay(0.03);
            delay.delayTime.value = 0.005 + Math.random() * 0.015;
            gain.connect(delay);
            delay.connect(Math.random() > 0.5 ? leftGain : rightGain);
        }

        leftGain.connect(merger, 0, 0);
        rightGain.connect(merger, 0, 1);
        merger.connect(ctx.destination);

        return merger;
    }

    /** Simplified stereo connection for already-connected node chains. */
    _stereoNode(node, ctx) {
        const merger = ctx.createChannelMerger(2);
        const pan = (Math.random() - 0.5) * 0.8;
        const leftGain = ctx.createGain();
        const rightGain = ctx.createGain();
        leftGain.gain.value = Math.max(0, 1 - pan);
        rightGain.gain.value = Math.max(0, 1 + pan);

        node.connect(leftGain);
        node.connect(rightGain);
        leftGain.connect(merger, 0, 0);
        rightGain.connect(merger, 0, 1);
        merger.connect(ctx.destination);
    }

    /** Slight random volume variation to prevent identical-sounding cues. */
    _masterVolume() {
        return 0.85 + Math.random() * 0.3;
    }

    /** Clean up. */
    destroy() {
        if (this._ctx) {
            this._ctx.close();
            this._ctx = null;
        }
    }
}

// ── Preset Mixes ──

SoundCueEngine.PRESETS = {
    /** All 24 categories — maximum variety, minimal habituation (~40+ distinct sounds with variation). */
    balanced: {
        categories: ['alert', 'perc', 'glitch', 'subtle', 'water', 'scrape', 'pop',
                     'balloon', 'chord', 'pluck', 'woodblock', 'whoosh', 'ding', 'reverse',
                     'doorbell', 'phone', 'airplane', 'cashreg', 'typewriter', 'camera',
                     'drop', 'twinkle', 'buzz', 'glass'],
        volume: 0.25,
    },
    /** ADHD-inattentive friendly — avoids harsh/alarming sounds. */
    gentle: {
        categories: ['subtle', 'water', 'ding', 'chord', 'pluck', 'whoosh'],
        volume: 0.18,
    },
    /** Maximum disruption — all aggressive sounds at higher volume. */
    intense: {
        categories: ['alert', 'perc', 'glitch', 'scrape', 'pop', 'balloon', 'woodblock'],
        volume: 0.35,
    },
    /** Minimal — only the gentlest sounds for sensory-sensitive users. */
    minimal: {
        categories: ['subtle', 'water', 'ding'],
        volume: 0.12,
    },
    /** Musical — chord, pluck, ding, woodblock. Feels like instruments. */
    musical: {
        categories: ['chord', 'pluck', 'woodblock', 'ding', 'subtle'],
        volume: 0.28,
    },
};
