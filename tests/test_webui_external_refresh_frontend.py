from pathlib import Path


SESSIONS_JS = Path("static/sessions.js").read_text(encoding="utf-8")
UI_JS = Path("static/ui.js").read_text(encoding="utf-8")


def test_load_session_supports_force_reload_for_external_refresh():
    assert "async function loadSession(sid)" in SESSIONS_JS
    assert "const opts = arguments[1] || {};" in SESSIONS_JS
    assert "const forceReload = !!opts.force" in SESSIONS_JS
    assert "if(currentSid===sid && !forceReload) return;" in SESSIONS_JS
    assert "loadSession(sid, {force:true" in SESSIONS_JS


def test_active_session_external_refresh_uses_metadata_then_force_reload():
    assert "function ensureActiveSessionExternalRefreshPoll()" in SESSIONS_JS
    assert "async function refreshActiveSessionIfExternallyUpdated(reason)" in SESSIONS_JS
    assert "messages=0&resolve_model=0" in SESSIONS_JS
    assert "remoteCount > localCount || remoteLast > localLast" in SESSIONS_JS
    assert "if(S.busy || S.activeStreamId) return;" in SESSIONS_JS
    assert "document.hidden" in SESSIONS_JS


def test_active_session_external_refresh_has_focus_and_visibility_hooks():
    assert "visibilitychange" in SESSIONS_JS
    assert "window.addEventListener('focus'" in SESSIONS_JS
    assert "ensureActiveSessionExternalRefreshPoll();" in SESSIONS_JS


def test_session_list_external_refresh_uses_sse_invalidation_not_polling():
    """New sessions should refresh the sidebar from server invalidation events."""
    assert "async function refreshSessionList(reason='manual', opts={})" in SESSIONS_JS
    assert "function ensureSessionEventsSSE()" in SESSIONS_JS
    assert "new EventSource('api/sessions/events')" in SESSIONS_JS
    assert "addEventListener('sessions_changed'" in SESSIONS_JS
    assert "function _scheduleSessionEventsRefresh(reason)" in SESSIONS_JS
    assert "_sessionEventsNeedsRefreshOnOpen = true" in SESSIONS_JS
    assert "void refreshSessionList('reconnect')" in SESSIONS_JS
    assert "renderSessionList({deferWhileInteracting:!force})" in SESSIONS_JS
    assert "const refreshActive = !!(opts && opts.refreshActive)" in SESSIONS_JS
    assert "if(refreshActive) await refreshActiveSessionIfExternallyUpdated(reason||'session-list')" in SESSIONS_JS
    assert "_sessionListRefreshPendingReason = reason || 'session-list'" in SESSIONS_JS
    assert "if(pendingReason) _scheduleSessionEventsRefresh(pendingReason)" in SESSIONS_JS
    assert "ensureSessionEventsSSE();" in SESSIONS_JS
    assert "document._hermesSessionEventsVisibilityHook" in SESSIONS_JS
    ensure_fn = SESSIONS_JS[SESSIONS_JS.find("function ensureSessionEventsSSE()") :]
    assert ensure_fn.find("document._hermesSessionEventsVisibilityHook") < ensure_fn.find("document.hidden) return")
    assert "_sessionListExternalRefreshMs" not in SESSIONS_JS


def test_pwa_pull_to_refresh_refreshes_session_list_not_page_when_available():
    assert "window.refreshSessionList('pull', {force:true, refreshActive:true})" in UI_JS
    assert "Promise.resolve(window.refreshSessionList('pull', {force:true, refreshActive:true})).catch(()=>{}).finally(_ptrReset)" in UI_JS


def test_force_reload_clears_stale_blocking_prompts_immediately():
    """External refresh should not leave old approval/clarify modals blocking the composer.

    hideApprovalCard() and hideClarifyCard() defer hiding for their minimum-visible
    timers unless force=true. That is correct for active streams, but when a
    same-session external state.db update triggers loadSession(..., {force:true}),
    the session has completed elsewhere and stale prompts should be removed now.
    """
    assert "hideApprovalCard(forceReload)" in SESSIONS_JS
    assert "hideClarifyCard(forceReload, forceReload?'external-refresh':'dismissed')" in SESSIONS_JS


