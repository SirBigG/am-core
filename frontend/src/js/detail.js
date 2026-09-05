import 'bootstrap/js/dist/dropdown';

function getCookie(name) {
    let matches = document.cookie.match(new RegExp(
        "(?:^|; )" + name.replace(/([\.$?*|{}\(\)\[\]\\\/\+^])/g, '\\$1') + "=([^;]*)"
    ));
    return matches ? decodeURIComponent(matches[1]) : undefined;
}

function post_view(post_id) {
    let http = new XMLHttpRequest();
    http.open('POST', '/api/post/view/', true);
    http.setRequestHeader("X-CSRFToken", getCookie("csrftoken"),);
    http.setRequestHeader('Content-type', 'application/json; charset=utf-8');
    http.onreadystatechange = function () {
        if (http.readyState === 4 && http.status === 200) {
            console.log("success view");
        } else {
            console.log(http.status);
        }
    }
    http.send(JSON.stringify({
        "fingerprint": "fingerprint",
        "post_id": post_id
    }));
}

document.addEventListener("DOMContentLoaded", function () {
    const actions = document.querySelector('[data-publication-actions]');
    if (!actions) return;
    const postId = actions.dataset.postId;
    const canonical = document.querySelector('link[rel="canonical"]');
    const shareUrl = canonical ? canonical.href : window.location.href.split(/[?#]/)[0];
    const shareButton = actions.querySelector('[data-share]');
    const fallback = actions.querySelector('[data-share-fallback]');
    const copyButton = actions.querySelector('[data-copy]');
    const shareStatus = actions.querySelector('[data-share-status]');
    const input = actions.querySelector('[data-share-url]');
    input.value = shareUrl;
    shareButton.hidden = false;

    function showFallback() {
        fallback.hidden = false;
        copyButton.focus();
    }

    shareButton.addEventListener('click', async function () {
        shareStatus.textContent = '';
        if (typeof navigator.share !== 'function') {
            showFallback();
            return;
        }
        shareButton.disabled = true;
        try {
            await navigator.share({title: actions.dataset.title, url: shareUrl});
        } catch (error) {
            if (error.name !== 'AbortError') showFallback();
        } finally {
            shareButton.disabled = false;
        }
    });

    copyButton.addEventListener('click', async function () {
        copyButton.disabled = true;
        shareStatus.textContent = '';
        try {
            await navigator.clipboard.writeText(shareUrl);
            shareStatus.textContent = actions.dataset.copySuccess;
        } catch (error) {
            actions.querySelector('[data-manual-copy]').hidden = false;
            input.focus();
            input.select();
        } finally {
            copyButton.disabled = false;
        }
    });

    const voteControls = actions.querySelector('[data-vote-controls]');
    const voteButtons = Array.from(actions.querySelectorAll('[data-vote]'));
    const voteStatus = actions.querySelector('[data-vote-status]');
    voteControls.hidden = false;
    let votePending = false;
    let voteSaved = false;
    voteButtons.forEach(button => button.addEventListener('click', async function () {
        if (votePending || voteSaved) return;
        votePending = true;
        voteButtons.forEach(item => { item.disabled = true; });
        voteControls.setAttribute('aria-busy', 'true');
        voteStatus.textContent = actions.dataset.voteLoading;
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 15000);
        try {
            const response = await fetch(actions.dataset.voteUrl, {
                method: 'POST',
                credentials: 'same-origin',
                signal: controller.signal,
                headers: {
                    'X-CSRFToken': getCookie('csrftoken') || '',
                    'Content-Type': 'application/json; charset=utf-8'
                },
                // Preserve the existing anonymous payload and server deduplication policy.
                body: JSON.stringify({fingerprint: 'fingerprint', post_id: postId, is_useful: button.dataset.vote === 'true'})
            });
            if (!response.ok || (await response.json()).code !== 200) throw new Error('Vote failed');
            voteSaved = true;
            button.setAttribute('aria-pressed', 'true');
            voteStatus.textContent = actions.dataset.voteSuccess;
        } catch (error) {
            voteStatus.textContent = actions.dataset.voteError;
        } finally {
            window.clearTimeout(timeout);
            votePending = false;
            voteControls.setAttribute('aria-busy', 'false');
            voteButtons.forEach(item => { item.disabled = voteSaved; });
        }
    }));

    document.querySelectorAll('[data-market-link]').forEach(link => {
        link.addEventListener('click', function () {
            if (typeof window.agromegaTrackEvent === 'function') {
                window.agromegaTrackEvent('agromarket_click', {
                    post_id: Number(link.dataset.postId),
                    entity_id: Number(link.dataset.entityId),
                    placement: link.dataset.placement
                });
            }
        });
    });
    post_view(postId);
});
