/**
 * Fixate Noise Generator — Standalone Web Audio API noise module.
 *
 * Three noise types (research-backed):
 *   - White:  Equal energy at all frequencies. Most studied for ADHD (g=0.249).
 *   - Pink:   -3 dB/octave. Rain-like. Good for sustained attention.
 *   - Brown:  -6 dB/octave. Deep rumble. Calming, masking.
 *
 * Audio chain:
 *   source[type] → gainNode[type] → masterGainNode → destination
 *
 * Design:
 *   - Only ONE noise type plays at a time (selecting a new one fades out the old).
 *   - Per-type volume sliders + master noise volume.
 *   - AudioContext created lazily on first user gesture.
 *   - Coexists with other audio (YouTube mixer, Spotify, etc.) — shares the
 *     same AudioContext.destination but is completely independent.
 *   - Zero dependencies, vanilla JS.
 *
 * Usage:
 *   NoiseGenerator.init();
 *   NoiseGenerator.play('pink');
 *   NoiseGenerator.setVolume('pink', 0.6);
 *   NoiseGenerator.setMasterVolume(0.8);
 *   NoiseGenerator.play('brown');  // fades out pink, starts brown
 *   NoiseGenerator.stop();
 *   NoiseGenerator.getActive();    // { type: 'brown', volume: 0.5, masterVolume: 0.8 }
 */

