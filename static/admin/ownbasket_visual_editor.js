(function () {
    const ALL_PACK_SLUG = 'all-fonts';
    const ALL_DESIGNER_LIBRARY_SLUG = 'all-designer-fonts';
    let activeSearchDropdown = null;
    const fontApiCache = new Map();
    const loadedGoogleFontFamilies = new Set();

    function createElement(tagName, className, textContent) {
        const element = document.createElement(tagName);
        if (className) {
            element.className = className;
        }
        if (typeof textContent === 'string') {
            element.textContent = textContent;
        }
        return element;
    }

    function parseJson(value, fallback) {
        try {
            return JSON.parse(value);
        } catch (error) {
            return fallback;
        }
    }

    function normalizeHex(value) {
        const raw = String(value || '').trim();
        const sixHex = raw.startsWith('#') ? raw : '#' + raw;
        return /^#[0-9a-fA-F]{6}$/.test(sixHex) ? sixHex.toUpperCase() : '';
    }

    function parseSimpleSize(value) {
        const match = String(value || '').trim().match(/^(-?\d*\.?\d+)(px|rem|em|%|vw|vh)$/);
        if (!match) {
            return null;
        }
        return {
            number: match[1],
            unit: match[2],
        };
    }

    function parsePadding(value) {
        const tokens = String(value || '').trim().split(/\s+/).filter(Boolean);
        if (!tokens.length) {
            return null;
        }
        const parsed = tokens.map(function (token) {
            return token.match(/^(-?\d*\.?\d+)(px|rem|em|%|vw|vh)$/);
        });
        if (parsed.some(function (item) { return !item; })) {
            return null;
        }

        const units = new Set(parsed.map(function (item) { return item[2]; }));
        if (units.size !== 1) {
            return null;
        }

        const values = parsed.map(function (item) { return item[1]; });
        while (values.length < 4) {
            if (values.length === 1) {
                values.push(values[0], values[0], values[0]);
            } else if (values.length === 2) {
                values.push(values[0], values[1]);
            } else if (values.length === 3) {
                values.push(values[1]);
            }
        }

        return {
            values: values.slice(0, 4),
            unit: parsed[0][2],
        };
    }

    function setHiddenState(element, shouldHide) {
        if (!element) {
            return;
        }
        element.style.display = shouldHide ? 'none' : '';
    }

    function setActiveSearchDropdown(controller) {
        if (activeSearchDropdown && activeSearchDropdown !== controller) {
            activeSearchDropdown.close({ restoreFocus: false });
        }
        activeSearchDropdown = controller || null;
    }

    function clearActiveSearchDropdown(controller) {
        if (!controller || activeSearchDropdown === controller) {
            activeSearchDropdown = null;
        }
    }

    function buildGoogleFontsUrl(families) {
        const filteredFamilies = families.filter(Boolean);
        if (!filteredFamilies.length) {
            return '';
        }
        const params = filteredFamilies.map(function (family) {
            return 'family=' + encodeURIComponent(family).replace(/%20/g, '+');
        }).join('&');
        return 'https://fonts.googleapis.com/css2?' + params + '&display=swap';
    }

    function loadGoogleFontFamilies(families) {
        const uniqueFamilies = Array.from(new Set((families || []).filter(function (family) {
            return family && !loadedGoogleFontFamilies.has(family);
        })));

        if (!uniqueFamilies.length) {
            return;
        }

        const chunkSize = 12;
        for (let index = 0; index < uniqueFamilies.length; index += chunkSize) {
            const chunk = uniqueFamilies.slice(index, index + chunkSize);
            const href = buildGoogleFontsUrl(chunk);
            if (!href) {
                continue;
            }
            const link = createElement('link');
            link.rel = 'stylesheet';
            link.href = href;
            document.head.appendChild(link);
            chunk.forEach(function (family) {
                loadedGoogleFontFamilies.add(family);
            });
        }
    }

    function enhanceColorField(input) {
        if (!input || input.dataset.veEnhanced === 'true') {
            return;
        }
        input.dataset.veEnhanced = 'true';

        const shell = createElement('div', 've-control-shell');
        const colorShell = createElement('div', 've-color-shell');
        const colorPicker = createElement('input');
        const preview = createElement('span', 've-color-preview');

        colorPicker.type = 'color';
        colorPicker.className = 've-builder-input';
        colorPicker.value = normalizeHex(input.value) || '#FFB800';
        preview.style.backgroundColor = colorPicker.value;

        input.parentNode.insertBefore(shell, input);
        shell.appendChild(colorShell);
        colorShell.appendChild(colorPicker);
        colorShell.appendChild(input);
        colorShell.appendChild(preview);

        function syncFromHex() {
            const normalized = normalizeHex(input.value);
            if (normalized) {
                colorPicker.value = normalized;
                preview.style.backgroundColor = normalized;
                input.value = normalized;
            }
        }

        function syncFromPicker() {
            input.value = colorPicker.value.toUpperCase();
            preview.style.backgroundColor = colorPicker.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        colorPicker.addEventListener('input', syncFromPicker);
        input.addEventListener('input', syncFromHex);
        syncFromHex();
    }

    function enhanceSearchableSelect(select) {
        if (!select || select.dataset.veEnhanced === 'true') {
            return;
        }
        select.dataset.veEnhanced = 'true';
        const dropdownType = select.dataset.dropdown || 'native-select';
        const isFontPreview = select.dataset.fontPreview === 'true';
        const isFontPicker = dropdownType === 'font-picker' && select.dataset.fontPicker === 'true';
        const initialFontEntries = isFontPicker ? parseJson(select.dataset.fontOptions || '[]', []) : getNativeSelectEntries(select);
        const fontPacks = isFontPicker ? parseJson(select.dataset.fontPacks || '[]', []) : [];
        const designerFontLibraries = isFontPicker ? parseJson(select.dataset.designerFontLibraries || '[]', []) : [];
        const fontApiUrl = select.dataset.fontApiUrl || '';
        const recentStorageKey = select.dataset.fontRecentKey || 'ownbasket-recent-fonts';
        const favoriteStorageKey = select.dataset.fontFavoritesKey || 'ownbasket-favorite-fonts';
        const shellClass = isFontPreview ? 've-search-shell ve-search-shell--font' : 've-search-shell';
        const shell = createElement('div', shellClass);
        const controlsRow = createElement('div', isFontPicker ? 've-search-controls ve-search-controls--font-picker' : 've-search-controls');
        const triggerWrap = createElement('div', 've-search-trigger-wrap');
        const packWrap = createElement('div', 've-font-pack-wrap');
        const packLabel = createElement('label', 've-font-pack-label', 'Font Packs');
        const packSelect = createElement('select', 've-font-pack-select');
        const designerWrap = createElement('div', 've-font-pack-wrap');
        const designerLabel = createElement('label', 've-font-pack-label', 'Designer Font Library');
        const designerSelect = createElement('select', 've-font-pack-select');
        const trigger = createElement('button', 've-search-trigger');
        const triggerLabel = createElement('span', 've-search-trigger__label');
        const triggerMeta = createElement(
            'span',
            've-search-trigger__meta',
            isFontPreview ? 'Live font preview' : 'Search and select'
        );
        const previewCard = createElement('div', 've-font-preview-card');
        const previewCardBadge = createElement('div', 've-font-preview-card__badge', 'Live Preview');
        const previewCardName = createElement('div', 've-font-preview-card__name', 'Select a font');
        const previewCardMeta = createElement('div', 've-font-preview-card__meta', 'Typography preview');
        const previewCardLineUpper = createElement('div', 've-font-preview-card__line', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ');
        const previewCardLineLower = createElement('div', 've-font-preview-card__line', 'abcdefghijklmnopqrstuvwxyz');
        const previewCardLineNumbers = createElement('div', 've-font-preview-card__line', '1234567890');
        const previewCardSentence = createElement('div', 've-font-preview-card__sentence', 'The quick brown fox jumps over the lazy dog.');
        const dropdown = createElement('div', 've-search-dropdown');
        const toolbar = createElement('div', 've-search-toolbar');
        const search = createElement('input', 've-search-input');
        const closeButton = createElement('button', 've-search-close', 'Close');
        const favoriteWrap = createElement('div', 've-search-favorites');
        const favoriteHeading = createElement('div', 've-search-section-heading', 'Favorites');
        const favoriteList = createElement('div', 've-search-favorite-list');
        const recentWrap = createElement('div', 've-search-recent');
        const recentHeading = createElement('div', 've-search-section-heading', 'Recently used');
        const recentList = createElement('div', 've-search-recent-list');
        const optionsWrap = createElement('div', 've-search-options');
        const emptyState = createElement('div', 've-search-empty', 'No fonts available in this category.');
        const optionButtons = [];
        let metadataByValue = {};
        let currentEntries = initialFontEntries.slice();
        let dropdownMounted = false;
        let isOpen = false;
        let activePack = ALL_PACK_SLUG;
        let activeDesignerLibrary = ALL_DESIGNER_LIBRARY_SLUG;
        let observer = null;

        trigger.type = 'button';
        packSelect.id = (select.id || select.name || 'font-picker') + '-pack';
        designerSelect.id = (select.id || select.name || 'font-picker') + '-designer-library';
        search.type = 'search';
        closeButton.type = 'button';
        packLabel.setAttribute('for', packSelect.id);
        designerLabel.setAttribute('for', designerSelect.id);
        closeButton.setAttribute('aria-label', 'Close dropdown');
        search.placeholder = isFontPreview ? 'Search font family...' : 'Search options...';
        dropdown.hidden = true;
        emptyState.hidden = true;

        select.parentNode.insertBefore(shell, select);
        shell.appendChild(select);
        shell.appendChild(controlsRow);
        if (isFontPicker) {
            controlsRow.appendChild(packWrap);
            packWrap.appendChild(packLabel);
            packWrap.appendChild(packSelect);
            controlsRow.appendChild(designerWrap);
            designerWrap.appendChild(designerLabel);
            designerWrap.appendChild(designerSelect);
        }
        controlsRow.appendChild(triggerWrap);
        triggerWrap.appendChild(trigger);
        trigger.appendChild(triggerLabel);
        trigger.appendChild(triggerMeta);
        if (isFontPicker) {
            shell.appendChild(previewCard);
            previewCard.appendChild(previewCardBadge);
            previewCard.appendChild(previewCardName);
            previewCard.appendChild(previewCardMeta);
            previewCard.appendChild(previewCardLineUpper);
            previewCard.appendChild(previewCardLineLower);
            previewCard.appendChild(previewCardLineNumbers);
            previewCard.appendChild(previewCardSentence);
        }
        dropdown.appendChild(toolbar);
        toolbar.appendChild(search);
        toolbar.appendChild(closeButton);
        if (isFontPicker) {
            favoriteWrap.appendChild(favoriteHeading);
            favoriteWrap.appendChild(favoriteList);
            recentWrap.appendChild(recentHeading);
            recentWrap.appendChild(recentList);
            dropdown.appendChild(favoriteWrap);
            dropdown.appendChild(recentWrap);
        }
        dropdown.appendChild(optionsWrap);
        dropdown.appendChild(emptyState);
        select.classList.add('ve-searchable-native');

        function setEntryMap(entries) {
            metadataByValue = {};
            entries.forEach(function (entry) {
                metadataByValue[entry.css_name] = entry;
            });
        }

        function getNativeSelectEntries(nativeSelect) {
            return Array.from(nativeSelect.options).map(function (option) {
                return {
                    id: null,
                    name: option.textContent || option.label || option.value || '',
                    css_name: option.value || '',
                    category: '',
                    preview: '',
                    font_url: '',
                    packs: [],
                    pack_names: [],
                    designer_libraries: [],
                    designer_library_names: [],
                    style_label: '',
                    source: 'native',
                    google_family: '',
                    disabled: option.disabled,
                };
            });
        }

        function setFontFamily(element, fontName, fallbackStack) {
            if (!element) {
                return;
            }
            const fallback = fallbackStack || 'sans-serif';
            element.style.fontFamily = fontName ? '"' + fontName + '", ' + fallback : '';
        }

        function getSelectedEntry() {
            return metadataByValue[select.value] || null;
        }

        function loadFontsForRenderedOptions(entries, preferredValue) {
            if (!isFontPicker) {
                return;
            }
            const families = [];
            entries.forEach(function (entry, index) {
                if (entry.source !== 'google') {
                    return;
                }
                if (index < 12 || entry.css_name === preferredValue) {
                    families.push(entry.google_family || entry.css_name);
                }
            });
            loadGoogleFontFamilies(families);
        }

        function updateFontPreviewCard(entry) {
            if (!isFontPicker) {
                return;
            }
            if (!entry) {
                previewCardName.textContent = 'No font selected';
                previewCardMeta.textContent = 'Typography preview';
                [previewCardName, previewCardLineUpper, previewCardLineLower, previewCardLineNumbers, previewCardSentence].forEach(function (node) {
                    setFontFamily(node, '', 'sans-serif');
                });
                return;
            }
            previewCardName.textContent = entry.name;
            previewCardMeta.textContent = entry.style_label || 'Typography preview';
            [previewCardName, previewCardLineUpper, previewCardLineLower, previewCardLineNumbers, previewCardSentence].forEach(function (node) {
                setFontFamily(node, entry.css_name, entry.category === 'serif' ? 'serif' : 'sans-serif');
            });
            if (entry.source === 'google') {
                loadGoogleFontFamilies([entry.google_family || entry.css_name]);
            }
        }

        function readRecentFonts() {
            return parseJson(window.localStorage.getItem(recentStorageKey) || '[]', []);
        }

        function readFavoriteFonts() {
            return parseJson(window.localStorage.getItem(favoriteStorageKey) || '[]', []);
        }

        function storeRecentFont(value) {
            if (!isFontPicker || !value) {
                return;
            }
            const recents = readRecentFonts().filter(function (item) {
                return item !== value;
            });
            recents.unshift(value);
            window.localStorage.setItem(recentStorageKey, JSON.stringify(recents.slice(0, 6)));
        }

        function toggleFavoriteFont(value) {
            if (!isFontPicker || !value) {
                return;
            }

            const favorites = readFavoriteFonts();
            const nextFavorites = favorites.includes(value)
                ? favorites.filter(function (item) { return item !== value; })
                : [value].concat(favorites);

            window.localStorage.setItem(
                favoriteStorageKey,
                JSON.stringify(nextFavorites.slice(0, 12))
            );
        }

        function isFavoriteFont(value) {
            return readFavoriteFonts().includes(value);
        }

        function matchesPack(entry) {
            if (!isFontPicker || activePack === ALL_PACK_SLUG) {
                return true;
            }
            return Array.isArray(entry.packs) && entry.packs.includes(activePack);
        }

        function matchesDesignerLibrary(entry) {
            if (!isFontPicker || activeDesignerLibrary === ALL_DESIGNER_LIBRARY_SLUG) {
                return true;
            }
            return Array.isArray(entry.designer_libraries) && entry.designer_libraries.includes(activeDesignerLibrary);
        }

        function createRecentButton(entry) {
            const button = createElement('button', 've-search-recent-item');
            const title = createElement('span', 've-search-recent-item__title', entry.name);
            const meta = createElement('span', 've-search-recent-item__meta', entry.style_label || entry.category.replace('-', ' '));

            button.type = 'button';
            button.dataset.value = entry.css_name;
            setFontFamily(title, entry.css_name, entry.category === 'serif' ? 'serif' : 'sans-serif');
            button.appendChild(title);
            button.appendChild(meta);
            button.addEventListener('click', function () {
                selectValue(entry.css_name);
                closeDropdown({ restoreFocus: false });
            });
            return button;
        }

        function createFavoriteButton(entry) {
            const button = createElement('button', 've-search-recent-item ve-search-recent-item--favorite');
            const title = createElement('span', 've-search-recent-item__title', entry.name);
            const meta = createElement('span', 've-search-recent-item__meta', entry.style_label || entry.category.replace('-', ' '));

            button.type = 'button';
            button.dataset.value = entry.css_name;
            setFontFamily(title, entry.css_name, entry.category === 'serif' ? 'serif' : 'sans-serif');
            button.appendChild(title);
            button.appendChild(meta);
            button.addEventListener('click', function () {
                selectValue(entry.css_name);
                closeDropdown({ restoreFocus: false });
            });
            return button;
        }

        function renderFavoriteFonts(query) {
            if (!isFontPicker) {
                return 0;
            }
            const favoriteValues = readFavoriteFonts();
            favoriteList.innerHTML = '';

            const matchingEntries = favoriteValues.map(function (value) {
                return metadataByValue[value];
            }).filter(function (entry) {
                if (!entry) {
                    return false;
                }
                const matchesQuery = !query || entry.name.toLowerCase().includes(query);
                return matchesQuery && matchesPack(entry) && matchesDesignerLibrary(entry);
            });

            matchingEntries.forEach(function (entry) {
                favoriteList.appendChild(createFavoriteButton(entry));
            });
            favoriteWrap.hidden = matchingEntries.length === 0;
            return matchingEntries.length;
        }

        function renderRecentFonts(query) {
            if (!isFontPicker) {
                return 0;
            }
            const recentValues = readRecentFonts();
            recentList.innerHTML = '';

            const matchingEntries = recentValues.map(function (value) {
                return metadataByValue[value];
            }).filter(function (entry) {
                if (!entry) {
                    return false;
                }
                const matchesQuery = !query || entry.name.toLowerCase().includes(query);
                return matchesQuery && matchesPack(entry) && matchesDesignerLibrary(entry);
            });

            matchingEntries.forEach(function (entry) {
                recentList.appendChild(createRecentButton(entry));
            });
            recentWrap.hidden = matchingEntries.length === 0;
            return matchingEntries.length;
        }

        function updateTrigger() {
            const selectedEntry = getSelectedEntry();
            const selectedLabel = selectedEntry ? selectedEntry.name : 'Select an option';

            triggerLabel.textContent = selectedLabel;
            if (isFontPreview && selectedEntry) {
                setFontFamily(
                    triggerLabel,
                    selectedEntry.css_name,
                    selectedEntry.category === 'serif' ? 'serif' : 'sans-serif'
                );
            }
            if (isFontPicker && selectedEntry) {
                const activeFilters = [];
                const selectedPack = fontPacks.find(function (pack) {
                    return pack.slug === activePack;
                });
                const selectedDesignerLibrary = designerFontLibraries.find(function (library) {
                    return library.slug === activeDesignerLibrary;
                });
                if (selectedPack && activePack !== ALL_PACK_SLUG) {
                    activeFilters.push(selectedPack.name);
                }
                if (selectedDesignerLibrary && activeDesignerLibrary !== ALL_DESIGNER_LIBRARY_SLUG) {
                    activeFilters.push(selectedDesignerLibrary.name);
                }
                triggerMeta.textContent = activeFilters.length
                    ? activeFilters.join(' • ')
                    : (selectedEntry.style_label || 'Live font preview');
            } else {
                triggerMeta.textContent = selectedEntry
                    ? (selectedEntry.style_label || 'Live font preview')
                    : (isFontPreview ? 'Live font preview' : 'Search and select');
            }

            optionButtons.forEach(function (button) {
                button.classList.toggle('is-selected', button.dataset.value === select.value);
            });
            updateFontPreviewCard(selectedEntry);
        }

        function mountDropdown() {
            if (dropdownMounted) {
                return;
            }
            document.body.appendChild(dropdown);
            dropdownMounted = true;
        }

        function updateDropdownPosition() {
            if (!isOpen) {
                return;
            }

            const rect = trigger.getBoundingClientRect();
            const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
            const dropdownHeight = Math.min(340, dropdown.scrollHeight || 0);
            const spaceBelow = viewportHeight - rect.bottom;
            const spaceAbove = rect.top;
            const openAbove = spaceBelow < dropdownHeight && spaceAbove > spaceBelow;
            const top = openAbove
                ? Math.max(8, rect.top - dropdownHeight - 8)
                : Math.min(viewportHeight - dropdownHeight - 8, rect.bottom + 8);

            dropdown.style.position = 'fixed';
            dropdown.style.left = rect.left + 'px';
            dropdown.style.top = top + 'px';
            dropdown.style.width = rect.width + 'px';
            dropdown.style.maxHeight = Math.min(340, viewportHeight - 16) + 'px';
            dropdown.dataset.placement = openAbove ? 'top' : 'bottom';
        }

        function closeDropdown(config) {
            const shouldRestoreFocus = !config || config.restoreFocus !== false;
            if (!isOpen) {
                return;
            }
            isOpen = false;
            shell.classList.remove('is-open');
            dropdown.hidden = true;
            dropdown.dataset.placement = '';
            clearActiveSearchDropdown(controller);
            if (shouldRestoreFocus) {
                trigger.focus();
            }
        }

        function openDropdown() {
            if (isOpen) {
                updateDropdownPosition();
                return;
            }
            setActiveSearchDropdown(controller);
            mountDropdown();
            isOpen = true;
            shell.classList.add('is-open');
            dropdown.hidden = false;
            updateDropdownPosition();
            search.focus();
            search.select();
        }

        function filterOptions() {
            const query = search.value.trim().toLowerCase();
            let hasVisibleOption = false;

            optionButtons.forEach(function (button) {
                const haystack = (button.dataset.label + ' ' + button.dataset.value).toLowerCase();
                const buttonPacks = button.dataset.packs ? button.dataset.packs.split('|') : [];
                const buttonDesignerLibraries = button.dataset.designerLibraries ? button.dataset.designerLibraries.split('|') : [];
                const matchesPackSelection = activePack === ALL_PACK_SLUG || buttonPacks.includes(activePack);
                const matchesDesignerSelection = activeDesignerLibrary === ALL_DESIGNER_LIBRARY_SLUG || buttonDesignerLibraries.includes(activeDesignerLibrary);
                const shouldShow = matchesPackSelection && matchesDesignerSelection && (!query || haystack.includes(query));
                button.hidden = !shouldShow;
                if (shouldShow) {
                    hasVisibleOption = true;
                }
            });

            hasVisibleOption = renderFavoriteFonts(query) > 0 || hasVisibleOption;
            hasVisibleOption = renderRecentFonts(query) > 0 || hasVisibleOption;
            emptyState.textContent = currentEntries.length
                ? (isFontPicker ? 'No matching fonts found.' : 'No matching options found.')
                : (isFontPicker ? 'No fonts available in this category.' : 'No options available.');
            emptyState.hidden = hasVisibleOption;
        }

        function selectValue(value) {
            select.value = value;
            storeRecentFont(value);
            const selectedEntry = getSelectedEntry();
            if (selectedEntry && selectedEntry.source === 'google') {
                loadGoogleFontFamilies([selectedEntry.google_family || selectedEntry.css_name]);
            }
            updateTrigger();
            select.dispatchEvent(new Event('input', { bubbles: true }));
            select.dispatchEvent(new Event('change', { bubbles: true }));
        }

        function disconnectObserver() {
            if (observer) {
                observer.disconnect();
                observer = null;
            }
        }

        function enableLazyGoogleLoading() {
            if (!isFontPicker) {
                return;
            }
            disconnectObserver();
            if (!('IntersectionObserver' in window)) {
                return;
            }
            observer = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    const family = entry.target.dataset.googleFamily;
                    if (family) {
                        loadGoogleFontFamilies([family]);
                    }
                    observer.unobserve(entry.target);
                });
            }, {
                root: optionsWrap,
                threshold: 0.1,
            });
            optionButtons.forEach(function (button) {
                if (button.dataset.googleFamily) {
                    observer.observe(button);
                }
            });
        }

        function buildPackSelector() {
            if (!isFontPicker) {
                return;
            }

            const groups = {};
            fontPacks.forEach(function (pack) {
                if (!groups[pack.group]) {
                    groups[pack.group] = document.createElement('optgroup');
                    groups[pack.group].label = pack.group.charAt(0).toUpperCase() + pack.group.slice(1);
                    packSelect.appendChild(groups[pack.group]);
                }
                const option = createElement('option');
                option.value = pack.slug;
                option.textContent = pack.name;
                groups[pack.group].appendChild(option);
            });

            packSelect.value = activePack;
            packSelect.addEventListener('change', function () {
                activePack = packSelect.value || ALL_PACK_SLUG;
                fetchAndApplyPackFonts(activePack, {
                    designerSlug: activeDesignerLibrary,
                    preferredValue: select.value,
                    autoSelectFirst: true,
                });
            });
        }

        function buildDesignerLibrarySelector() {
            if (!isFontPicker) {
                return;
            }

            designerFontLibraries.forEach(function (library) {
                const option = createElement('option');
                option.value = library.slug;
                option.textContent = library.name;
                designerSelect.appendChild(option);
            });

            designerSelect.value = activeDesignerLibrary;
            designerSelect.addEventListener('change', function () {
                activeDesignerLibrary = designerSelect.value || ALL_DESIGNER_LIBRARY_SLUG;
                fetchAndApplyPackFonts(activePack, {
                    designerSlug: activeDesignerLibrary,
                    preferredValue: select.value,
                    autoSelectFirst: true,
                });
            });
        }

        function createOptionButton(entry) {
            const button = createElement('button', isFontPreview ? 've-search-option ve-search-option--font' : 've-search-option');
            const title = createElement('span', 've-search-option__title', entry.name);
            const actionRow = createElement('div', 've-search-option__actions');

            button.type = 'button';
            button.dataset.value = entry.css_name;
            button.dataset.label = entry.name;
            button.dataset.category = entry.category || '';
            button.dataset.packs = Array.isArray(entry.packs) ? entry.packs.join('|') : '';
            button.dataset.designerLibraries = Array.isArray(entry.designer_libraries) ? entry.designer_libraries.join('|') : '';
            button.disabled = !!entry.disabled;
            if (entry.source === 'google') {
                button.dataset.googleFamily = entry.google_family || entry.css_name;
            }
            button.appendChild(title);

            if (isFontPreview && entry.css_name) {
                const sample = createElement('span', 've-search-option__sample', 'Aa Bb Cc 123');
                setFontFamily(title, entry.css_name, entry.category === 'serif' ? 'serif' : 'sans-serif');
                setFontFamily(sample, entry.css_name, entry.category === 'serif' ? 'serif' : 'sans-serif');
                button.appendChild(sample);
                if (entry.style_label) {
                    button.appendChild(
                        createElement('span', 've-search-option__meta', entry.style_label)
                    );
                }
                if (isFontPicker) {
                    const favoriteButton = createElement(
                        'button',
                        've-search-option__favorite' + (isFavoriteFont(entry.css_name) ? ' is-active' : ''),
                        'Favorite'
                    );
                    favoriteButton.type = 'button';
                    favoriteButton.setAttribute('aria-label', 'Toggle favorite font');
                    favoriteButton.addEventListener('click', function (event) {
                        event.preventDefault();
                        event.stopPropagation();
                        toggleFavoriteFont(entry.css_name);
                        favoriteButton.classList.toggle('is-active', isFavoriteFont(entry.css_name));
                        renderFavoriteFonts(search.value.trim().toLowerCase());
                    });
                    actionRow.appendChild(favoriteButton);
                    button.appendChild(actionRow);
                }
            }

            button.addEventListener('click', function () {
                selectValue(entry.css_name);
                closeDropdown({ restoreFocus: false });
            });
            return button;
        }

        function rebuildOptions(entries, preferredValue, autoSelectFirst) {
            currentEntries = entries.slice();
            setEntryMap(entries);
            optionButtons.splice(0, optionButtons.length);
            optionsWrap.innerHTML = '';
            select.innerHTML = '';
            disconnectObserver();

            entries.forEach(function (entry) {
                const option = createElement('option');
                option.value = entry.css_name;
                option.textContent = entry.name;
                option.disabled = !!entry.disabled;
                select.appendChild(option);

                const button = createOptionButton(entry);
                optionButtons.push(button);
                optionsWrap.appendChild(button);
            });

            const currentValueExists = entries.some(function (entry) {
                return entry.css_name === preferredValue;
            });
            let nextValue = preferredValue;
            if (!currentValueExists && autoSelectFirst) {
                nextValue = entries.length ? entries[0].css_name : '';
            }
            if (!entries.length) {
                nextValue = '';
            }
            select.value = nextValue;
            updateTrigger();
            renderFavoriteFonts('');
            renderRecentFonts('');
            filterOptions();
            loadFontsForRenderedOptions(entries, nextValue);
            enableLazyGoogleLoading();

            if (autoSelectFirst && nextValue) {
                select.dispatchEvent(new Event('input', { bubbles: true }));
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }

        function fetchFontEntries(packSlug, designerSlug) {
            if (!fontApiUrl) {
                return Promise.resolve(initialFontEntries);
            }
            const cacheKey = fontApiUrl + '::' + packSlug + '::' + designerSlug;
            if (!fontApiCache.has(cacheKey)) {
                const requestUrl = fontApiUrl
                    + '?pack=' + encodeURIComponent(packSlug)
                    + '&designer=' + encodeURIComponent(designerSlug || ALL_DESIGNER_LIBRARY_SLUG);
                fontApiCache.set(cacheKey, fetch(requestUrl, {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                }).then(function (response) {
                    if (!response.ok) {
                        throw new Error('Unable to load fonts.');
                    }
                    return response.json();
                }).then(function (payload) {
                    return payload.results || [];
                }));
            }
            return fontApiCache.get(cacheKey);
        }

        function fetchAndApplyPackFonts(packSlug, config) {
            const options = config || {};
            const designerSlug = options.designerSlug || activeDesignerLibrary;
            const preferredValue = options.preferredValue || select.value;
            triggerMeta.textContent = 'Loading fonts...';
            return fetchFontEntries(packSlug, designerSlug).then(function (entries) {
                rebuildOptions(entries, preferredValue, options.autoSelectFirst !== false);
                if (!entries.length) {
                    updateFontPreviewCard(null);
                }
                return entries;
            }).catch(function () {
                rebuildOptions([], '', false);
                emptyState.textContent = 'No fonts available in this category.';
            });
        }

        buildPackSelector();
        buildDesignerLibrarySelector();
        rebuildOptions(initialFontEntries, select.value, false);

        trigger.addEventListener('click', function (event) {
            event.preventDefault();
            if (isOpen) {
                closeDropdown();
                return;
            }
            openDropdown();
            filterOptions();
        });

        search.addEventListener('input', filterOptions);
        search.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeDropdown();
            }
        });
        closeButton.addEventListener('click', function (event) {
            event.preventDefault();
            closeDropdown();
        });

        select.addEventListener('change', updateTrigger);
        const controller = {
            shell: shell,
            dropdown: dropdown,
            trigger: trigger,
            search: search,
            isOpen: function () {
                return isOpen;
            },
            containsTarget: function (target) {
                return shell.contains(target) || dropdown.contains(target);
            },
            close: closeDropdown,
            updatePosition: updateDropdownPosition,
        };

        updateTrigger();
        filterOptions();
    }

    function enhanceRangeInput(input) {
        if (!input || input.dataset.veEnhanced === 'true') {
            return;
        }
        input.dataset.veEnhanced = 'true';

        const shell = createElement('div', 've-range-shell');
        const range = createElement('input');
        range.type = 'range';
        range.min = input.min || '0';
        range.max = input.max || '100';
        range.step = input.step || '1';
        range.value = input.value || input.min || '0';

        input.parentNode.insertBefore(shell, input);
        shell.appendChild(input);
        shell.appendChild(range);

        function syncFromInput() {
            range.value = input.value || range.min;
        }

        function syncFromRange() {
            input.value = range.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        input.addEventListener('input', syncFromInput);
        range.addEventListener('input', syncFromRange);
        syncFromInput();
    }

    function enhanceSizeInput(input) {
        if (!input || input.dataset.veEnhanced === 'true') {
            return;
        }
        input.dataset.veEnhanced = 'true';

        const wrapper = createElement('div', 've-builder-shell');
        const row = createElement('div', 've-builder-row ve-builder-row--triple');
        const numberWrap = createElement('div');
        const unitWrap = createElement('div');
        const toggleWrap = createElement('div');
        const numberInput = createElement('input', 've-builder-input');
        const unitSelect = createElement('select', 've-builder-select');
        const toggleButton = createElement('button', 've-builder-advanced-toggle', 'Advanced');
        const advancedWrap = createElement('div', 've-builder-advanced');
        const advancedInput = createElement('input', 've-builder-input');
        const unitOptions = (input.dataset.unitOptions || 'px,rem,em,%,vw,vh').split(',');

        numberInput.type = 'number';
        numberInput.step = '0.1';
        advancedInput.type = 'text';
        advancedInput.placeholder = 'clamp(...) or calc(...)';
        toggleButton.type = 'button';

        unitOptions.forEach(function (unit) {
            const option = createElement('option');
            option.value = unit;
            option.textContent = unit;
            unitSelect.appendChild(option);
        });

        numberWrap.appendChild(createElement('div', 've-builder-label', 'Value'));
        numberWrap.appendChild(numberInput);
        unitWrap.appendChild(createElement('div', 've-builder-label', 'Unit'));
        unitWrap.appendChild(unitSelect);
        toggleWrap.appendChild(createElement('div', 've-builder-label', 'Mode'));
        toggleWrap.appendChild(toggleButton);
        advancedWrap.appendChild(createElement('div', 've-builder-label', 'Advanced CSS'));
        advancedWrap.appendChild(advancedInput);

        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(row);
        row.appendChild(numberWrap);
        row.appendChild(unitWrap);
        row.appendChild(toggleWrap);
        wrapper.appendChild(advancedWrap);
        wrapper.appendChild(input);
        input.style.display = 'none';

        function setAdvancedMode(isAdvanced) {
            advancedWrap.classList.toggle('is-visible', isAdvanced);
            numberWrap.style.display = isAdvanced ? 'none' : '';
            unitWrap.style.display = isAdvanced ? 'none' : '';
        }

        function syncFromFieldValue() {
            const parsed = parseSimpleSize(input.value);
            if (parsed) {
                setAdvancedMode(false);
                numberInput.value = parsed.number;
                unitSelect.value = parsed.unit;
                advancedInput.value = '';
            } else {
                setAdvancedMode(true);
                advancedInput.value = input.value || '';
            }
        }

        function syncFromSimpleControls() {
            if (!numberInput.value) {
                return;
            }
            input.value = numberInput.value + unitSelect.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        function syncFromAdvanced() {
            input.value = advancedInput.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        toggleButton.addEventListener('click', function () {
            const isAdvanced = !advancedWrap.classList.contains('is-visible');
            setAdvancedMode(isAdvanced);
            if (!isAdvanced) {
                syncFromSimpleControls();
            }
        });
        numberInput.addEventListener('input', syncFromSimpleControls);
        unitSelect.addEventListener('change', syncFromSimpleControls);
        advancedInput.addEventListener('input', syncFromAdvanced);
        syncFromFieldValue();
    }

    function enhancePaddingInput(input) {
        if (!input || input.dataset.veEnhanced === 'true') {
            return;
        }
        input.dataset.veEnhanced = 'true';

        const wrapper = createElement('div', 've-builder-shell');
        const grid = createElement('div', 've-builder-row');
        const secondGrid = createElement('div', 've-builder-row');
        const unitWrap = createElement('div');
        const advancedWrap = createElement('div', 've-builder-advanced');
        const advancedInput = createElement('input', 've-builder-input');
        const unitSelect = createElement('select', 've-builder-select');
        const toggleButton = createElement('button', 've-builder-advanced-toggle', 'Advanced');
        const labels = ['Top', 'Right', 'Bottom', 'Left'];
        const inputs = labels.map(function (label) {
            const box = createElement('div');
            const field = createElement('input', 've-builder-input');
            field.type = 'number';
            field.step = '0.1';
            box.appendChild(createElement('div', 've-builder-label', label));
            box.appendChild(field);
            return { box: box, field: field };
        });

        ['px', 'rem', 'em', '%', 'vw', 'vh'].forEach(function (unit) {
            const option = createElement('option');
            option.value = unit;
            option.textContent = unit;
            unitSelect.appendChild(option);
        });
        advancedInput.type = 'text';
        advancedInput.placeholder = '0.75rem 1.25rem';
        toggleButton.type = 'button';

        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(grid);
        wrapper.appendChild(secondGrid);
        grid.appendChild(inputs[0].box);
        grid.appendChild(inputs[1].box);
        secondGrid.appendChild(inputs[2].box);
        secondGrid.appendChild(inputs[3].box);
        unitWrap.appendChild(createElement('div', 've-builder-label', 'Unit'));
        unitWrap.appendChild(unitSelect);
        wrapper.appendChild(unitWrap);
        wrapper.appendChild(toggleButton);
        advancedWrap.appendChild(createElement('div', 've-builder-label', 'Advanced CSS'));
        advancedWrap.appendChild(advancedInput);
        wrapper.appendChild(advancedWrap);
        wrapper.appendChild(input);
        input.style.display = 'none';

        function setAdvancedMode(isAdvanced) {
            advancedWrap.classList.toggle('is-visible', isAdvanced);
            grid.style.display = isAdvanced ? 'none' : 'grid';
            secondGrid.style.display = isAdvanced ? 'none' : 'grid';
            unitWrap.style.display = isAdvanced ? 'none' : '';
        }

        function syncFromField() {
            const parsed = parsePadding(input.value);
            if (!parsed) {
                setAdvancedMode(true);
                advancedInput.value = input.value || '';
                return;
            }

            setAdvancedMode(false);
            parsed.values.forEach(function (value, index) {
                inputs[index].field.value = value;
            });
            unitSelect.value = parsed.unit;
        }

        function syncSimple() {
            const values = inputs.map(function (item) {
                return item.field.value || '0';
            });
            input.value = values.map(function (value) {
                return value + unitSelect.value;
            }).join(' ');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        function syncAdvanced() {
            input.value = advancedInput.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        inputs.forEach(function (item) {
            item.field.addEventListener('input', syncSimple);
        });
        unitSelect.addEventListener('change', syncSimple);
        toggleButton.addEventListener('click', function () {
            const isAdvanced = !advancedWrap.classList.contains('is-visible');
            setAdvancedMode(isAdvanced);
            if (!isAdvanced) {
                syncSimple();
            }
        });
        advancedInput.addEventListener('input', syncAdvanced);
        syncFromField();
    }

    function enhanceDimensionInput(input) {
        if (!input || input.dataset.veEnhanced === 'true') {
            return;
        }
        input.dataset.veEnhanced = 'true';

        const presets = (input.dataset.dimensionPresets || 'auto,100%,fit-content,custom').split(',');
        const wrapper = createElement('div', 've-builder-shell');
        const row = createElement('div', 've-builder-row ve-builder-row--triple');
        const presetWrap = createElement('div');
        const presetSelect = createElement('select', 've-builder-select');
        const numberWrap = createElement('div');
        const numberInput = createElement('input', 've-builder-input');
        const unitWrap = createElement('div');
        const unitSelect = createElement('select', 've-builder-select');
        const advancedWrap = createElement('div', 've-builder-advanced');
        const advancedInput = createElement('input', 've-builder-input');

        numberInput.type = 'number';
        numberInput.step = '0.1';
        advancedInput.type = 'text';
        advancedInput.placeholder = 'calc(100% - 20px)';

        presets.forEach(function (preset) {
            const option = createElement('option');
            option.value = preset;
            option.textContent = preset === 'custom' ? 'Custom' : preset;
            presetSelect.appendChild(option);
        });

        ['px', 'rem', 'em', '%', 'vw', 'vh'].forEach(function (unit) {
            const option = createElement('option');
            option.value = unit;
            option.textContent = unit;
            unitSelect.appendChild(option);
        });

        presetWrap.appendChild(createElement('div', 've-builder-label', 'Preset'));
        presetWrap.appendChild(presetSelect);
        numberWrap.appendChild(createElement('div', 've-builder-label', 'Value'));
        numberWrap.appendChild(numberInput);
        unitWrap.appendChild(createElement('div', 've-builder-label', 'Unit'));
        unitWrap.appendChild(unitSelect);
        advancedWrap.appendChild(createElement('div', 've-builder-label', 'Advanced CSS'));
        advancedWrap.appendChild(advancedInput);

        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(row);
        row.appendChild(presetWrap);
        row.appendChild(numberWrap);
        row.appendChild(unitWrap);
        wrapper.appendChild(advancedWrap);
        wrapper.appendChild(input);
        input.style.display = 'none';

        function updateMode() {
            const isCustom = presetSelect.value === 'custom';
            const parsed = parseSimpleSize(input.value);
            advancedWrap.classList.toggle('is-visible', isCustom && !parsed);
            numberWrap.style.display = isCustom ? '' : 'none';
            unitWrap.style.display = isCustom ? '' : 'none';
        }

        function syncFromField() {
            const parsed = parseSimpleSize(input.value);
            if (parsed) {
                presetSelect.value = 'custom';
                numberInput.value = parsed.number;
                unitSelect.value = parsed.unit;
                advancedInput.value = '';
            } else if (presets.indexOf(input.value) !== -1) {
                presetSelect.value = input.value;
                advancedInput.value = '';
            } else if (input.value) {
                presetSelect.value = 'custom';
                advancedInput.value = input.value;
            } else {
                presetSelect.value = 'auto';
            }
            updateMode();
        }

        function syncFromPreset() {
            if (presetSelect.value !== 'custom') {
                input.value = presetSelect.value;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            } else if (advancedInput.value) {
                input.value = advancedInput.value;
            } else if (numberInput.value) {
                input.value = numberInput.value + unitSelect.value;
            }
            updateMode();
        }

        function syncCustomSize() {
            input.value = numberInput.value + unitSelect.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        function syncAdvanced() {
            input.value = advancedInput.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            updateMode();
        }

        presetSelect.addEventListener('change', syncFromPreset);
        numberInput.addEventListener('input', syncCustomSize);
        unitSelect.addEventListener('change', syncCustomSize);
        advancedInput.addEventListener('input', syncAdvanced);
        syncFromField();
    }

    function getFieldValue(ids) {
        for (let index = 0; index < ids.length; index += 1) {
            const field = document.getElementById(ids[index]);
            if (field) {
                if (field.type === 'checkbox') {
                    return field.checked;
                }
                return field.value;
            }
        }
        return '';
    }

    function getFileFieldUrl(fieldId, existingUrls) {
        const field = document.getElementById(fieldId);
        if (!field) {
            return existingUrls[fieldId.replace(/^id_/, '')] || '';
        }

        if (field.files && field.files[0]) {
            return URL.createObjectURL(field.files[0]);
        }
        return existingUrls[field.name] || existingUrls[fieldId.replace(/^id_/, '')] || '';
    }

    function syncPreview() {
        const panel = document.querySelector('.ve-live-preview');
        if (!panel) {
            return;
        }

        const existingUrls = parseJson(panel.dataset.fileUrls || '{}', {});
        const badge = panel.querySelector('.ve-preview-badge');
        const heading = panel.querySelector('.ve-preview-heading');
        const copy = panel.querySelector('.ve-preview-copy');
        const primaryButton = panel.querySelector('.ve-preview-button--primary');
        const secondaryButton = panel.querySelector('.ve-preview-button--secondary');
        const backdrop = panel.querySelector('.ve-preview-stage__backdrop');
        const overlay = panel.querySelector('.ve-preview-stage__overlay');
        const stage = panel.querySelector('.ve-preview-stage');
        const mediaImage = panel.querySelector('.ve-preview-media__image');
        const mediaPlaceholder = panel.querySelector('.ve-preview-media__placeholder');

        const badgeText = getFieldValue(['id_badge_text', 'id_hero_badge_text']);
        const headingText = getFieldValue(['id_heading', 'id_banner_title', 'id_hero_heading', 'id_title']);
        const descriptionText = getFieldValue(['id_description', 'id_banner_subtitle', 'id_hero_subheading']);
        const primaryButtonText = getFieldValue(['id_button_text', 'id_hero_button_text']);
        const secondaryButtonText = getFieldValue(['id_left_button_text', 'id_right_button_text']);
        const backgroundType = getFieldValue(['id_background_type']);
        const backgroundColor = getFieldValue(['id_background_color', 'id_hero_background_color', 'id_promo_background_color']) || '#f3f4f6';
        const headingColor = getFieldValue(['id_heading_text_color']) || '#ffffff';
        const descriptionColor = getFieldValue(['id_description_text_color']) || 'rgba(255,255,255,.92)';
        const badgeTextColor = getFieldValue(['id_badge_text_color']) || '#ffffff';
        const buttonTextColor = getFieldValue(['id_button_text_color']) || '#131921';
        const buttonBackgroundColor = getFieldValue(['id_button_background_color']) || '#ffb800';
        const buttonBorderColor = getFieldValue(['id_button_border_color']) || buttonBackgroundColor;
        const buttonRadius = getFieldValue(['id_button_border_radius']) || '8';
        const buttonPadding = getFieldValue(['id_button_padding']) || '10px 18px';
        const buttonWidth = getFieldValue(['id_button_width']) || 'auto';
        const buttonHeight = getFieldValue(['id_button_height']) || 'auto';
        const buttonFontSize = getFieldValue(['id_button_font_size']) || '14px';
        const buttonFontFamily = getFieldValue(['id_button_font_family']) || 'Inter';
        const buttonFontWeight = getFieldValue(['id_button_font_weight']) || '700';
        const headingFontSize = getFieldValue(['id_heading_font_size']) || '34px';
        const headingFontFamily = getFieldValue(['id_heading_font_family']) || 'Inter';
        const headingFontWeight = getFieldValue(['id_heading_font_weight']) || '800';
        const descriptionFontSize = getFieldValue(['id_description_font_size']) || '15px';
        const descriptionFontFamily = getFieldValue(['id_description_font_family']) || 'Inter';
        const descriptionFontWeight = getFieldValue(['id_description_font_weight']) || '400';
        const badgeFontSize = getFieldValue(['id_badge_font_size']) || '12px';
        const badgeFontFamily = getFieldValue(['id_badge_font_family']) || 'Inter';
        const badgeFontWeight = getFieldValue(['id_badge_font_weight']) || '700';
        const overlayEnabled = getFieldValue(['id_enable_overlay']);
        const overlayColor = getFieldValue(['id_background_overlay_color']) || '#111827';
        const overlayOpacity = getFieldValue(['id_background_overlay_opacity']) || '0.2';
        const primaryBackgroundImage = getFileFieldUrl('id_background_image', existingUrls) ||
            getFileFieldUrl('id_image', existingUrls) ||
            getFileFieldUrl('id_cover_image', existingUrls) ||
            getFileFieldUrl('id_hero_image', existingUrls) ||
            getFileFieldUrl('id_promo_image', existingUrls);
        const mediaImageUrl = getFileFieldUrl('id_image', existingUrls) ||
            getFileFieldUrl('id_cover_image', existingUrls) ||
            getFileFieldUrl('id_hero_image', existingUrls) ||
            getFileFieldUrl('id_promo_image', existingUrls);

        badge.textContent = badgeText || 'Badge';
        heading.textContent = headingText || 'Banner heading preview';
        copy.textContent = descriptionText || 'Supporting description preview appears here as you update the form.';
        primaryButton.textContent = primaryButtonText || 'Primary Button';
        secondaryButton.textContent = secondaryButtonText || 'Secondary Button';

        setHiddenState(badge, !badgeText);
        setHiddenState(copy, !descriptionText);
        setHiddenState(primaryButton, !primaryButtonText);
        setHiddenState(secondaryButton, !secondaryButtonText);

        heading.style.color = headingColor;
        heading.style.fontFamily = '"' + headingFontFamily + '", sans-serif';
        heading.style.fontSize = headingFontSize;
        heading.style.fontWeight = headingFontWeight;
        copy.style.color = descriptionColor;
        copy.style.fontFamily = '"' + descriptionFontFamily + '", sans-serif';
        copy.style.fontSize = descriptionFontSize;
        copy.style.fontWeight = descriptionFontWeight;
        badge.style.color = badgeTextColor;
        badge.style.fontFamily = '"' + badgeFontFamily + '", sans-serif';
        badge.style.fontSize = badgeFontSize;
        badge.style.fontWeight = badgeFontWeight;
        primaryButton.style.backgroundColor = buttonBackgroundColor;
        primaryButton.style.color = buttonTextColor;
        primaryButton.style.borderColor = buttonBorderColor;
        primaryButton.style.borderRadius = buttonRadius + 'px';
        primaryButton.style.padding = buttonPadding;
        primaryButton.style.width = buttonWidth;
        primaryButton.style.height = buttonHeight;
        primaryButton.style.fontFamily = '"' + buttonFontFamily + '", sans-serif';
        primaryButton.style.fontSize = buttonFontSize;
        primaryButton.style.fontWeight = buttonFontWeight;

        stage.style.background = backgroundColor;
        if (backgroundType === 'gradient') {
            const first = getFieldValue(['id_background_gradient_color_1']) || '#f8fafc';
            const second = getFieldValue(['id_background_gradient_color_2']) || '#e2e8f0';
            const direction = getFieldValue(['id_background_gradient_direction']) || 'to right';
            stage.style.background = 'linear-gradient(' + direction + ', ' + first + ', ' + second + ')';
        }

        backdrop.style.backgroundImage = primaryBackgroundImage ? 'url("' + primaryBackgroundImage + '")' : 'none';
        overlay.style.backgroundColor = overlayEnabled ? overlayColor : 'transparent';
        overlay.style.opacity = overlayEnabled ? overlayOpacity : '0';

        if (mediaImageUrl) {
            mediaImage.src = mediaImageUrl;
            mediaImage.hidden = false;
            mediaPlaceholder.style.display = 'none';
        } else {
            mediaImage.hidden = true;
            mediaPlaceholder.style.display = '';
        }
    }

    function initVisualEditor() {
        document.querySelectorAll('.ve-color-source').forEach(enhanceColorField);
        document.querySelectorAll('.ve-searchable-select').forEach(enhanceSearchableSelect);
        document.querySelectorAll('.ve-range-sync').forEach(enhanceRangeInput);
        document.querySelectorAll('.ve-css-size').forEach(enhanceSizeInput);
        document.querySelectorAll('.ve-css-padding').forEach(enhancePaddingInput);
        document.querySelectorAll('.ve-dimension-input').forEach(enhanceDimensionInput);
        syncPreview();
        document.addEventListener('input', syncPreview, true);
        document.addEventListener('change', syncPreview, true);
    }

    document.addEventListener('pointerdown', function (event) {
        if (!activeSearchDropdown || !activeSearchDropdown.isOpen()) {
            return;
        }
        if (!activeSearchDropdown.containsTarget(event.target)) {
            activeSearchDropdown.close({ restoreFocus: false });
        }
    }, true);

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape' || !activeSearchDropdown || !activeSearchDropdown.isOpen()) {
            return;
        }
        event.preventDefault();
        activeSearchDropdown.close();
    });

    window.addEventListener('resize', function () {
        if (activeSearchDropdown && activeSearchDropdown.isOpen()) {
            activeSearchDropdown.updatePosition();
        }
    });

    window.addEventListener('scroll', function () {
        if (activeSearchDropdown && activeSearchDropdown.isOpen()) {
            activeSearchDropdown.updatePosition();
        }
    }, true);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initVisualEditor);
    } else {
        initVisualEditor();
    }
})();
