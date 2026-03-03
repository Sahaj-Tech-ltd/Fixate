class BionicReader {
    constructor(options = {}) {
        this.text = options.text || '';
        this.boldIntensity = options.boldIntensity || 0.5;
        this.onStart = options.onStart || (() => {});
        this.onRender = options.onRender || (() => {});
        this.onProgress = options.onProgress || (() => {});
        
        this.words = [];
        this.currentIndex = 0;
        this.element = null;
        
        this.prepareWords();
    }
    
    prepareWords() {
        this.words = this.text
            .split(/\s+/)
            .filter(word => word.trim().length > 0);
    }
    
    getBoldLength(word) {
        const length = word.length;
        if (length <= 1) return 1;
        if (length <= 3) return 1;
        if (length <= 5) return 2;
        return Math.ceil(length * this.boldIntensity);
    }
    
    formatWord(word) {
        const boldLength = this.getBoldLength(word);
        const boldPart = word.slice(0, boldLength);
        const rest = word.slice(boldLength);
        return `<strong>${boldPart}</strong>${rest}`;
    }
    
    render(container, position = 0) {
        this.currentIndex = Math.max(0, Math.min(position, this.words.length - 1));
        this.element = container;
        
        const visibleWords = 50;
        const start = Math.max(0, this.currentIndex - 5);
        const end = Math.min(this.words.length, start + visibleWords);
        
        let html = '';
        
        for (let i = start; i < end; i++) {
            const formattedWord = this.formatWord(this.words[i]);
            const isCurrentWord = i === this.currentIndex;
            const wordClass = isCurrentWord ? 'word current' : 'word';
            html += `<span class="${wordClass}" data-index="${i}">${formattedWord}</span> `;
        }
        
        container.innerHTML = html;
        this.onRender(html);
        this.onProgress(this.currentIndex / this.words.length);
        
        const currentWordEl = container.querySelector('.current');
        if (currentWordEl) {
            currentWordEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }
    
    next() {
        if (this.currentIndex < this.words.length - 1) {
            this.currentIndex++;
            this.render(this.element, this.currentIndex);
        }
    }
    
    prev() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this.render(this.element, this.currentIndex);
        }
    }
    
    goTo(index) {
        this.currentIndex = Math.max(0, Math.min(index, this.words.length - 1));
        this.render(this.element, this.currentIndex);
    }
    
    setBoldIntensity(intensity) {
        this.boldIntensity = Math.max(0.2, Math.min(0.8, intensity));
        if (this.element) {
            this.render(this.element, this.currentIndex);
        }
    }
    
    setPosition(position) {
        this.currentIndex = Math.max(0, Math.min(position, this.words.length - 1));
        if (this.element) {
            this.render(this.element, this.currentIndex);
        }
    }
    
    getProgress() {
        return {
            current: this.currentIndex,
            total: this.words.length,
            percent: (this.currentIndex / this.words.length) * 100
        };
    }
}

window.BionicReader = BionicReader;
