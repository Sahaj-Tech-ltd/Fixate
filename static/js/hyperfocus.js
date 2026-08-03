/**
 * Fixate Hyperfocus Engine — sprint timer, variable rewards,
 * micro-nudges, comprehension pop-ins, and DMN disruption.
 *
 * Grounded in ADHD neuroscience research:
 *   - DMN intrusion window: 5-15 seconds (disrupt before it starts)
 *   - Stimulants work through REWARD, not attention (build pharmacologically equivalent loop)
 *   - Variable-ratio schedules sustain dopamine better than fixed
 *   - Stochastic resonance: low-level noise improves signal detection in under-aroused brains
 *   - Speed-drop detection: fMRI can predict lapses 20s in advance; speed drops are the proxy
 *
 * Usage:
 *   const hf = new HyperfocusEngine({
 *       onReward: (reward) => { ... },
 *       onNudge: () => { ... },
 *       onComprehensionCheck: (check) => { ... },
 *       onDMNBurst: () => { ... },              // stochastic resonance burst
 *       onSprintTick: (remaining) => { ... },
 *       onSprintEnd: () => { ... },
 *   });
 *   hf.startSprint(25);
 *   hf.onWord(42);           // call on every word advance
 *   hf.onPause(); hf.onResume();
 */

const COMPLIMENTS = [
    "You're locked in 🔥",
    "Flow state activated ⚡",
    "ADHD who? 🧠",
    "Neurons firing on all cylinders",
    "This is your brain on Fixate",
    "Keep that streak alive 🏆",
    "Hyperfocus: engaged",
    "Page by page, you're crushing it",
    "Dopamine delivery 📦",
    "You make this look easy",
];

const XP_EMOJI = ['⭐', '💎', '🌟', '✨', '🔥', '⚡', '🧠', '🏆'];

// ── Comprehension Check Varieties ──
// Rotate through these so ADHD brains don't get bored.
const CHECK_VARIETIES = [
    {
        type: 'tap',
        question: "Tap anywhere to continue — quick checkpoint!",
        resolveOn: 'click',
    },
    {
        type: 'yes_no',
        question: "Still with us? Got the last section?",
        options: ['Got it ✓', 'Re-reading...'],
    },
    {
        type: 'emoji',
        question: "How's your focus right now?",
        options: ['🔥 Locked in', '😐 Okay', '😴 Fading', '💨 Gone'],
    },
    {
        type: 'breathe',
        question: "Take one deep breath. In... and out. Ready?",
        options: ['Continue'],
    },
    {
        type: 'mental',
        question: "Quick: summarize the last paragraph in 3 words in your head. Done?",
        options: ['Done ✓', 'Need to re-read'],
    },
    {
        type: 'tap',
        question: "Comprehension checkpoint. Tap to keep going.",
        resolveOn: 'click',
    },
];

class HyperfocusEngine {
    /**
     * @param {object} opts
     * @param {function} opts.onReward - called with {type, text, xp}
     * @param {function} opts.onNudge - called when micro-nudge should fire
     * @param {function} opts.onComprehensionCheck - called with {question}
     * @param {function} opts.onSprintTick - called with {remaining: seconds, total: seconds}
     * @param {function} opts.onSprintEnd - called when sprint completes
     */
    constructor(opts = {}) {
        this.onReward = opts.onReward || (() => {});
        this.onNudge = opts.onNudge || (() => {});
        this.onComprehensionCheck = opts.onComprehensionCheck || (() => {});
        this.onDMNBurst = opts.onDMNBurst || (() => {});
        this.onSprintTick = opts.onSprintTick || (() => {});
        this.onSprintEnd = opts.onSprintEnd || (() => {});

        // Sprint state
        this.sprintMinutes = 25;
        this.sprintStartTime = null;
        this.sprintEndTime = null;
        this.sprintActive = false;
        this.sprintPaused = false;
        this.pauseStartTime = null;
        this.totalPausedMs = 0;
        this._tickInterval = null;

        // Reward schedule (variable ratio)
        this.wordCount = 0;
        this.nextRewardAt = this._nextRewardWord();
        this.rewardsGiven = 0;

        // Nudge schedule (variable interval)
        this.nextNudgeAt = 0;
        this.nudgesGiven = 0;

        // Comprehension schedule (fixed interval ~3 min)
        this.nextComprehensionCheckAt = 0;
        this.checksGiven = 0;
        this._lastCheckVariety = -1;   // track which variety was used last

        // DMN disruption — speed-drop detection
        // Track word timestamps to detect reading speed collapses
        this.wordTimestamps = [];      // [{index, time}] — last 60 entries
        this.baselineWPM = null;       // established baseline speed
        this.baselineWindow = 30;      // words to establish baseline
        this.speedDropThreshold = 0.40; // 40% drop from baseline triggers burst
        this.lastBurstTime = 0;        // throttle bursts (min 60s apart)
        this.burstCooldownMs = 60000;
    }