var NoiseGenerator = (function() {
    'use strict';

    // ── Private state ──
    var _ctx = null;            // AudioContext (lazy)
    var _masterGain = null;     // Master GainNode
    var _activeType = null;     // Currently playing noise type string
    var _sources = {};          // { white: { source, gain, buffer }, ... }
    var _volumes = {            // Per-type volume (0..1)
        white: 0.5,
        pink:  0.5,
        brown: 0.5
    };
    var _masterVolume = 0.7;    // Master noise volume (0..1)
    var _isPlaying = false;
    var _fadeMs = 300;          // Crossfade duration in ms

    // ── Noise buffer generation ──

    /**
     * Generate a looping noise buffer for the given type.
     * @param {string} type - 'white', 'pink', or 'brown'
     * @returns {AudioBuffer}
     */
    function _generateBuffer(type) {
        var sampleRate = _ctx.sampleRate;
        var duration = 2; // 2 seconds, looped
        var length = sampleRate * duration;
        var buffer = _ctx.createBuffer(1, length, sampleRate);
        var data = buffer.getChannelData(0);
        var i;

        switch (type) {
        case 'white':
            for (i = 0; i < length; i++) {
                data[i] = Math.random() * 2 - 1;
            }
            break;

        case 'pink':
            // Paul Kellett's refined method (7-pole filter)
            var b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
            for (i = 0; i < length; i++) {
                var white = Math.random() * 2 - 1;
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
            // Brownian noise: integrate white noise with leaky integrator
            var last = 0;
            for (i = 0; i < length; i++) {
                var w = Math.random() * 2 - 1;
                last = (last + (0.02 * w)) / 1.02;
                data[i] = last * 3.5; // Normalize
            }
            break;

        default:
            // Fallback to white
            for (i = 0; i < length; i++) {
                data[i] = Math.random() * 2 - 1;
            }
            break;
        }

        return buffer;
    }

    // ── Gain ramp helper ──

    /**
     * Smoothly ramp a GainNode's value over durationMs.
     * @param {GainNode} gainNode
     * @param {number} targetValue
     * @param {number} durationMs
     */
    function _rampGain(gainNode, targetValue, durationMs) {
        if (!gainNode || !_ctx) return;
        var now = _ctx.currentTime;
        gainNode.gain.cancelScheduledValues(now);
        gainNode.gain.setValueAtTime(gainNode.gain.value, now);
        gainNode.gain.linearRampToValueAtTime(
            targetValue,
            now + durationMs / 1000
        );
    }

    // ── Ensure AudioContext ──

    /**
     * Create the AudioContext if it doesn't exist.
     * Must be called from a user gesture handler for browsers that block autoplay.
     */
    function _ensureContext() {
        if (_ctx) {
            if (_ctx.state === 'suspended') _ctx.resume();
            return;
        }
        _ctx = new (window.AudioContext || window.webkitAudioContext)();

        // Master gain node — all noise types route through this
        _masterGain = _ctx.createGain();
        _masterGain.gain.value = 0; // Start silent; fade in on play()
        _masterGain.connect(_ctx.destination);
    }

    /**
     * Ensure a source + gain chain exists for a specific noise type.
     * Does NOT start playback — just prepares the nodes.
     * @param {string} type
     */
    function _ensureTypeNodes(type) {
        if (_sources[type]) return;

        var buffer = _generateBuffer(type);
        var gainNode = _ctx.createGain();
        gainNode.gain.value = 0; // Silent until explicitly played
        gainNode.connect(_masterGain);

        _sources[type] = {
            source: null,   // AudioBufferSourceNode (created on play)
            gain: gainNode,
            buffer: buffer
        };
    }

    /**
     * Start an AudioBufferSourceNode for the given type.
     * @param {string} type
     */
    function _startSource(type) {
        var entry = _sources[type];
        if (!entry) return;

        // Stop existing source if any
        if (entry.source) {
            try { entry.source.stop(); } catch(e) {}
            try { entry.source.disconnect(); } catch(e) {}
            entry.source = null;
        }

        var source = _ctx.createBufferSource();
        source.buffer = entry.buffer;
        source.loop = true;
        source.connect(entry.gain);
        source.start(0);
        entry.source = source;
    }

    /**
     * Stop and disconnect the source for a given type.
     * @param {string} type
     */
    function _stopSource(type) {
        var entry = _sources[type];
        if (!entry) return;

        if (entry.source) {
            try { entry.source.stop(); } catch(e) {}
            try { entry.source.disconnect(); } catch(e) {}
            entry.source = null;
        }
    }

    // ── Public API ──

    return {
        /**
         * Initialize the noise generator. Safe to call multiple times.
         * Creates AudioContext on first call (must be from user gesture).
         */
        init: function() {
            _ensureContext();
        },

        /**
         * Play a noise type. If another type is active, crossfades to the new one.
         * @param {string} type - 'white', 'pink', or 'brown'
         * @param {number} [fadeMs=300] - Crossfade duration in milliseconds
         */
        play: function(type, fadeMs) {
            if (['white', 'pink', 'brown'].indexOf(type) === -1) {
                console.warn('NoiseGenerator: unknown type "' + type + '"');
                return;
            }

            _ensureContext();
            _ensureTypeNodes(type);

            var fade = (typeof fadeMs === 'number') ? fadeMs : _fadeMs;
            var targetVol = _volumes[type];

            if (_activeType === type) {
                // Already playing this type — just make sure it's audible
                _rampGain(_sources[type].gain, targetVol, fade);
                if (!_isPlaying) {
                    // Source was stopped, restart
                    _startSource(type);
                    _rampGain(_masterGain, _masterVolume, fade);
                }
                _isPlaying = true;
                return;
            }

            // Fade out the old type
            if (_activeType && _sources[_activeType]) {
                _rampGain(_sources[_activeType].gain, 0, fade);
                // Stop source after fade completes
                (function(oldType) {
                    setTimeout(function() {
                        _stopSource(oldType);
                    }, fade + 50);
                })(_activeType);
            }

            // Start the new type
            _startSource(type);
            _rampGain(_sources[type].gain, targetVol, fade);
            _rampGain(_masterGain, _masterVolume, fade);

            _activeType = type;
            _isPlaying = true;
        },

        /**
         * Stop all noise playback with a fade-out.
         * @param {number} [fadeMs=300] - Fade-out duration
         */
        stop: function(fadeMs) {
            if (!_isPlaying || !_activeType) return;

            var fade = (typeof fadeMs === 'number') ? fadeMs : _fadeMs;

            // Fade master to 0
            _rampGain(_masterGain, 0, fade);

            // Stop source after fade
            var typeToStop = _activeType;
            setTimeout(function() {
                _stopSource(typeToStop);
                // Reset per-type gain to 0
                if (_sources[typeToStop]) {
                    _sources[typeToStop].gain.gain.value = 0;
                }
            }, fade + 50);

            _activeType = null;
            _isPlaying = false;
        },

        /**
         * Pause noise (suspend AudioContext — also pauses all other noise).
         * Prefer stop() for just stopping noise without affecting context.
         */
        pause: function() {
            if (_ctx && _ctx.state === 'running') _ctx.suspend();
        },

        /**
         * Resume noise (resume AudioContext).
         */
        resume: function() {
            if (_ctx && _ctx.state === 'suspended') _ctx.resume();
        },

        /**
         * Set volume for a specific noise type.
         * @param {string} type - 'white', 'pink', or 'brown'
         * @param {number} vol - Volume 0.0 to 1.0
         * @param {number} [rampMs=100] - Ramp duration
         */
        setVolume: function(type, vol, rampMs) {
            if (['white', 'pink', 'brown'].indexOf(type) === -1) return;

            vol = Math.max(0, Math.min(1, vol));
            _volumes[type] = vol;

            // If this type is currently active, apply immediately
            if (_isPlaying && _activeType === type && _sources[type]) {
                var ramp = (typeof rampMs === 'number') ? rampMs : 100;
                _rampGain(_sources[type].gain, vol, ramp);
            }
        },

        /**
         * Set the master noise volume (affects all noise types equally).
         * @param {number} vol - Volume 0.0 to 1.0
         * @param {number} [rampMs=100] - Ramp duration
         */
        setMasterVolume: function(vol, rampMs) {
            vol = Math.max(0, Math.min(1, vol));
            _masterVolume = vol;

            if (_masterGain && _ctx) {
                var ramp = (typeof rampMs === 'number') ? rampMs : 100;
                _rampGain(_masterGain, _isPlaying ? vol : 0, ramp);
            }
        },

        /**
         * Get current state.
         * @returns {{ type: string|null, volume: number, volumes: object, masterVolume: number, isPlaying: boolean }}
         */
        getActive: function() {
            return {
                type: _activeType,
                volume: _activeType ? _volumes[_activeType] : 0,
                volumes: {
                    white: _volumes.white,
                    pink:  _volumes.pink,
                    brown: _volumes.brown
                },
                masterVolume: _masterVolume,
                isPlaying: _isPlaying
            };
        },

        /**
         * Check if Web Audio API is supported.
         * @returns {boolean}
         */
        isSupported: function() {
            return !!(window.AudioContext || window.webkitAudioContext);
        },

        /**
         * Destroy the noise generator, release all resources.
         */
        destroy: function() {
            // Stop all sources
            ['white', 'pink', 'brown'].forEach(function(type) {
                _stopSource(type);
            });

            // Disconnect master
            if (_masterGain) {
                try { _masterGain.disconnect(); } catch(e) {}
                _masterGain = null;
            }

            // Close context
            if (_ctx) {
                try { _ctx.close(); } catch(e) {}
                _ctx = null;
            }

            _sources = {};
            _activeType = null;
            _isPlaying = false;
        },

        /**
         * Get the internal AudioContext (for advanced integration).
         * Returns null if not initialized.
         * @returns {AudioContext|null}
         */
        getContext: function() {
            return _ctx;
        }
    };
})();
