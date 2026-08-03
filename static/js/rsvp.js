/**
 * Fixate RSVP — Rapid Serial Visual Presentation
 *
 * Two implementations:
 *   - RSVPReader: lightweight, battle-tested, used by readerApp() inline
 *   - RSVPEngine: enhanced standalone mode with ORP highlighting, smart
 *     chunking, and punctuation-aware pauses (for full-screen flash reading)
 */

// ── RSVPReader (existing, used by readerApp) ──

class RSVPReader {
    constructor(options = {}) {
        this.text = options.text || '';
        this.wpm = options.wpm || 300;
        this.chunkSize = options.chunkSize || 1;
        this.onStart = options.onStart || (() => {});
        this.onWord = options.onWord || (() => {});
        this.onProgress = options.onProgress || (() => {});
        this.onComplete = options.onComplete || (() => {});
        this.onPause = options.onPause || (() => {});

        this.words = [];
        this.currentIndex = 0;
        this.isPlaying = false;
        this.timeoutId = null;
        this.lastChunk = [];

        this.prepareWords();
    }

    prepareWords() {
        this.words = this.text
            .split(/\s+/)
            .filter(word => word.trim().length > 0);
    }

    getInterval() {
        return 60000 / this.wpm;
    }

    getCurrentChunk() {
        const start = this.currentIndex;
        const end = Math.min(start + this.chunkSize, this.words.length);
        return this.words.slice(start, end).join(' ');
    }

    getNextChunk() {
        const start = this.currentIndex + this.chunkSize;
        if (start >= this.words.length) return '';
        const end = Math.min(start + this.chunkSize, this.words.length);
        return this.words.slice(start, end).join(' ');
    }

    start() {
        if (this.words.length === 0) return;
        this.isPlaying = true;
        this.onStart();
        this.displayNext();
    }

    displayNext() {
        if (!this.isPlaying) return;

        if (this.currentIndex >= this.words.length) {
            this.isPlaying = false;
            this.onComplete();
            return;
        }

        const chunk = this.getCurrentChunk();
        this.lastChunk = [chunk, this.currentIndex];
        this.onWord(chunk, this.currentIndex);
        this.onProgress(this.currentIndex / this.words.length);

        this.currentIndex += this.chunkSize;

        let interval = this.getInterval();
        if (chunk.match(/[.!?,;:]$/)) {
            interval += 100;
        }

        this.timeoutId = setTimeout(() => this.displayNext(), interval);
    }

    pause() {
        this.isPlaying = false;
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        this.onPause();
    }

    resume() {
        if (!this.isPlaying && this.currentIndex < this.words.length) {
            this.isPlaying = true;
            this.displayNext();
        }
    }

    toggle() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.resume();
        }
    }

    rewind(count = 10) {
        this.currentIndex = Math.max(0, this.currentIndex - count);
        if (!this.isPlaying) {
            const chunk = this.getCurrentChunk();
            this.onWord(chunk, this.currentIndex);
            this.onProgress(this.currentIndex / this.words.length);
        }
    }

    forward(count = 10) {
        this.currentIndex = Math.min(this.words.length - 1, this.currentIndex + count);
        if (!this.isPlaying) {
            const chunk = this.getCurrentChunk();
            this.onWord(chunk, this.currentIndex);
            this.onProgress(this.currentIndex / this.words.length);
        }
    }

    goTo(index) {
        this.currentIndex = Math.max(0, Math.min(index, this.words.length - 1));
        if (!this.isPlaying) {
            const chunk = this.getCurrentChunk();
            this.onWord(chunk, this.currentIndex);
            this.onProgress(this.currentIndex / this.words.length);
        }
    }

    setWPM(wpm) {
        this.wpm = Math.max(50, Math.min(1000, wpm));
    }

    setChunkSize(size) {
        this.chunkSize = Math.max(1, Math.min(5, size));
    }

    setPosition(position) {
        this.currentIndex = Math.max(0, Math.min(position, this.words.length - 1));
    }

    getProgress() {
        return {
            current: this.currentIndex,
            total: this.words.length,
            percent: (this.currentIndex / this.words.length) * 100
        };
    }
}

window.RSVPReader = RSVPReader;


// ── RSVPEngine (enhanced standalone flash reader) ──

/**
 * Enhanced RSVP with Optimal Recognition Position highlighting, smart
 * chunking (short words bundled, long words solo), and punctuation-aware
 * pausing. Designed for a full-screen "flash reading" mode separate from
 * the inline readerApp().
 *
 * Research:
 *   - ORP at ~30% into word = fastest lexical access (Rayner, 1979)
 *   - Punctuation pauses improve RSVP comprehension to match natural
 *     reading (Masson, 1986)
 *   - Eliminates regression and saccade fatigue (ADHD-specific benefit)
 *
 * Usage:
 *   const rsvp = new RSVPEngine({
 *       container: document.getElementById('rsvp-target'),
 *       text: "Full document text...",
 *       wpm: 350,
 *   });
 *   rsvp.start();
 */
class RSVPEngine {
    constructor(opts = {}) {
        this.container = opts.container;
        this.wpm = Math.max(100, Math.min(1000, opts.wpm || 350));
        this.orpColor = opts.orpColor || '#7c3aed';
        this.showORP = opts.showORP !== false;
        this.smartChunk = opts.smartChunk !== false;
        this.punctuationPauses = opts.punctuationPauses !== false;
        this.onProgress = opts.onProgress || null;
        this.onComplete = opts.onComplete || null;
        this.onPause = opts.onPause || null;

        this._words = [];
        this._chunks = [];
        this._chunkIdx = -1;
        this._timer = null;
        this._running = false;
        this._paused = false;

        if (opts.text) this.loadText(opts.text);
        this._loadSettings();
    }

