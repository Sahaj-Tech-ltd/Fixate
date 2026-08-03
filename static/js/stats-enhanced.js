/* ═══════════════════════════════════════════════════════════════
   FIXATE — Enhanced Focus Stats Module
   Drop-in enhancement for #panel-stats in dashboard.html
   ═══════════════════════════════════════════════════════════════

   INTEGRATION GUIDE:
   1. Paste the <style> block into {% block extra_css %} (or before </style>)
   2. Replace the #panel-stats .fx-panel-body content with the HTML below
   3. Paste the JS block at the end of the <script> section
   4. The JS auto-hooks into onTimerComplete via session logging

   Data source: localStorage key 'fixate_sessions'
   Schema: [{ date: ISO string, duration: minutes (number), mode: string, completed: boolean }]
   ═══════════════════════════════════════════════════════════════ */

(function FixateEnhancedStats() {
    'use strict';

    /* ── Helpers ── */
    var $ = function(sel) { return document.querySelector(sel); };
    var $$ = function(sel) { return document.querySelectorAll(sel); };

    var SESSIONS_KEY = 'fixate_sessions';
    var FOCUS_STATS_KEY = 'fixate_focus_stats'; // legacy key for migration
    var DAILY_GOAL_KEY = 'fx_daily_goal';
    var WEEKLY_GOAL_KEY = 'fx_weekly_goal';

    var MODE_META = {
        pomodoro:   { icon: '🍅', label: 'Pomodoro' },
        countdown:  { icon: '⏳', label: 'Countdown' },
        stopwatch:  { icon: '⏱️', label: 'Stopwatch' },
        animedoro:  { icon: '🎌', label: 'Animedoro' },
        focus:      { icon: '🎯', label: 'Focus' },
        break:      { icon: '☕', label: 'Break' }
    };

    /* ── Data Layer ── */

    function getSessions() {
        try {
            return JSON.parse(localStorage.getItem(SESSIONS_KEY) || '[]');
        } catch (e) { return []; }
    }

    function saveSessions(sessions) {
        localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
    }

    function addSession(duration, mode, completed) {
        var sessions = getSessions();
        sessions.push({
            date: new Date().toISOString(),
            duration: Math.round(duration),  // minutes
            mode: mode || 'pomodoro',
            completed: completed !== false
        });
        // Keep last 500 sessions to avoid localStorage bloat
        if (sessions.length > 500) {
            sessions = sessions.slice(sessions.length - 500);
        }
        saveSessions(sessions);
    }

    /* Migrate from legacy fixate_focus_stats format */
    function migrateLegacyData() {
        var existing = getSessions();
        if (existing.length > 0) return; // already have new-format data

        try {
            var legacy = JSON.parse(localStorage.getItem(FOCUS_STATS_KEY) || '{}');
            var migrated = [];
            Object.keys(legacy).forEach(function(dateKey) {
                var day = legacy[dateKey];
                if (day.l && day.l.length) {
                    day.l.forEach(function(entry) {
                        migrated.push({
                            date: dateKey + 'T' + (entry.t || '12:00:00'),
                            duration: entry.m || 0,
                            mode: 'pomodoro',
                            completed: true
                        });
                    });
                }
            });
            if (migrated.length > 0) {
                saveSessions(migrated);
            }
        } catch (e) { /* ignore */ }
    }

    /* ── Stats Calculations ── */

    function dateKey(d) {
        return new Date(d).toISOString().split('T')[0];
    }

    function isToday(d) {
        return dateKey(d) === dateKey(new Date());
    }

    function isThisWeek(d) {
        var now = new Date();
        var start = new Date(now);
        start.setDate(now.getDate() - now.getDay()); // Sunday
        start.setHours(0, 0, 0, 0);
        return new Date(d) >= start;
    }

    function isThisMonth(d) {
        var now = new Date();
        var dt = new Date(d);
        return dt.getFullYear() === now.getFullYear() && dt.getMonth() === now.getMonth();
    }

    function daysBetween(a, b) {
        var msDay = 86400000;
        var da = new Date(a); da.setHours(0, 0, 0, 0);
        var db = new Date(b); db.setHours(0, 0, 0, 0);
        return Math.round((db - da) / msDay);
    }

    function computeStats() {
        var sessions = getSessions();
        var todayMin = 0, weekMin = 0, totalMin = 0, totalSessions = sessions.length;
        var activeDays = {};

        sessions.forEach(function(s) {
            var dur = s.duration || 0;
            totalMin += dur;
            if (isToday(s.date)) todayMin += dur;
            if (isThisWeek(s.date)) weekMin += dur;
            var dk = dateKey(s.date);
            if (!activeDays[dk]) activeDays[dk] = 0;
            activeDays[dk] += dur;
        });

        return {
            todayMin: Math.round(todayMin),
            weekMin: Math.round(weekMin),
            totalSessions: totalSessions,
            avgMin: totalSessions > 0 ? Math.round(totalMin / totalSessions) : 0,
            totalHours: (totalMin / 60).toFixed(1),
            totalMin: totalMin,
            activeDays: activeDays
        };
    }

    function computeStreaks() {
        var sessions = getSessions();
        if (sessions.length === 0) return { current: 0, longest: 0 };

        // Get unique days with completed focus sessions
        var daySet = {};
        sessions.forEach(function(s) {
            if (s.completed && s.duration > 0) {
                daySet[dateKey(s.date)] = true;
            }
        });
        var days = Object.keys(daySet).sort();
        if (days.length === 0) return { current: 0, longest: 0 };

        // Compute streaks
        var longest = 1, streak = 1;
        for (var i = 1; i < days.length; i++) {
            if (daysBetween(days[i - 1], days[i]) === 1) {
                streak++;
            } else {
                if (streak > longest) longest = streak;
                streak = 1;
            }
        }
        if (streak > longest) longest = streak;

        // Current streak: count backwards from today
        var today = dateKey(new Date());
        var current = 0;
        if (daySet[today]) {
            current = 1;
            var checkDate = new Date();
            while (true) {
                checkDate.setDate(checkDate.getDate() - 1);
                var ck = dateKey(checkDate);
                if (daySet[ck]) {
                    current++;
                } else {
                    break;
                }
            }
        } else {
            // Check if yesterday had a session (streak might still be active if today hasn't started)
            var yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            if (daySet[dateKey(yesterday)]) {
                current = 1;
                var checkDate2 = new Date(yesterday);
                while (true) {
                    checkDate2.setDate(checkDate2.getDate() - 1);
                    var ck2 = dateKey(checkDate2);
                    if (daySet[ck2]) {
                        current++;
                    } else {
                        break;
                    }
                }
            }
        }

        return { current: current, longest: Math.max(longest, current) };
    }

    /* ── Chart Rendering ── */

    function renderDailyChart() {
        var sessions = getSessions();
        var dailyMin = {};
        sessions.forEach(function(s) {
            var dk = dateKey(s.date);
            if (!dailyMin[dk]) dailyMin[dk] = 0;
            dailyMin[dk] += s.duration || 0;
        });

        var goal = parseInt(localStorage.getItem(DAILY_GOAL_KEY) || '120');
        var days = [];
        for (var i = 13; i >= 0; i--) {
            var d = new Date();
            d.setDate(d.getDate() - i);
            var dk = dateKey(d);
            days.push({
                label: d.toLocaleDateString('en', { weekday: 'short' }),
                min: Math.round(dailyMin[dk] || 0),
                today: i === 0,
                dateStr: dk
            });
        }

        renderBars(days, goal, 'min');
    }

    function renderWeeklyChart() {
        var sessions = getSessions();
        // Last 8 weeks
        var weeks = [];
        for (var w = 7; w >= 0; w--) {
            var weekStart = new Date();
            weekStart.setDate(weekStart.getDate() - weekStart.getDay() - (w * 7));
            weekStart.setHours(0, 0, 0, 0);
            var weekEnd = new Date(weekStart);
            weekEnd.setDate(weekEnd.getDate() + 6);
            weekEnd.setHours(23, 59, 59, 999);

            var total = 0;
            sessions.forEach(function(s) {
                var sd = new Date(s.date);
                if (sd >= weekStart && sd <= weekEnd) total += s.duration || 0;
            });

            var label = (weekStart.getMonth() + 1) + '/' + weekStart.getDate();
            weeks.push({
                label: label,
                min: Math.round(total),
                today: w === 0
            });
        }

        var weeklyGoal = parseInt(localStorage.getItem(WEEKLY_GOAL_KEY) || '840');
        renderBars(weeks, weeklyGoal, 'min');
    }

    function renderMonthlyChart() {
        var sessions = getSessions();
        var monthlyMin = {};
        sessions.forEach(function(s) {
            var d = new Date(s.date);
            var key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            if (!monthlyMin[key]) monthlyMin[key] = 0;
            monthlyMin[key] += s.duration || 0;
        });

        var months = [];
        var now = new Date();
        for (var m = 5; m >= 0; m--) {
            var md = new Date(now.getFullYear(), now.getMonth() - m, 1);
            var key = md.getFullYear() + '-' + String(md.getMonth() + 1).padStart(2, '0');
            var label = md.toLocaleDateString('en', { month: 'short' });
            months.push({
                label: label,
                min: Math.round(monthlyMin[key] || 0),
                today: m === 0
            });
        }

        // Goal: 30x daily goal per month
        var dailyGoal = parseInt(localStorage.getItem(DAILY_GOAL_KEY) || '120');
        renderBars(months, dailyGoal * 30, 'min');
    }

    function renderBars(data, goalValue, unit) {
        var chart = $('#fx-chart-enhanced');
        if (!chart) return;
        chart.innerHTML = '';

        var maxVal = Math.max(goalValue * 0.5, 1);
        data.forEach(function(d) { if (d.min > maxVal) maxVal = d.min; });

        data.forEach(function(d) {
            var col = document.createElement('div');
            col.className = 'fx-chart-col';

            var bar = document.createElement('div');
            bar.className = 'fx-chart-bar' + (d.today ? ' today' : '');
            if (d.min > 0) bar.classList.add('has-data');
            var heightPx = Math.max(2, Math.round((d.min / maxVal) * 120));
            bar.style.height = heightPx + 'px';
            bar.setAttribute('data-tooltip', d.min + ' ' + unit);

            var lbl = document.createElement('span');
            lbl.className = 'fx-chart-label';
            lbl.textContent = d.label;

            col.appendChild(bar);
            col.appendChild(lbl);
            chart.appendChild(col);
        });
    }

    /* ── Weekly Goal Ring ── */

    function updateGoalRing() {
        var sessions = getSessions();
        var weekMin = 0;
        sessions.forEach(function(s) {
            if (isThisWeek(s.date)) weekMin += s.duration || 0;
        });

        var weeklyGoal = parseInt(localStorage.getItem(WEEKLY_GOAL_KEY) || '840');
        var pct = Math.min(100, Math.round((weekMin / weeklyGoal) * 100));
        var circumference = 2 * Math.PI * 34; // r=34
        var offset = circumference - (circumference * pct / 100);

        var circle = $('#fx-goal-ring-circle');
        if (circle) {
            circle.setAttribute('stroke-dasharray', circumference.toFixed(1));
            circle.setAttribute('stroke-dashoffset', offset.toFixed(1));
        }

        var pctEl = $('#fx-goal-ring-pct');
        if (pctEl) pctEl.textContent = pct + '%';

        var titleEl = $('#fx-goal-ring-title');
        if (titleEl) {
            var hrs = (weekMin / 60).toFixed(1);
            var goalHrs = (weeklyGoal / 60).toFixed(0);
            titleEl.textContent = hrs + 'h / ' + goalHrs + 'h this week';
        }

        var subEl = $('#fx-goal-ring-sub');
        if (subEl) {
            if (pct >= 100) {
                subEl.textContent = '🎉 Goal reached! Amazing work!';
            } else if (pct >= 75) {
                subEl.textContent = 'Almost there! Keep pushing 💪';
            } else if (pct >= 50) {
                subEl.textContent = 'Halfway to your weekly goal 🎯';
            } else {
                var remaining = weeklyGoal - weekMin;
                subEl.textContent = Math.round(remaining) + ' min remaining';
            }
        }
    }

    /* ── Session History ── */

    function renderHistory() {
        var container = $('#fx-history-list');
        if (!container) return;

        var sessions = getSessions();
        if (sessions.length === 0) {
            container.innerHTML = '<div class="fx-history-empty">' +
                '<span class="fx-history-empty-icon">🎯</span>' +
                'No focus sessions yet.<br>Start a timer to begin tracking!</div>';
            return;
        }

        // Last 20, most recent first
        var recent = sessions.slice(-20).reverse();
        container.innerHTML = '';

        recent.forEach(function(s) {
            var meta = MODE_META[s.mode] || MODE_META.pomodoro;
            var d = new Date(s.date);
            var dateLabel;

            if (isToday(s.date)) {
                dateLabel = 'Today, ' + d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
            } else {
                var yesterday = new Date();
                yesterday.setDate(yesterday.getDate() - 1);
                if (dateKey(d) === dateKey(yesterday)) {
                    dateLabel = 'Yesterday, ' + d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
                } else {
                    dateLabel = d.toLocaleDateString('en', { month: 'short', day: 'numeric' }) +
                        ', ' + d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });
                }
            }

            var durLabel;
            if (s.duration >= 60) {
                var hrs = Math.floor(s.duration / 60);
                var mins = s.duration % 60;
                durLabel = hrs + 'h' + (mins > 0 ? mins + 'm' : '');
            } else {
                durLabel = s.duration + 'm';
            }

            var item = document.createElement('div');
            item.className = 'fx-history-item glass-panel-inner';
            item.innerHTML =
                '<span class="fx-history-mode-icon">' + meta.icon + '</span>' +
                '<div class="fx-history-info">' +
                    '<div class="fx-history-date">' + dateLabel + '</div>' +
                    '<div class="fx-history-mode-label">' + meta.label +
                        (s.completed ? '' : ' · incomplete') + '</div>' +
                '</div>' +
                '<span class="fx-history-dur">' + durLabel + '</span>';
            container.appendChild(item);
        });
    }

    /* ── Chart Tab Switching ── */

    function initChartTabs() {
        var tabs = $$('#fx-chart-tabs button');
        tabs.forEach(function(btn) {
            btn.addEventListener('click', function() {
                tabs.forEach(function(t) { t.classList.remove('active'); });
                btn.classList.add('active');
                var range = btn.getAttribute('data-range');
                if (range === 'daily') renderDailyChart();
                else if (range === 'weekly') renderWeeklyChart();
                else if (range === 'monthly') renderMonthlyChart();
            });
        });
    }

    /* ── Goal Input Persistence ── */

    function initGoalInputs() {
        var dailyInput = $('#fx-stats-goal-input');
        if (dailyInput) {
            dailyInput.value = localStorage.getItem(DAILY_GOAL_KEY) || '120';
            dailyInput.addEventListener('change', function() {
                localStorage.setItem(DAILY_GOAL_KEY, this.value);
                refreshAll();
            });
        }

        var weeklyInput = $('#fx-stats-weekly-goal-input');
        if (weeklyInput) {
            weeklyInput.value = localStorage.getItem(WEEKLY_GOAL_KEY) || '840';
            weeklyInput.addEventListener('change', function() {
                localStorage.setItem(WEEKLY_GOAL_KEY, this.value);
                refreshAll();
            });
        }
    }

    /* ── Master Refresh ── */

    function refreshAll() {
        var stats = computeStats();

        // Update stat cards
        var todayEl = $('#fx-stat-today');
        if (todayEl) todayEl.textContent = stats.todayMin;

        var weekEl = $('#fx-stat-week');
        if (weekEl) weekEl.textContent = stats.weekMin;

        var sessEl = $('#fx-stat-sessions');
        if (sessEl) sessEl.textContent = stats.totalSessions;

        var avgEl = $('#fx-stat-avg');
        if (avgEl) avgEl.textContent = stats.avgMin + 'm';

        // Streaks
        var streaks = computeStreaks();
        var curEl = $('#fx-streak-current');
        if (curEl) curEl.textContent = streaks.current;
        var longEl = $('#fx-streak-longest');
        if (longEl) longEl.textContent = streaks.longest;

        // Total hours
        var totalEl = $('#fx-total-hours');
        if (totalEl) totalEl.textContent = stats.totalHours;
        var totalSub = $('#fx-total-sessions-sub');
        if (totalSub) totalSub.textContent = stats.totalSessions + ' sessions';

        // Goal ring
        updateGoalRing();

        // Chart (render active tab)
        var activeTab = $('#fx-chart-tabs button.active');
        if (activeTab) {
            var range = activeTab.getAttribute('data-range');
            if (range === 'daily') renderDailyChart();
            else if (range === 'weekly') renderWeeklyChart();
            else if (range === 'monthly') renderMonthlyChart();
        } else {
            renderDailyChart();
        }

        // History
        renderHistory();
    }

    /* ── Hook into Timer Completion ── */

    function hookTimer() {
        // Monkey-patch onTimerComplete to also log to fixate_sessions
        if (typeof window.onTimerComplete === 'function') {
            var origComplete = window.onTimerComplete;
            window.onTimerComplete = function() {
                origComplete.call(this);
                logCurrentSession();
            };
        }

        // Also watch for completion overlay becoming visible
        var observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(m) {
                if (m.target.id === 'fx-completion' && m.target.classList.contains('visible')) {
                    // Session just completed — already logged via onTimerComplete hook
                }
            });
        });
        var completionEl = document.getElementById('fx-completion');
        if (completionEl) {
            observer.observe(completionEl, { attributes: true, attributeFilter: ['class'] });
        }
    }

    function logCurrentSession() {
        // Get duration from timer object
        var duration = 0;
        var mode = 'pomodoro';

        if (typeof timer !== 'undefined') {
            // timer._totalDur is in ms
            duration = Math.round((timer._totalDur || 0) / 60000);
            mode = timer.mode || 'pomodoro';
            // Don't log break sessions
            if (timer.isBreak) return;
        }

        if (duration <= 0) return;

        addSession(duration, mode, true);
        refreshAll();
    }

    /* ── Public API ── */

    window.FixateStats = {
        refresh: refreshAll,
        addSession: addSession,
        getSessions: getSessions,
        computeStats: computeStats,
        computeStreaks: computeStreaks
    };

    /* ── Initialization ── */

    function init() {
        migrateLegacyData();
        initChartTabs();
        initGoalInputs();
        hookTimer();
        refreshAll();
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Also refresh when the stats panel is opened
    var panelStats = document.getElementById('panel-stats');
    if (panelStats) {
        var panelObserver = new MutationObserver(function(mutations) {
            mutations.forEach(function(m) {
                if (m.target.classList.contains('open')) {
                    refreshAll();
                }
            });
        });
        panelObserver.observe(panelStats, { attributes: true, attributeFilter: ['class'] });
    }

})();
