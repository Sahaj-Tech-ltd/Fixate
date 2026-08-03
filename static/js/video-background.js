/**
 * Fixate — Video Background Engine
 * 
 * Renders a full-screen YouTube/Vimeo embed behind the main content
 * with a configurable dark overlay for readability.
 * 
 * Features:
 *   - 8 curated scenic presets (Bali, NYC, Tokyo, Alps, Aurora, Beach, Rain, Forest)
 *   - Custom URL input (paste any YouTube/Vimeo link)
 *   - Opacity slider for the dark overlay
 *   - Persists to localStorage
 *   - Web-only feature (desktop doesn't ship with this)
 */

function videoBackground() {
    return {
        presets: [
            {
                id: 'bali',
                name: 'Bali',
                location: 'Rice Terraces & Temples',
                thumbnail: '🌴',
                videoId: 'lzjruXO0Fvc',
                platform: 'youtube',
            },
            {
                id: 'nyc',
                name: 'New York',
                location: 'Skyline at Night',
                thumbnail: '🌃',
                videoId: 'BbPiuO8NAdE',
                platform: 'youtube',
            },
            {
                id: 'tokyo',
                name: 'Tokyo',
                location: 'Shibuya Night Walk',
                thumbnail: '🗼',
                videoId: '0nTO4zSEpOs',
                platform: 'youtube',
            },
            {
                id: 'alps',
                name: 'Swiss Alps',
                location: 'Mountain Majesty',
                thumbnail: '🏔️',
                videoId: 'BTMjD7_evjE',
                platform: 'youtube',
            },
            {
                id: 'aurora',
                name: 'Northern Lights',
                location: 'Aurora Borealis',
                thumbnail: '🌌',
                videoId: 'v5RGH0SmKJY',
                platform: 'youtube',
            },
            {
                id: 'beach',
                name: 'Tropical Beach',
                location: 'Bali Aerial Drone',
                thumbnail: '🏝️',
                videoId: 'dEep6DAv_xs',
                platform: 'youtube',
            },
            {
                id: 'rain',
                name: 'Rainy Cafe',
                location: 'Cozy Coffee Shop',
                thumbnail: '☕',
                videoId: 'bWGQTlopoEY',
                platform: 'youtube',
            },
            {
                id: 'forest',
                name: 'Forest Stream',
                location: 'Nature & Birdsong',
                thumbnail: '🌿',
                videoId: '3PZ65s2qLTE',
                platform: 'youtube',
            },
            // CSS Gradient scenes (no bandwidth, works offline, ships with desktop)
            {
                id: 'gradient-northern',
                name: 'Northern Lights',
                location: 'CSS Gradient',
                thumbnail: '🌌',
                type: 'gradient',
                cssClass: 'bg-gradient-northern',
            },
            {
                id: 'gradient-ocean',
                name: 'Ocean Depths',
                location: 'CSS Gradient',
                thumbnail: '🌊',
                type: 'gradient',
                cssClass: 'bg-gradient-ocean',
            },
            {
                id: 'gradient-sunset',
                name: 'Sunset Glow',
                location: 'CSS Gradient',
                thumbnail: '🌅',
                type: 'gradient',
                cssClass: 'bg-gradient-sunset',
            },
            {
                id: 'gradient-forest',
                name: 'Forest Canopy',
                location: 'CSS Gradient',
                thumbnail: '🌲',
                type: 'gradient',
                cssClass: 'bg-gradient-forest',
            },
            {
                id: 'gradient-cyberpunk',
                name: 'Cyberpunk',
                location: 'CSS Gradient',
                thumbnail: '🌆',
                type: 'gradient',
                cssClass: 'bg-gradient-cyberpunk',
            },
        ],

        active: null,
        customVideoId: null,
        customPlatform: null,
        customLabel: '',
        showPicker: false,
        opacity: 0.55,
        customUrl: '',
        parseError: '',

        init() {
            const saved = JSON.parse(localStorage.getItem('fixate-video-bg') || '{}');
            if (saved.active) {
                if (saved.active === 'custom' && saved.customVideoId) {
                    this.setCustomVideo(saved.customVideoId, saved.customPlatform, saved.customLabel || '');
                } else {
                    const preset = this.presets.find(p => p.id === saved.active);
                    if (preset) this.activate(preset);
                }
            }
            if (saved.opacity !== undefined) this.opacity = saved.opacity;
            this.applyOverlay();
        },

        activate(preset) {
            this.closePip();
            this.active = preset.id;
            this.customVideoId = null;
            this.customPlatform = null;
            this.customLabel = '';

            if (preset.type === 'gradient') {
                this.renderGradient(preset.cssClass);
            } else {
                this.renderVideo(preset.videoId, preset.platform);
            }
            this.save();
        },

        renderGradient(cssClass) {
            // Clear video container
            const container = document.getElementById('video-bg-container');
            if (container) container.innerHTML = '';

            // Apply gradient class to body
            document.body.classList.forEach(c => {
                if (c.startsWith('bg-gradient-')) document.body.classList.remove(c);
            });
            document.body.classList.add(cssClass);

            // Show background layer
            const layer = document.getElementById('video-bg-layer');
            if (layer) layer.classList.add('active');
        },

        setCustomUrl() {
            this.parseError = '';
            const url = this.customUrl.trim();
            if (!url) return;

            const parsed = this.parseUrl(url);
            if (!parsed) {
                this.parseError = 'Could not parse that URL. Paste a YouTube or Vimeo link.';
                return;
            }

            this.active = 'custom';
            this.customVideoId = parsed.videoId;
            this.customPlatform = parsed.platform;
            this.customLabel = url.length > 40 ? url.slice(0, 40) + '…' : url;
            this.renderVideo(parsed.videoId, parsed.platform);
            this.save();
            this.customUrl = '';
        },

        parseUrl(url) {
            // YouTube: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/embed/ID, youtube.com/shorts/ID
            let match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/);
            if (match) return { videoId: match[1], platform: 'youtube' };

            // Vimeo: vimeo.com/ID
            match = url.match(/vimeo\.com\/(\d+)/);
            if (match) return { videoId: match[1], platform: 'vimeo' };

            return null;
        },

        renderVideo(videoId, platform) {
            const container = document.getElementById('video-bg-container');
            if (!container) return;

            const layer = document.getElementById('video-bg-layer');
            if (layer) layer.classList.add('active');

            let src;
            if (platform === 'youtube') {
                // autoplay + mute + loop + no controls + no related
                src = 'https://www.youtube.com/embed/' + videoId
                    + '?autoplay=1&mute=1&loop=1&controls=0'
                    + '&playlist=' + videoId
                    + '&rel=0&showinfo=0&iv_load_policy=3'
                    + '&modestbranding=1&disablekb=1';
            } else if (platform === 'vimeo') {
                src = 'https://player.vimeo.com/video/' + videoId
                    + '?autoplay=1&muted=1&loop=1&background=1&controls=0';
            }

            container.innerHTML = '<iframe src="' + src + '" frameborder="0" allow="autoplay; fullscreen" allowfullscreen></iframe>';
        },

        setCustomVideo(videoId, platform, label) {
            this.active = 'custom';
            this.customVideoId = videoId;
            this.customPlatform = platform;
            this.customLabel = label || 'Custom Video';
            this.renderVideo(videoId, platform);
        },

        clear() {
            this.active = null;
            this.customVideoId = null;
            this.customPlatform = null;
            this.customLabel = '';
            this.closePip();
            const container = document.getElementById('video-bg-container');
            if (container) container.innerHTML = '';
            const layer = document.getElementById('video-bg-layer');
            if (layer) layer.classList.remove('active');
            // Remove any gradient classes
            document.body.classList.forEach(c => {
                if (c.startsWith('bg-gradient-')) document.body.classList.remove(c);
            });
            this.save();
        },

        setOpacity(val) {
            this.opacity = parseFloat(val);
            this.applyOverlay();
            this.save();
        },

        applyOverlay() {
            const overlay = document.getElementById('video-bg-overlay');
            if (overlay) {
                overlay.style.background = 'rgba(8, 8, 10, ' + this.opacity + ')';
            }
        },

        save() {
            localStorage.setItem('fixate-video-bg', JSON.stringify({
                active: this.active,
                customVideoId: this.customVideoId,
                customPlatform: this.customPlatform,
                customLabel: this.customLabel,
                opacity: this.opacity,
            }));
        },

        isActive(id) {
            return this.active === id;
        },

        getActiveName() {
            if (!this.active) return '';
            if (this.active === 'custom') return this.customLabel || 'Custom Video';
            const preset = this.presets.find(p => p.id === this.active);
            return preset ? (preset.thumbnail + ' ' + preset.name + ' — ' + preset.location) : '';
        },

        // ── Picture-in-Picture (faux mini-player) ──
        pipActive: false,
        pipEl: null,

        canPip() {
            if (!this.active || this.active.startsWith('gradient')) return false;
            if (this.active === 'custom') return !!this.customVideoId;
            const preset = this.presets.find(p => p.id === this.active);
            return !!(preset && preset.videoId);
        },

        togglePip() {
            if (this.pipActive) { this.closePip(); } else { this.openPip(); }
        },

        openPip() {
            if (!this.active || this.pipActive) return;
            // Move the existing background iframe into PiP instead of creating a second embed
            const bgContainer = document.getElementById('video-bg-container');
            const existingIframe = bgContainer && bgContainer.querySelector('iframe');
            if (!existingIframe) return;

            const pip = document.createElement('div');
            pip.id = 'faux-pip-player';
            pip.innerHTML =
                '<div class="pip-header" style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:var(--bg-primary);cursor:move;user-select:none;">' +
                    '<span style="font-size:12px;color:var(--text-secondary);">📺 Picture-in-Picture</span>' +
                    '<button class="pip-close-btn" style="background:none;border:none;color:var(--text-secondary);cursor:pointer;font-size:14px;padding:2px 6px;border-radius:4px;">✕</button>' +
                '</div>' +
                '<div class="pip-video-wrap" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;"></div>';
            pip.style.cssText = 'position:fixed;bottom:80px;right:24px;width:320px;z-index:9999;background:var(--bg-secondary);border:1px solid var(--border);border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.6);';

            // Move the existing iframe into the PiP container
            const videoWrap = pip.querySelector('.pip-video-wrap');
            existingIframe.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;border:none;';
            videoWrap.appendChild(existingIframe);

            // Dim the background layer to indicate PiP mode
            const layer = document.getElementById('video-bg-layer');
            if (layer) layer.style.opacity = '0.3';

            if (!document.getElementById('pip-anim-style')) {
                const s = document.createElement('style');
                s.id = 'pip-anim-style';
                s.textContent = '@keyframes pip-enter{from{opacity:0;transform:scale(0.9)}to{opacity:1;transform:scale(1)}}#faux-pip-player{animation:pip-enter 0.25s ease}#faux-pip-player .pip-close-btn:hover{color:var(--text-primary);background:rgba(255,255,255,0.1)}';
                document.head.appendChild(s);
            }

            document.body.appendChild(pip);
            this.pipEl = pip;
            this.pipActive = true;
            pip.querySelector('.pip-close-btn').addEventListener('click', () => this.closePip());
            this._initPipDrag(pip);
        },

        closePip() {
            if (!this.pipEl) return;
            // Move the iframe back to the background container
            const existingIframe = this.pipEl.querySelector('iframe');
            if (existingIframe) {
                const bgContainer = document.getElementById('video-bg-container');
                if (bgContainer) {
                    existingIframe.style.cssText = '';
                    bgContainer.appendChild(existingIframe);
                }
            }
            // Restore background layer opacity
            const layer = document.getElementById('video-bg-layer');
            if (layer) layer.style.opacity = '';
            this.pipEl.remove();
            this.pipEl = null;
            this.pipActive = false;
        },

        _initPipDrag(el) {
            const header = el.querySelector('.pip-header');
            if (!header) return;
            let dragging = false, sx, sy, ox, oy;
            const onDown = (e) => {
                dragging = true; sx = e.clientX; sy = e.clientY;
                const r = el.getBoundingClientRect(); ox = r.left; oy = r.top;
                el.style.transition = 'none'; e.preventDefault();
            };
            const onMove = (e) => {
                if (!dragging) return;
                el.style.left = (ox + e.clientX - sx) + 'px';
                el.style.top = (oy + e.clientY - sy) + 'px';
                el.style.right = 'auto'; el.style.bottom = 'auto';
            };
            const onUp = () => { dragging = false; };
            header.addEventListener('mousedown', onDown);
            document.addEventListener('mousemove', onMove);
            document.addEventListener('mouseup', onUp);
        },
    };
}