    loadText(text) {
        if (!text) return;
        const raw = text.split(/\s+/).filter(w => w.length > 0);
        this._chunks = this.smartChunk ? this._smartChunk(raw) : raw.map(w => [w]);
        this._chunkIdx = -1;
    }

    start() {
        if (this._chunks.length === 0) return;
        this.stop();
        this._running = true;
        this._paused = false;
        this._chunkIdx = -1;
        this._containerClear();
        this._containerShow();
        this._nextChunk();
    }

    pause() {
        if (!this._running || this._paused) return;
        this._paused = true;
        if (this._timer) clearTimeout(this._timer);
        if (this.onPause) this.onPause({ wordIndex: this._chunkIdx, totalWords: this._chunks.length });
    }

    resume() {
        if (!this._paused) return;
        this._paused = false;
        this._nextChunk();
    }

    toggle() {
        if (this._paused) this.resume();
        else if (this._running) this.pause();
        else this.start();
    }

    stop() {
        this._running = false;
        this._paused = false;
        if (this._timer) clearTimeout(this._timer);
        this._timer = null;
        this._containerClear();
        this._containerHide();
    }

    setWPM(wpm) {
        this.wpm = Math.max(100, Math.min(1000, wpm));
        this._saveSettings();
    }

    adjustWPM(delta) { this.setWPM(this.wpm + delta); }

    get isRunning() { return this._running; }
    get isPaused() { return this._paused; }
    get currentWord() { return this._chunkIdx + 1; }
    get totalWords() { return this._chunks.length; }
    get msPerWord() { return 60000 / this.wpm; }

    // ── Internal ──

    _smartChunk(raw) {
        const chunks = [];
        let i = 0;
        while (i < raw.length) {
            const word = raw[i];
            if (word === '\n' || word === '\n\n') { i++; continue; }
            if (/[.!?;:]$/.test(word) && word.length <= 6) { chunks.push([word]); i++; continue; }
            if (word.length <= 3 && !/[.!?;:,]$/.test(word) && i + 1 < raw.length) {
                const next = raw[i + 1];
                if (next.length <= 3 && !/[.!?;:,]$/.test(next)) {
                    if (i + 2 < raw.length && raw[i + 2].length <= 3 && !/[.!?;:,]$/.test(raw[i + 2])) {
                        chunks.push([word, next, raw[i + 2]]); i += 3;
                    } else { chunks.push([word, next]); i += 2; }
                    continue;
                }
            }
            chunks.push([word]); i++;
        }
        return chunks;
    }

    _nextChunk() {
        if (!this._running || this._paused) return;
        this._chunkIdx++;
        if (this._chunkIdx >= this._chunks.length) {
            this.stop();
            if (this.onComplete) this.onComplete();
            return;
        }
        const chunk = this._chunks[this._chunkIdx];
        this._renderChunk(chunk);
        if (this.onProgress) this.onProgress({ wordIndex: this._chunkIdx, totalWords: this._chunks.length });

        let delay = this.msPerWord;
        if (this.punctuationPauses && chunk.length === 1) {
            const word = chunk[0];
            if (/[.!?]$/.test(word)) delay = this.msPerWord * 2.0;
            else if (/[,;:]$/.test(word)) delay = this.msPerWord * 1.5;
            else if (/[—]$/.test(word) || /^[—]/.test(word)) delay = this.msPerWord * 1.3;
        }
        this._timer = setTimeout(() => this._nextChunk(), delay);
    }

    _renderChunk(chunk) {
        if (chunk.length === 1) {
            this.container.innerHTML = this._highlightORP(chunk[0]);
        } else {
            const first = this._highlightORP(chunk[0]);
            const rest = chunk.slice(1).map(w => `<span class="rsvp-word-plain">${this._escape(w)}</span>`).join(' ');
            this.container.innerHTML = `${first} ${rest}`;
        }
    }

    _highlightORP(word) {
        if (!this.showORP || word.length <= 1) return `<span class="rsvp-word">${this._escape(word)}</span>`;
        let orpPos;
        if (word.length <= 3) orpPos = Math.min(1, word.length - 1);
        else if (word.length <= 6) orpPos = Math.floor(word.length * 0.4);
        else orpPos = Math.floor(word.length * 0.35);
        const orpChar = word[orpPos];
        if (/[.,;:!?'\")]/.test(orpChar) && orpPos > 0) orpPos--;
        const prefix = this._escape(word.slice(0, orpPos));
        const center = this._escape(word[orpPos]);
        const suffix = this._escape(word.slice(orpPos + 1));
        return `<span class="rsvp-word">${prefix}<span class="rsvp-orp" style="color:${this.orpColor}">${center}</span>${suffix}</span>`;
    }

    _escape(str) { const d = document.createElement('div'); d.textContent = str; return d.innerHTML; }
    _containerClear() { this.container.innerHTML = ''; }
    _containerShow() { this.container.style.display = 'flex'; }
    _containerHide() { this.container.style.display = 'none'; }

    _saveSettings() { localStorage.setItem('fixate-rsvp', JSON.stringify({ wpm: this.wpm })); }
    _loadSettings() {
        try { const s = JSON.parse(localStorage.getItem('fixate-rsvp') || '{}'); if (s.wpm) this.wpm = s.wpm; } catch (e) {}
    }
}

window.RSVPEngine = RSVPEngine;
