// Shared navigation for long pages; publication headings stay in their owning body.
(function () {
    const root = document.documentElement;
    const menu = document.querySelector('.second-menu-container');
    const topButton = document.querySelector('[data-back-to-top]');
    const bottomMenu = document.querySelector('.mobile-bottom-nav');
    const consent = document.querySelector('[data-cookie-consent]');
    const body = document.querySelector('.site-article-body');
    const wide = window.matchMedia('(min-width: 1400px)');
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let toc, details, links = [], headings = [], queued = false;

    if (body) {
        headings = Array.from(body.querySelectorAll('h2, h3')).filter(h => h.textContent.trim());
        if (headings.length >= 3) {
            toc = document.createElement('nav');
            toc.className = 'publication-toc';
            toc.setAttribute('aria-label', 'Зміст публікації');
            details = document.createElement('details');
            const summary = document.createElement('summary');
            summary.textContent = 'Зміст публікації';
            details.append(summary);
            const list = document.createElement('ul');
            headings.forEach((heading, index) => {
                if (!heading.id) {
                    let id = `article-section-${index + 1}`;
                    while (document.getElementById(id)) id += '-section';
                    heading.id = id;
                }
                const item = document.createElement('li');
                item.classList.toggle('publication-toc__subsection', heading.tagName === 'H3');
                const link = document.createElement('a');
                link.textContent = heading.textContent.trim();
                link.href = '#' + encodeURIComponent(heading.id);
                link.addEventListener('click', event => {
                    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
                    event.preventDefault();
                    if (!wide.matches) details.open = false;
                    history.pushState(null, '', link.hash);
                    goTo(heading);
                });
                item.append(link);
                list.append(item);
                links.push(link);
            });
            details.append(list);
            toc.append(details);
            body.before(toc);
            body.parentElement.classList.add('publication-reading-section');
            const adapt = () => { details.open = wide.matches; schedule(); };
            wide.addEventListener('change', adapt);
            adapt();
            details.addEventListener('keydown', event => {
                if (event.key === 'Escape' && !wide.matches) {
                    details.open = false;
                    summary.focus({preventScroll: true});
                }
            });
        }
    }

    function offset() {
        return (menu ? menu.getBoundingClientRect().height : 0) + 16;
    }

    let animation;
    function stopScroll() { cancelAnimationFrame(animation); }
    ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(event =>
        window.addEventListener(event, stopScroll, {passive: true}));
    function scrollToPosition(top, behavior) {
        stopScroll();
        if (behavior === 'instant' || reducedMotion.matches) {
            window.scrollTo({top, behavior: 'instant'});
            return;
        }
        const start = window.scrollY;
        const started = performance.now();
        function frame(now) {
            const progress = Math.min(1, (now - started) / 350);
            const eased = 1 - Math.pow(1 - progress, 3);
            window.scrollTo({top: start + (top - start) * eased, behavior: 'instant'});
            if (progress < 1) animation = requestAnimationFrame(frame);
        }
        animation = requestAnimationFrame(frame);
    }

    function goTo(target, behavior = reducedMotion.matches ? 'instant' : 'smooth') {
        const extra = toc && !wide.matches ? details.querySelector('summary').getBoundingClientRect().height + 12 : 0;
        target.setAttribute('tabindex', '-1');
        target.focus({preventScroll: true});
        scrollToPosition(Math.max(0, window.scrollY + target.getBoundingClientRect().top - offset() - extra), behavior);
    }

    function update() {
        queued = false;
        const gap = offset();
        root.style.setProperty('--reading-top', `${gap}px`);
        if (topButton) {
            // Hide while consent or a modal occupies the foreground.
            topButton.hidden = window.scrollY < window.innerHeight * 2 ||
                Boolean(consent && !consent.hidden) || document.body.classList.contains('modal-open');
            const bottom = bottomMenu ? bottomMenu.getBoundingClientRect().height : 0;
            topButton.style.bottom = `calc(${bottom + 16}px + env(safe-area-inset-bottom))`;
        }
        if (toc) {
            let current = -1;
            const threshold = gap + (wide.matches ? 0 : details.querySelector('summary').getBoundingClientRect().height) + 24;
            headings.forEach((heading, index) => {
                if (heading.getBoundingClientRect().top <= threshold) current = index;
            });
            links.forEach((link, index) => {
                if (index === current) link.setAttribute('aria-current', 'location');
                else link.removeAttribute('aria-current');
            });
        }
    }
    function schedule() {
        if (!queued) { queued = true; requestAnimationFrame(update); }
    }
    if (topButton) topButton.addEventListener('click', () => {
        const target = document.querySelector('header') || document.body;
        target.setAttribute('tabindex', '-1');
        target.focus({preventScroll: true});
        scrollToPosition(0, reducedMotion.matches ? 'instant' : 'smooth');
    });
    window.addEventListener('scroll', schedule, {passive: true});
    window.addEventListener('resize', schedule);
    if (window.ResizeObserver) {
        const observer = new ResizeObserver(schedule);
        [menu, bottomMenu, document.body].filter(Boolean).forEach(node => observer.observe(node));
    }
    if (consent) new MutationObserver(schedule).observe(consent, {attributes: true, attributeFilter: ['hidden']});
    new MutationObserver(schedule).observe(document.body, {attributes: true, attributeFilter: ['class']});
    function restoreHash() {
        let id;
        try { id = decodeURIComponent(window.location.hash.slice(1)); } catch (_) { return; }
        const heading = headings.find(h => h.id === id);
        if (heading && toc) goTo(heading, 'instant');
    }
    window.addEventListener('hashchange', restoreHash);
    window.addEventListener('load', () => { restoreHash(); schedule(); });
    update();
}());
