const tabs = document.querySelector('.potato-tabs');
const links = [...tabs.querySelectorAll('a')];
const sections = links.map(link => document.querySelector(link.hash));

function highlightSection() {
    const threshold = tabs.getBoundingClientRect().bottom + 90;
    let index = 0;
    sections.forEach((section, position) => {
        if (section.getBoundingClientRect().top <= threshold) index = position;
    });
    links.forEach((link, position) => {
        if (index === position) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
    });
}

window.addEventListener('scroll', highlightSection, { passive: true });
window.addEventListener('resize', highlightSection);
highlightSection();

const filterToggle = document.querySelector('#potato-filter-toggle');
const filterPanel = document.querySelector('#potato-filter-panel');
const filterSummary = filterPanel.querySelector('summary');

function syncFilterToggle() {
    filterToggle.setAttribute('aria-expanded', String(filterPanel.open));
    filterPanel.hidden = !filterPanel.open;
}

filterToggle.addEventListener('click', () => {
    filterPanel.open = !filterPanel.open;
    syncFilterToggle();
});
filterSummary.hidden = true;
syncFilterToggle();
filterToggle.hidden = false;

const priceTools = document.querySelector('.potato-price-tools');
if (priceTools) {
    const groups = [...document.querySelectorAll('[data-potato-price-group]')];
    const selector = priceTools.querySelector('select');
    const sort = priceTools.querySelector('button');
    let ascending = true;

    function showSelectedGroup() {
        groups.forEach(group => {
            group.hidden = group.dataset.potatoPriceGroup !== selector.value;
        });
    }

    selector.addEventListener('change', showSelectedGroup);
    sort.addEventListener('click', () => {
        groups.forEach(group => {
            const body = group.querySelector('tbody');
            const rows = [...body.rows];
            rows.sort((a, b) => a.dataset.currency.localeCompare(b.dataset.currency) ||
                (Number(a.dataset.price) - Number(b.dataset.price)) * (ascending ? 1 : -1));
            body.append(...rows);
            group.querySelector('[data-price-heading]').setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
        });
        sort.textContent = ascending ? 'Ціна продавця ↑' : 'Ціна продавця ↓';
        ascending = !ascending;
    });
    groups.forEach(group => {
        group.open = true;
        group.querySelector('summary').hidden = true;
    });
    showSelectedGroup();
    priceTools.hidden = false;
}