    // ── Sprint Timer ──

    /** Start a reading sprint.
     *  @param {number} [minutes=25] — sprint duration
     */
    startSprint(minutes = 25) {
        this.sprintMinutes = minutes;
        this.sprintStartTime = Date.now();
        this.sprintEndTime = this.sprintStartTime + (minutes * 60 * 1000);
        this.sprintActive = true;
        this.sprintPaused = false;
        this.totalPausedMs = 0;
        this.wordCount = 0;
        this.rewardsGiven = 0;
        this.nudgesGiven = 0;
        this.checksGiven = 0;
        this._lastCheckVariety = -1;

        // Reset DMN state
        this.wordTimestamps = [];
        this.baselineWPM = null;
        this.lastBurstTime = 0;

        // Schedule first nudge and comprehension check
        this.nextRewardAt = this._nextRewardWord();
        this.nextNudgeAt = Date.now() + this._randomNudgeDelay();
        this.nextComprehensionCheckAt = Date.now() + (3 * 60 * 1000);

        // Start the tick timer
        this._startTick();
    }

    /** Pause the sprint timer. */
    pause() {
        if (!this.sprintActive || this.sprintPaused) return;
        this.sprintPaused = true;
        this.pauseStartTime = Date.now();
        this._stopTick();
    }

    /** Resume the sprint timer. */
    resume() {
        if (!this.sprintActive || !this.sprintPaused) return;
        this.totalPausedMs += Date.now() - this.pauseStartTime;
        this.sprintPaused = false;
        this.pauseStartTime = null;
        this._startTick();
    }

    /** End the sprint early. */
    endSprint() {
        this.sprintActive = false;
        this.sprintPaused = false;
        this._stopTick();
        this.onSprintEnd();
    }

    /** Get remaining sprint time in seconds. */
    get remaining() {
        if (!this.sprintActive) return 0;
        const now = Date.now();
        const effectiveEnd = this.sprintEndTime + this.totalPausedMs +
            (this.sprintPaused ? (now - this.pauseStartTime) : 0);
        return Math.max(0, Math.round((effectiveEnd - now) / 1000));
    }

    /** Get elapsed time in seconds. */
    get elapsed() {
        if (!this.sprintActive) return 0;
        return (this.sprintMinutes * 60) - this.remaining;
    }

    /** Format remaining as mm:ss. */
    get remainingDisplay() {
        const r = this.remaining;
        const m = Math.floor(r / 60);
        const s = r % 60;
        return `${m}:${String(s).padStart(2, '0')}`;
    }

    // ── Word Tracking ──

    /** Call this on every word advance during a sprint.
     *  @param {number} index — current word index
     */
    onWord(index) {
        if (!this.sprintActive || this.sprintPaused) return;
        this.wordCount = index;

        // Track timestamp for DMN detection
        this.wordTimestamps.push({ index, time: Date.now() });
        if (this.wordTimestamps.length > 60) {
            this.wordTimestamps.shift();
        }

        this._checkReward();
        this._checkNudge();
        this._checkComprehension();
        this._checkDMNIntrusion();
    }

