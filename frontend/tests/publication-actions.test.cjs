const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/js/detail.js'), 'utf8').replace(/^import .*;\n/, '');

function setup({navigator = {}, fetch = async () => ({ok: true, json: async () => ({code: 200})})} = {}) {
    const nodes = new Map();
    function element(selector) {
        if (!nodes.has(selector)) nodes.set(selector, {
            hidden: true, disabled: false, textContent: '', dataset: {}, attributes: {}, handlers: {},
            addEventListener(event, handler) { this.handlers[event] = handler; },
            setAttribute(name, value) { this.attributes[name] = value; },
            focus() { this.focused = true; }, select() { this.selected = true; }
        });
        return nodes.get(selector);
    }
    const actions = element('[data-publication-actions]');
    actions.dataset = {postId: '460', title: 'Голден Делішес', voteUrl: '/api/post/useful/',
        voteLoading: 'loading', voteError: 'error', voteSuccess: 'saved', copySuccess: 'copied'};
    actions.querySelector = element;
    const votes = ['true', 'false'].map(value => {
        const node = element(`[data-vote="${value}"]`);
        node.dataset.vote = value;
        node.attributes['aria-pressed'] = 'false';
        return node;
    });
    actions.querySelectorAll = () => votes;
    const canonical = 'https://agromega.in.ua/yabluni/sorty-yablun/holden-delishes-460.html';
    element('link[rel="canonical"]').href = canonical;
    const calls = [];
    vm.runInNewContext(source, {
        document: {cookie: 'csrftoken=test-token', querySelector: element, querySelectorAll: () => [],
            addEventListener(event, callback) { callback(); }},
        navigator, window: {setTimeout, clearTimeout}, AbortController, console,
        fetch: async (...args) => { calls.push(args); return fetch(...args); },
        XMLHttpRequest: class { open() {} setRequestHeader() {} send() {} }
    });
    return {element, votes, calls, canonical};
}

test('native share receives canonical and title; cancellation is silent', async () => {
    let shared;
    const page = setup({navigator: {share: async data => { shared = data; throw {name: 'AbortError'}; }}});
    await page.element('[data-share]').handlers.click();
    assert.equal(shared.url, page.canonical);
    assert.equal(shared.title, 'Голден Делішес');
    assert.equal(page.element('[data-share-fallback]').hidden, true);
    assert.equal(page.element('[data-share-status]').textContent, '');
    assert.equal(page.element('[data-share]').disabled, false);
});

test('unsupported share and native failure offer copying; clipboard failure exposes selectable URL', async () => {
    for (const navigator of [{}, {share: async () => { throw {name: 'NotAllowedError'}; }}]) {
        const page = setup({navigator});
        await page.element('[data-share]').handlers.click();
        assert.equal(page.element('[data-share-fallback]').hidden, false);
        await page.element('[data-copy]').handlers.click();
        assert.equal(page.element('[data-manual-copy]').hidden, false);
        assert.equal(page.element('[data-share-url]').value, page.canonical);
        assert.equal(page.element('[data-share-url]').selected, true);
        assert.equal(page.element('[data-share-status]').textContent, '');
    }
});

test('successful copy announces confirmation', async () => {
    let copied;
    const page = setup({navigator: {clipboard: {writeText: async value => { copied = value; }}}});
    await page.element('[data-copy]').handlers.click();
    assert.equal(copied, page.canonical);
    assert.equal(page.element('[data-share-status]').textContent, 'copied');
});

test('pending and saved votes prevent duplicates and preserve payload and CSRF', async () => {
    let resolve;
    const page = setup({fetch: () => new Promise(done => { resolve = done; })});
    const pending = page.votes[0].handlers.click();
    assert.equal(page.votes.every(button => button.disabled), true);
    await page.votes[1].handlers.click();
    assert.equal(page.calls.length, 1);
    resolve({ok: true, json: async () => ({code: 200})});
    await pending;
    await page.votes[0].handlers.click();
    assert.equal(page.calls.length, 1);
    assert.equal(page.calls[0][1].headers['X-CSRFToken'], 'test-token');
    assert.deepEqual(JSON.parse(page.calls[0][1].body), {fingerprint: 'fingerprint', post_id: '460', is_useful: true});
    assert.equal(page.votes[0].attributes['aria-pressed'], 'true');
    assert.equal(page.votes[1].attributes['aria-pressed'], 'false');
    assert.equal(page.element('[data-vote-status]').textContent, 'saved');
});

test('HTTP, network and invalid success responses never select a vote; retry remains possible', async () => {
    for (const fetch of [async () => ({ok: false}), async () => { throw new Error('offline'); },
        async () => ({ok: true, json: async () => ({code: 400})})]) {
        const page = setup({fetch});
        await page.votes[1].handlers.click();
        assert.equal(page.element('[data-vote-status]').textContent, 'error');
        assert.equal(page.votes.every(button => !button.disabled && button.attributes['aria-pressed'] === 'false'), true);
        await page.votes[1].handlers.click();
        assert.equal(page.calls.length, 2);
    }
});

test('analytics respects current and stored consent, including revocation after storage fails', () => {
    const base = fs.readFileSync(path.join(__dirname, '../../templates/base.html'), 'utf8');
    const start = base.indexOf('    (function () {\n        const config = window.agromegaConsentConfig');
    const end = base.indexOf('    }());', start) + '    }());'.length;
    let stored = null;
    let failWrites = false;
    const events = [];
    const handlers = {};
    const banner = {querySelector: selector => ({addEventListener: (event, handler) => { handlers[selector] = handler; }})};
    const window = {
        agromegaConsentConfig: {analytics: {enabled: true, measurementId: 'test'}},
        localStorage: {
            getItem: () => stored,
            setItem: (key, value) => { if (failWrites) throw new Error('blocked'); stored = value; }
        },
        gtag: (...args) => events.push(args)
    };
    vm.runInNewContext(base.slice(start, end), {
        window, document: {
            querySelector: selector => selector === '[data-cookie-consent]' ? banner : null,
            querySelectorAll: () => [], getElementById: () => true
        }
    });
    window.agromegaTrackEvent('agromarket_click', {post_id: 460});
    assert.equal(events.length, 0);
    handlers['[data-cookie-accept-all]']();
    window.agromegaTrackEvent('agromarket_click', {post_id: 460});
    assert.equal(events.filter(event => event[0] === 'event').length, 1);
    failWrites = true;
    handlers['[data-cookie-reject]']();
    window.agromegaTrackEvent('agromarket_click', {post_id: 460});
    assert.equal(events.filter(event => event[0] === 'event').length, 1);
});