def test_same_session_force_reload_preserves_non_empty_composer_input():
    """A slow same-session refresh must not roll back text typed meanwhile.

    The active-session refresh path can finish seconds after it started. If the
    user kept typing, restoring the server draft at the end of that load would
    replace newer local input with an older debounced draft.
    """
    assert "function _restoreComposerDraft(draft, targetSid, opts={})" in SESSIONS_JS
    assert "const preserveActiveInput = !!(opts && opts.preserveActiveInput);" in SESSIONS_JS
    assert "if (preserveActiveInput && current && current !== text) return;" in SESSIONS_JS
    assert "_restoreComposerDraft(_draft, sid, {preserveActiveInput:currentSid===sid&&forceReload});" in SESSIONS_JS


def test_same_session_force_reload_captures_loaded_width_before_clear():
    """Reload-width hint must be captured before loadSession clears messages.

    PR #3313's _pendingCarryForwardSnapshot must remain in the same block; it
    preserves ephemeral fields, while this hint preserves the fetched transcript
    width for the next _ensureMessagesLoaded() call.
    """
    body = SESSIONS_JS[SESSIONS_JS.index("async function loadSession(sid)") : SESSIONS_JS.index("// Phase 1: Load metadata only")]
    hint_idx = body.index("_captureSameSessionForceReloadHint(sid)")
    carry_idx = body.index("_pendingCarryForwardSnapshot =")
    clear_idx = body.index("S.messages = [];")

    assert "let _sameSessionForceReloadHint = null" in SESSIONS_JS
    assert "function _captureSameSessionForceReloadHint(sid)" in SESSIONS_JS
    assert hint_idx < clear_idx
    assert carry_idx < clear_idx
    assert "loadedRenderableCount:_sameSessionLoadedRenderableCount()" in SESSIONS_JS
    assert "wasTruncated:!!_messagesTruncated" in SESSIONS_JS


def test_same_session_force_reload_uses_dynamic_reload_limit_and_clears_hint():
    body = SESSIONS_JS[SESSIONS_JS.index("async function _ensureMessagesLoaded") : SESSIONS_JS.index("function _messageComparableText")]

    assert "function _messageReloadLimitForSession(sid)" in SESSIONS_JS
    assert "const reloadLimit=_messageReloadLimitForSession(sid);" in body
    assert "const reloadLimitParam=reloadLimit===null?'':`&msg_limit=${encodeURIComponent(reloadLimit||_INITIAL_MSG_LIMIT)}`;" in body
    assert "messages=1&resolve_model=0${reloadLimitParam}" in body
    assert "_clearSameSessionForceReloadHint(sid);" in body
    assert "loadedWidth+appended" in SESSIONS_JS
    assert "if(!hint.wasTruncated) return null;" in SESSIONS_JS


def test_same_session_force_reload_preserves_scroll_without_changing_session_switch_default():
    body = SESSIONS_JS[SESSIONS_JS.index("async function loadSession(sid)") : SESSIONS_JS.index("// Sync context usage indicator")]
    idle_branch = body[body.index("}else{\n      S.busy=false;") :]

    assert "if(currentSid===sid&&forceReload){syncTopbar();renderMessages({preserveScroll:true});}" in idle_branch
    assert "else{syncTopbar();renderMessages();}" in idle_branch


def test_same_session_force_reload_does_not_reset_scroll_pin_state():
    """The preserve-scroll render relies on the user's existing pin state.

    Same-session external refresh must not call the session-switch scroll reset;
    otherwise an unpinned reader is marked pinned before renderMessages() can
    restore the captured viewport.
    """
    body = SESSIONS_JS[SESSIONS_JS.index("async function loadSession(sid)") : SESSIONS_JS.index("// Sync context usage indicator")]

    assert "currentSid !== sid && typeof window !== 'undefined' && typeof window._resetScrollDirectionTracker === 'function'" in body
    assert "currentSid===sid&&forceReload" in body
