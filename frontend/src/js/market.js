const picker = document.querySelector('[data-market-picker]');
if (picker) {
    const { category, variety, region, hub } = picker.elements;
    let pending;

    category.addEventListener('change', refreshVarieties);
    region.addEventListener('change', refreshVarieties);

    async function refreshVarieties() {
        if (pending) pending.abort();
        const controller = new AbortController();
        pending = controller;
        const previous = variety.value;
        variety.replaceChildren(new Option('Усі сорти', ''));
        variety.disabled = true;
        if (!category.value) return;

        const url = new URL(picker.dataset.optionsUrl, location.origin);
        url.searchParams.set('category', category.value);
        if (region.value) url.searchParams.set('region', region.value);
        if (hub) url.searchParams.set('hub', hub.value);

        try {
            const response = await fetch(url, { signal: controller.signal });
            if (!response.ok) return;
            const { varieties } = await response.json();
            if (pending !== controller) return;
            variety.append(...varieties.map(item => new Option(item.title, item.id)));
            if (varieties.some(item => String(item.id) === previous)) variety.value = previous;
        } catch (error) {
            // Submitting the category still works if the options request fails.
        } finally {
            if (pending === controller) variety.disabled = false;
        }
    }
}
