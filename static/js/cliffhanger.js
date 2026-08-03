/**
 * Fixate Zeigarnik Cliffhanger Engine — Unfinished Task Memory Hooks
 *
 * The Zeigarnik Effect (Bluma Zeigarnik, 1927): people remember interrupted
 * or incomplete tasks ~90% better than completed ones. Unfinished cognitive
 * "loops" create mental tension that the brain wants to resolve.
 *
 * Netflix exploits this with "Next episode in 5..." auto-play. We exploit it
 * for reading: when you pause or stop mid-document, we save a "cliffhanger"
 * — the first ~15 words of your next unread paragraph. When you come back,
 * the dashboard shows it as a teaser. Your brain WANTS to resolve it.
 *
 * Three hook points:
 *   1. Pause Cliffhanger — when user pauses reading, grab next paragraph preview
 *   2. Exit Cliffhanger — when user leaves reader, save stronger teaser
 *   3. Dashboard Comeback — show pending cliffhangers as "Continue reading..."
 *
 * Also integrates with comprehension checks: questions asked during a session
 * can defer answer display until the user resumes, creating a double hook
 * (both the cliffhanger AND the unanswered question pulling them back).
 *
 * Usage:
 *   const zh = new ZeigarnikEngine();
 *   zh.saveCliffhanger({
 *       documentId: 'abc123',
 *       documentTitle: 'My Paper',
 *       position: 0.42,         // 42% through
 *       nextParagraph: 'The critical insight that changes everything about...',
 *       pendingQuestion: 'What did the author mean by...?',
 *   });
 *
 *   // Later, on dashboard:
 *   const hooks = zh.getPendingHooks();
 *   // [{ documentId, documentTitle, teaser, position, pendingQuestion }]
 */

class ZeigarnikEngine {
    constructor() {
        this._storageKey = 'fixate-cliffhangers';
    }

    /**
     * Save a cliffhanger hook for a document.
     * @param {object} opts
     * @param {string} opts.documentId
     * @param {string} opts.documentTitle
     * @param {number} [opts.position] — 0.0-1.0 progress
     * @param {string} [opts.nextParagraph] — first ~80 chars of next paragraph
     * @param {string} [opts.pendingQuestion] — unanswered comprehension question
     * @param {number} [opts.expiresInHours=72] — auto-expire after X hours
     */
    saveCliffhanger(opts) {
        if (!opts.documentId) return;

        const hooks = this._loadAll();

        // Remove existing hook for same document (replace, don't duplicate)
        const filtered = hooks.filter(h => h.documentId !== opts.documentId);

        filtered.push({
            documentId: opts.documentId,
            documentTitle: opts.documentTitle || 'Untitled',
            position: opts.position ?? 0,
            nextParagraph: opts.nextParagraph || '',
            pendingQuestion: opts.pendingQuestion || '',
            savedAt: Date.now(),
            expiresAt: Date.now() + (opts.expiresInHours || 72) * 3600000,
        });

        // Keep only the 10 most recent hooks
        const trimmed = filtered.slice(-10);

        this._saveAll(trimmed);
    }

    /**
     * Get all pending (non-expired) cliffhanger hooks.
     * Most recently saved first.
     */
    getPendingHooks() {
        const hooks = this._loadAll();
        const now = Date.now();

        const active = hooks
            .filter(h => h.expiresAt > now)
            .sort((a, b) => b.savedAt - a.savedAt);

        // Clean expired hooks
        if (active.length < hooks.length) {
            this._saveAll(active);
        }

        return active;
    }

    /**
     * Get a specific hook by document ID.
     */
    getHook(documentId) {
        const hooks = this._loadAll();
        return hooks.find(h => h.documentId === documentId && h.expiresAt > Date.now()) || null;
    }

    /**
     * Mark a hook as resolved (user continued reading).
     */
    resolveHook(documentId) {
        const hooks = this._loadAll();
        const filtered = hooks.filter(h => h.documentId !== documentId);
        this._saveAll(filtered);
    }

    /**
     * Generate a compelling teaser from a paragraph snippet.
     * Tailors the wording to different hook styles.
     *
     * @param {string} paragraph — the next paragraph text
     * @param {object} [opts]
     * @param {string} [opts.style='curiosity'] — 'curiosity', 'challenge', 'mystery'
     * @returns {string} teaser text
     */
    static generateTeaser(paragraph, opts = {}) {
        if (!paragraph) return '';

        const style = opts.style || 'curiosity';
        const preview = paragraph.trim().slice(0, 80);

        const templates = {
            curiosity: [
                `Up next: "${preview}..."`,
                `You were about to discover: "${preview}..."`,
                `The next insight: "${preview}..."`,
            ],
            challenge: [
                `Can you figure out: "${preview}..."?`,
                `The author claims: "${preview}..." — do you agree?`,
                `Challenge: "${preview}..."`,
            ],
            mystery: [
                `What happens next? "${preview}..."`,
                `The story continues: "${preview}..."`,
                `Don't leave it hanging: "${preview}..."`,
            ],
        };

        const pool = templates[style] || templates.curiosity;
        return pool[Math.floor(Math.random() * pool.length)];
    }

    /**
     * Extract the next paragraph from a document after a given position.
     * Used when user pauses — we grab the upcoming text as bait.
     *
     * @param {string} fullText — full document text
     * @param {number} position — 0.0-1.0 progress
     * @returns {object} { nextParagraph, position }
     */
    static extractNextParagraph(fullText, position) {
        if (!fullText) return { nextParagraph: '', position: 0 };

        const paragraphs = fullText.split(/\n\n+/).filter(p => p.trim().length > 0);
        if (paragraphs.length === 0) return { nextParagraph: '', position: 0 };

        // Find which paragraph we're in based on position
        const totalChars = fullText.length;
        const charPos = Math.floor(position * totalChars);

        let cumulative = 0;
        let currentIdx = 0;

        for (let i = 0; i < paragraphs.length; i++) {
            cumulative += paragraphs[i].length;
            if (cumulative >= charPos) {
                currentIdx = i;
                break;
            }
        }

        // Get the NEXT paragraph (or current if it's the last one)
        const nextIdx = Math.min(currentIdx + 1, paragraphs.length - 1);
        const nextParagraph = paragraphs[nextIdx] || '';

        return {
            nextParagraph: nextParagraph.trim().slice(0, 200), // reasonable preview
            position,
        };
    }

    // ── Internal ──

    _loadAll() {
        try {
            return JSON.parse(localStorage.getItem(this._storageKey) || '[]');
        } catch (e) {
            return [];
        }
    }

    _saveAll(hooks) {
        localStorage.setItem(this._storageKey, JSON.stringify(hooks));
    }
}