    // ── Reward System ──

    _nextRewardWord() {
        // Variable ratio: 40-400 words
        return this.wordCount + 40 + Math.floor(Math.random() * 360);
    }

    _checkReward() {
        if (this.wordCount < this.nextRewardAt) return;

        this.rewardsGiven++;

        // Pick reward type (weighted: mostly XP, sometimes compliment)
        const roll = Math.random();
        let reward;
        if (roll < 0.5) {
            reward = { type: 'xp', xp: 5 + Math.floor(Math.random() * 20), text: null };
        } else if (roll < 0.85) {
            const comp = COMPLIMENTS[Math.floor(Math.random() * COMPLIMENTS.length)];
            reward = { type: 'compliment', xp: 0, text: comp };
        } else {
            const emoji = XP_EMOJI[Math.floor(Math.random() * XP_EMOJI.length)];
            reward = { type: 'emoji', xp: 10, text: emoji + ' +10 XP' };
        }

        this.onReward(reward);
        this.nextRewardAt = this._nextRewardWord();
    }

    // ── Micro-Nudges ──

    _randomNudgeDelay() {
        // 30-120 seconds
        return (30 + Math.floor(Math.random() * 90)) * 1000;
    }

    _checkNudge() {
        if (Date.now() < this.nextNudgeAt) return;
        this.nudgesGiven++;
        this.onNudge();
        this.nextNudgeAt = Date.now() + this._randomNudgeDelay();
    }

    // ── Comprehension Checks ──

    _checkComprehension() {
        if (Date.now() < this.nextComprehensionCheckAt) return;
        this.checksGiven++;

        // Rotate through varieties (never same twice in a row)
        let varietyIndex;
        do {
            varietyIndex = Math.floor(Math.random() * CHECK_VARIETIES.length);
        } while (varietyIndex === this._lastCheckVariety && CHECK_VARIETIES.length > 1);
        this._lastCheckVariety = varietyIndex;

        const check = { ...CHECK_VARIETIES[varietyIndex], checkNumber: this.checksGiven };
        this.onComprehensionCheck(check);
        this.nextComprehensionCheckAt = Date.now() + (3 * 60 * 1000);
    }

    // ── DMN Intrusion Detection ──

    /** Detect reading speed collapses and trigger stochastic resonance burst.
     *
     *  Mechanism: track word timestamps over a sliding window.
     *  Establish a baseline WPM from the first `baselineWindow` words.
     *  After baseline is set, if recent speed drops >40%, fire a burst.
     *  Bursts are throttled (max 1 per 60 seconds) to avoid overstimulation.
     */
    _checkDMNIntrusion() {
        // Need at least baselineWindow words before we can detect drops
        if (this.wordTimestamps.length < this.baselineWindow) return;

        // Throttle bursts
        if (Date.now() - this.lastBurstTime < this.burstCooldownMs) return;

        // Calculate recent speed (last 10 words)
        const recent = this.wordTimestamps.slice(-10);
        const recentDuration = (recent[recent.length - 1].time - recent[0].time) / 1000;
        if (recentDuration <= 0) return;
        const recentWPM = (recent.length / recentDuration) * 60;

        // Calculate or use baseline
        if (this.baselineWPM === null) {
            const baseline = this.wordTimestamps.slice(0, this.baselineWindow);
            const baselineDuration = (baseline[baseline.length - 1].time - baseline[0].time) / 1000;
            if (baselineDuration <= 0) return;
            this.baselineWPM = (baseline.length / baselineDuration) * 60;
            return; // don't fire on first baseline calculation
        }

        // Check for significant drop
        const dropRatio = 1 - (recentWPM / this.baselineWPM);
        if (dropRatio > this.speedDropThreshold) {
            this.lastBurstTime = Date.now();
            this.onDMNBurst();

            // Reset baseline — brain has re-engaged, new baseline starts now
            this.wordTimestamps = this.wordTimestamps.slice(-5);
            this.baselineWPM = null;
        }
    }

