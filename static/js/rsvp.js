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