    // ── Internal ──

    _startTick() {
        this._stopTick();
        this._tickInterval = setInterval(() => {
            if (this.sprintPaused) return;

            const remaining = this.remaining;
            this.onSprintTick({
                remaining: remaining,
                total: this.sprintMinutes * 60,
            });

            if (remaining <= 0) {
                this._stopTick();
                this.sprintActive = false;
                this.onSprintEnd();
            }
        }, 1000);
    }

    _stopTick() {
        if (this._tickInterval) {
            clearInterval(this._tickInterval);
            this._tickInterval = null;
        }
    }
}


// ── Confetti Effect (inline — no dependencies) ──

/**
 * Fire a quick confetti burst.
 * @param {HTMLElement} container — element to fire confetti over
 */
function fireConfetti(container) {
    const rect = container.getBoundingClientRect();
    const colors = ['#6366f1', '#818cf8', '#c084fc', '#f472b6', '#fb923c', '#34d399', '#fbbf24'];
    const particleCount = 40;
    const particles = [];

    for (let i = 0; i < particleCount; i++) {
        const el = document.createElement('div');
        el.style.cssText = `
            position: fixed;
            z-index: 9999;
            pointer-events: none;
            width: 8px;
            height: 8px;
            background: ${colors[Math.floor(Math.random() * colors.length)]};
            border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
            left: ${rect.left + Math.random() * rect.width}px;
            top: ${rect.top + Math.random() * 60}px;
            opacity: 1;
            transition: transform 1.5s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                        opacity 1.5s ease-out;
        `;
        document.body.appendChild(el);

        const vx = (Math.random() - 0.5) * 300;
        const vy = -50 - Math.random() * 200;
        const rot = (Math.random() - 0.5) * 720;

        particles.push({ el, vx, vy, rot });

        // Trigger animation in next frame
        requestAnimationFrame(() => {
            el.style.transform = `translate(${vx}px, ${vy}px) rotate(${rot}deg)`;
            el.style.opacity = '0';
        });
    }

    // Cleanup after animation
    setTimeout(() => {
        particles.forEach(p => p.el.remove());
    }, 1600);
}


/**
 * Show a floating XP popup.
 * @param {string} text — text to display
 * @param {HTMLElement} anchor — element to anchor the popup near
 */
function showXPPopup(text, anchor) {
    const rect = anchor.getBoundingClientRect();
    const el = document.createElement('div');
    el.textContent = text;
    el.style.cssText = `
        position: fixed;
        z-index: 9999;
        pointer-events: none;
        left: ${rect.left + rect.width / 2 - 40}px;
        top: ${rect.top}px;
        font-size: 18px;
        font-weight: 700;
        color: var(--accent, #6366f1);
        opacity: 1;
        transition: transform 2s ease-out, opacity 2s ease-out;
    `;
    document.body.appendChild(el);

    requestAnimationFrame(() => {
        el.style.transform = 'translateY(-80px) scale(1.2)';
        el.style.opacity = '0';
    });

    setTimeout(() => el.remove(), 2100);
}


// ── Comprehension Check (Variety-Based) ──

/**
 * Show a comprehension check modal — supports multiple interaction types.
 * @param {object} check — {type, question, options?, resolveOn?, checkNumber}
 * @returns {Promise<string>} — user response
 */
function showComprehensionCheck(check) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed; inset: 0; z-index: 10000;
            background: rgba(0,0,0,0.6);
            display: flex; align-items: center; justify-content: center;
        `;

        const modal = document.createElement('div');
        modal.style.cssText = `
            background: var(--bg-secondary, #1a1a1a);
            color: var(--text-primary, #fff);
            border: 1px solid var(--border, #2a2a2a);
            border-radius: 12px;
            padding: 24px 32px;
            max-width: 420px;
            text-align: center;
            font-family: inherit;
            animation: ritual-enter 0.3s ease-out;
        `;

        const close = (response) => {
            overlay.remove();
            resolve(response);
        };

        switch (check.type) {
        case 'tap':
            // Simplest interaction — tap/click anywhere
            modal.innerHTML = `
                <p style="font-size: 16px; margin-bottom: 16px;">${check.question}</p>
                <p style="font-size: 12px; color: var(--text-secondary);">
                    (or press any key)
                </p>
            `;
            overlay.addEventListener('click', () => close('tap'));
            document.addEventListener('keydown', function onKey(e) {
                document.removeEventListener('keydown', onKey);
                close('tap');
            }, { once: true });
            break;

        case 'yes_no':
        case 'mental':
            modal.innerHTML = `
                <p style="font-size: 15px; margin-bottom: 20px;">${check.question}</p>
                <div style="display: flex; gap: 10px; justify-content: center;">
                    ${(check.options || ['Got it ✓', 'Skip']).map((opt, i) => `
                        <button class="comp-btn comp-btn-${i === 0 ? 'primary' : 'secondary'}" style="
                            padding: 10px 20px;
                            ${i === 0
                                ? 'background: var(--accent, #6366f1); border: none; color: white;'
                                : 'background: transparent; border: 1px solid var(--border, #2a2a2a); color: var(--text-secondary);'}
                            border-radius: 6px; cursor: pointer; font-size: 14px; font-family: inherit;
                        ">${opt}</button>
                    `).join('')}
                </div>
            `;
            modal.querySelectorAll('button').forEach((btn, i) => {
                btn.addEventListener('click', () => close(check.options[i]));
            });
            break;

        case 'emoji':
            modal.innerHTML = `
                <p style="font-size: 15px; margin-bottom: 16px;">${check.question}</p>
                <div style="display: flex; gap: 8px; justify-content: center; flex-wrap: wrap;">
                    ${check.options.map(opt => `
                        <button style="
                            padding: 10px 14px; background: var(--bg-primary);
                            border: 1px solid var(--border); border-radius: 8px;
                            color: var(--text-primary); cursor: pointer;
                            font-size: 14px; font-family: inherit;
                            transition: border-color 0.15s;
                        " onmouseover="this.style.borderColor='var(--accent)'"
                           onmouseout="this.style.borderColor='var(--border)'"
                        >${opt}</button>
                    `).join('')}
                </div>
            `;
            modal.querySelectorAll('button').forEach((btn, i) => {
                btn.addEventListener('click', () => close(check.options[i]));
            });
            break;

        case 'breathe':
            modal.innerHTML = `
                <p style="font-size: 15px; margin-bottom: 20px;">${check.question}</p>
                <button style="
                    padding: 14px 32px; background: var(--accent, #6366f1);
                    border: none; border-radius: 8px; color: white;
                    cursor: pointer; font-size: 15px; font-family: inherit;
                ">${check.options[0]}</button>
            `;
            modal.querySelector('button').addEventListener('click', () => close('continue'));
            break;

        default:
            // Fallback to yes/no
            modal.innerHTML = `
                <p style="font-size: 15px; margin-bottom: 20px;">${check.question || 'Comprehension check'}</p>
                <div style="display: flex; gap: 10px; justify-content: center;">
                    <button style="padding: 10px 24px; background: var(--accent); border: none; border-radius: 6px; color: white; cursor: pointer;">Got it</button>
                </div>
            `;
            modal.querySelector('button').addEventListener('click', () => close('ok'));
        }

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Click outside closes (except for 'tap' type which uses it as input)
        if (check.type !== 'tap') {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close('dismiss');
            });
        }
    });
}


// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { HyperfocusEngine, fireConfetti, showXPPopup, showComprehensionCheck };
}
