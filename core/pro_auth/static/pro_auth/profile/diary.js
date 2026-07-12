(function () {
    "use strict";

    let pendingActionFocusSelector = null;

    function setModalOpen(modalElement, isOpen) {
        if (!modalElement) {
            return;
        }

        modalElement.classList.toggle("is-open", isOpen);
        modalElement.setAttribute("aria-hidden", String(!isOpen));
    }

    function focusFirstField(container) {
        const firstField = container ? container.querySelector("select, input:not([type='hidden']), textarea, button") : null;
        if (firstField) {
            firstField.focus();
        }
    }

    function syncPlantTargetsState(formElement, inputSelector) {
        const applyToAllInput = formElement.querySelector(inputSelector);
        const plantTargets = formElement.querySelector("[data-plant-targets]");
        const plantTargetSection = formElement.querySelector("[data-plant-target-section]");

        if (!applyToAllInput || !plantTargets) {
            return;
        }

        const applyToAll = applyToAllInput.checked;
        const inputs = plantTargets.querySelectorAll('input[type="checkbox"]');

        plantTargets.hidden = applyToAll;
        if (plantTargetSection) {
            plantTargetSection.hidden = applyToAll;
        }
        inputs.forEach(function (input) {
            input.disabled = applyToAll;
        });
    }

    function bindDiaryItemForm(formElement, inputSelector) {
        if (formElement.dataset.diaryItemFormBound === "true") {
            return;
        }
        formElement.dataset.diaryItemFormBound = "true";

        const applyToAllInput = formElement.querySelector(inputSelector);
        const actionInput = formElement.querySelector("select[name$='action_type']");
        const harvestFields = formElement.querySelector("[data-harvest-fields]");
        const harvestInputs = harvestFields ? harvestFields.querySelectorAll("[data-harvest-input]") : [];
        const fileInput = formElement.querySelector("input[type='file']");
        const fileName = formElement.querySelector("[data-file-name]");
        const plantModeControls = formElement.querySelector("[data-plant-mode-controls]");
        const imagePreview = formElement.querySelector("[data-image-preview]");
        const imagePreviewOutput = formElement.querySelector("[data-image-preview-output]");
        const imageRotate = formElement.querySelector("[data-image-rotate]");

        syncPlantTargetsState(formElement, inputSelector);

        function syncHarvestFields() {
            if (!actionInput || !harvestFields) {
                return;
            }

            const isHarvest = actionInput.value === "harvest";
            harvestFields.hidden = !isHarvest;
            harvestInputs.forEach(function (input) {
                input.disabled = !isHarvest;
                if (!isHarvest) {
                    input.value = "";
                }
            });
        }

        syncHarvestFields();

        if (actionInput) {
            actionInput.addEventListener("change", syncHarvestFields);
        }

        if (applyToAllInput) {
            applyToAllInput.addEventListener("change", function () {
                syncPlantTargetsState(formElement, inputSelector);
            });
        }

        if (plantModeControls && applyToAllInput) {
            const modeButtons = plantModeControls.querySelectorAll("[data-plant-mode]");
            function syncPlantModeButtons() {
                modeButtons.forEach(function (button) {
                    button.classList.toggle(
                        "is-active",
                        (button.dataset.plantMode === "all") === applyToAllInput.checked
                    );
                });
            }
            syncPlantModeButtons();
            modeButtons.forEach(function (button) {
                button.addEventListener("click", function () {
                    applyToAllInput.checked = button.dataset.plantMode === "all";
                    applyToAllInput.dispatchEvent(new Event("change", {bubbles: true}));
                    syncPlantModeButtons();
                });
            });
        }

        if (fileInput && fileName) {
            fileInput.addEventListener("change", function () {
                const selectedFile = fileInput.files && fileInput.files.length ? fileInput.files[0].name : "";
                fileName.textContent = selectedFile || "Файл не вибрано";
                formElement.dataset.imageRotation = "0";
                if (imagePreview && imagePreviewOutput) {
                    if (formElement.dataset.imagePreviewUrl) {
                        URL.revokeObjectURL(formElement.dataset.imagePreviewUrl);
                    }
                    if (selectedFile) {
                        const previewUrl = URL.createObjectURL(fileInput.files[0]);
                        formElement.dataset.imagePreviewUrl = previewUrl;
                        imagePreviewOutput.src = previewUrl;
                        imagePreviewOutput.style.transform = "rotate(0deg)";
                        imagePreview.hidden = false;
                    } else {
                        imagePreview.hidden = true;
                        imagePreviewOutput.removeAttribute("src");
                    }
                }
            });
        }

        if (imageRotate && imagePreviewOutput) {
            imageRotate.addEventListener("click", function () {
                const rotation = (Number(formElement.dataset.imageRotation || 0) + 90) % 360;
                formElement.dataset.imageRotation = String(rotation);
                imagePreviewOutput.style.transform = "rotate(" + rotation + "deg)";
            });
        }
    }

    function formatLocalDate(dateValue) {
        const year = dateValue.getFullYear();
        const month = String(dateValue.getMonth() + 1).padStart(2, "0");
        const day = String(dateValue.getDate()).padStart(2, "0");
        return year + "-" + month + "-" + day;
    }

    function initDateShortcuts(root) {
        const container = root || document;
        container.querySelectorAll("[data-date-shortcuts]").forEach(function (shortcuts) {
            if (shortcuts.dataset.dateShortcutsBound === "true") {
                return;
            }
            shortcuts.dataset.dateShortcutsBound = "true";

            const formGroup = shortcuts.closest(".profile-form-group");
            const input = formGroup ? formGroup.querySelector("[data-profile-datepicker]") : null;
            if (!input) {
                return;
            }

            shortcuts.querySelectorAll("[data-date-offset]").forEach(function (button) {
                button.addEventListener("click", function () {
                    const selectedDate = new Date();
                    selectedDate.setHours(12, 0, 0, 0);
                    selectedDate.setDate(selectedDate.getDate() + Number(button.dataset.dateOffset || 0));

                    if (input._flatpickr) {
                        input._flatpickr.setDate(selectedDate, true);
                    } else {
                        input.value = formatLocalDate(selectedDate);
                        input.dispatchEvent(new Event("change", {bubbles: true}));
                    }
                });
            });
        });
    }

    function announceAsyncStatus(message, isError) {
        const status = document.querySelector("[data-profile-async-status]");
        if (!status) {
            return;
        }
        status.textContent = message || "";
        status.classList.toggle("is-visible", Boolean(message));
        status.classList.toggle("is-error", Boolean(isError));
        if (message) {
            window.setTimeout(function () {
                status.classList.remove("is-visible");
            }, 4200);
        }
    }

    function closeOpenActionModals() {
        document.querySelectorAll(".profile-diary-item-modal.is-open, .profile-quick-action-backdrop.is-open").forEach(function (modal) {
            setModalOpen(modal, false);
            const form = modal.querySelector("form");
            if (form) {
                form.reset();
            }
        });
    }

    function refreshDiaryWorkspace(refreshUrl) {
        if (!refreshUrl) {
            return Promise.resolve();
        }

        const target = document.getElementById("profileDiaryDetailContent") || document.getElementById("profileDiaryListContent");
        if (!target) {
            return Promise.resolve();
        }

        const selector = "#" + target.id;
        const fragmentUrl = new URL(refreshUrl, window.location.origin);
        fragmentUrl.searchParams.set("fragment", "workspace");
        if (!window.htmx) {
            return window.fetch(fragmentUrl.toString(), {credentials: "same-origin"}).then(function (response) {
                return response.text();
            }).then(function (html) {
                const parsed = new DOMParser().parseFromString(html, "text/html");
                const replacement = parsed.querySelector(selector);
                if (replacement) {
                    target.replaceWith(replacement);
                    initDiaryInteractions();
                }
            });
        }
        return window.htmx.ajax("GET", fragmentUrl.toString(), {
            target: selector,
            swap: "outerHTML",
        });
    }

    function initHtmxDiaryEvents() {
        if (document.body.dataset.diaryHtmxEventsBound === "true") {
            return;
        }
        document.body.dataset.diaryHtmxEventsBound = "true";

        document.body.addEventListener("diaryActionSaved", function (event) {
            const detail = event.detail || {};
            closeOpenActionModals();
            announceAsyncStatus(detail.message || "Зміни збережено", false);
            refreshDiaryWorkspace(detail.refreshUrl).then(function () {
                const nextAction = pendingActionFocusSelector
                    ? document.querySelector(pendingActionFocusSelector)
                    : document.querySelector("[data-diary-item-modal-open]");
                if (nextAction) {
                    nextAction.focus();
                }
                pendingActionFocusSelector = null;
            });
        });

        document.body.addEventListener("diaryActionError", function (event) {
            const detail = event.detail || {};
            announceAsyncStatus(detail.message || "Не вдалося зберегти зміни", true);
        });

        document.body.addEventListener("htmx:beforeRequest", function (event) {
            const form = event.target.closest ? event.target.closest("form") : null;
            if (form) {
                form.setAttribute("aria-busy", "true");
            }
        });

        document.body.addEventListener("htmx:afterRequest", function (event) {
            const form = event.target.closest ? event.target.closest("form") : null;
            if (form) {
                form.removeAttribute("aria-busy");
            }
        });

        document.body.addEventListener("htmx:afterSwap", function (event) {
            initDateShortcuts(event.target);
            if (window.initProfileDatepickers) {
                window.initProfileDatepickers(event.target);
            }
            event.target.querySelectorAll(".profile-diary-item-modal__form").forEach(function (form) {
                bindDiaryItemForm(form, "input[name$='apply_to_all']");
            });
            initDiaryInteractions();

            const invalid = event.target.querySelector(".profile-form-error");
            if (invalid) {
                invalid.setAttribute("tabindex", "-1");
                invalid.focus();
            }
        });
    }

    function dispatchResponseTriggers(response) {
        const triggerHeader = response.headers.get("HX-Trigger");
        if (!triggerHeader) {
            return;
        }
        const triggers = JSON.parse(triggerHeader);
        Object.keys(triggers).forEach(function (eventName) {
            document.body.dispatchEvent(new CustomEvent(eventName, {detail: triggers[eventName]}));
        });
    }

    function canvasToBlob(canvas, type, quality) {
        return new Promise(function (resolve, reject) {
            canvas.toBlob(function (blob) {
                if (blob) {
                    resolve(blob);
                } else {
                    reject(new Error("Image conversion failed"));
                }
            }, type, quality);
        });
    }

    async function rotateImageFile(file, rotation) {
        if (typeof createImageBitmap === "undefined") {
            return file;
        }
        const bitmap = await createImageBitmap(file, {imageOrientation: "from-image"});
        const scale = Math.min(1, 1920 / Math.max(bitmap.width, bitmap.height));
        const drawWidth = Math.round(bitmap.width * scale);
        const drawHeight = Math.round(bitmap.height * scale);
        const swapSides = rotation === 90 || rotation === 270;
        const canvas = document.createElement("canvas");
        canvas.width = swapSides ? drawHeight : drawWidth;
        canvas.height = swapSides ? drawWidth : drawHeight;
        const context = canvas.getContext("2d");
        context.translate(canvas.width / 2, canvas.height / 2);
        context.rotate((rotation || 0) * Math.PI / 180);
        context.drawImage(bitmap, -drawWidth / 2, -drawHeight / 2, drawWidth, drawHeight);
        bitmap.close();
        const blob = await canvasToBlob(canvas, "image/webp", 0.88);
        return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".webp", {type: "image/webp"});
    }

    async function prepareDiaryFormData(form) {
        const formData = new FormData(form);
        const imageInput = form.querySelector("input[type='file']");
        const image = imageInput && imageInput.files ? imageInput.files[0] : null;
        if (!image) {
            return formData;
        }
        try {
            const rotated = await rotateImageFile(image, Number(form.dataset.imageRotation || 0));
            const compressed = window.imageCompression
                ? await window.imageCompression(rotated, {
                    maxSizeMB: 1,
                    maxWidthOrHeight: 1920,
                    useWebWorker: true,
                    fileType: "image/webp",
                    initialQuality: 0.82,
                })
                : rotated;
            const prepared = new File(
                [compressed],
                image.name.replace(/\.[^.]+$/, "") + ".webp",
                {type: "image/webp", lastModified: Date.now()}
            );
            formData.set(imageInput.name, prepared, prepared.name);
        } catch (error) {
            announceAsyncStatus("Фото буде завантажено без оптимізації", false);
        }
        return formData;
    }

    function initLazyRecommendation(root) {
        if (window.htmx) {
            return;
        }
        const container = root || document;
        const recommendation = container.querySelector("#diaryRecommendation[hx-get]");
        if (!recommendation || recommendation.dataset.lazyRecommendationLoading === "true") {
            return;
        }
        recommendation.dataset.lazyRecommendationLoading = "true";
        window.fetch(recommendation.getAttribute("hx-get"), {credentials: "same-origin"})
            .then(function (response) { return response.text(); })
            .then(function (html) {
                recommendation.outerHTML = html;
                initDiaryInteractions();
            })
            .catch(function () {
                recommendation.setAttribute("aria-busy", "false");
                const title = recommendation.querySelector(".profile-diary-recommendation__title");
                if (title) {
                    title.textContent = "Порада тимчасово недоступна";
                }
            });
    }

    function initAsyncFormFallback(root) {
        const container = root || document;
        container.querySelectorAll("form[hx-post]").forEach(function (form) {
            if (form.dataset.asyncFallbackBound === "true") {
                return;
            }
            form.dataset.asyncFallbackBound = "true";
            form.addEventListener("submit", async function (event) {
                event.preventDefault();
                if (form.getAttribute("aria-busy") === "true") {
                    return;
                }
                form.setAttribute("aria-busy", "true");
                const submitButton = form.querySelector("button[type='submit']");
                if (submitButton) {
                    submitButton.disabled = true;
                }

                const formData = await prepareDiaryFormData(form);
                window.fetch(form.getAttribute("hx-post"), {
                    method: "POST",
                    body: formData,
                    headers: {"HX-Request": "true"},
                    credentials: "same-origin",
                }).then(function (response) {
                    dispatchResponseTriggers(response);
                    if (response.status === 204 || form.getAttribute("hx-swap") === "none") {
                        return "";
                    }
                    return response.text();
                }).then(function (html) {
                    if (!html) {
                        return;
                    }
                    const target = form.closest("[data-diary-item-form-container]");
                    if (target) {
                        target.outerHTML = html;
                        initDiaryInteractions();
                        const error = document.querySelector("[data-diary-item-form-container] .profile-form-error");
                        if (error) {
                            error.setAttribute("tabindex", "-1");
                            error.focus();
                        }
                    }
                }).catch(function () {
                    announceAsyncStatus("Не вдалося зберегти зміни. Перевірте з’єднання і спробуйте ще раз.", true);
                }).finally(function () {
                    form.removeAttribute("aria-busy");
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                });
            });
        });
    }

    function closeMenuGroup(menuSelector, toggleSelector, dropdownSelector) {
        document.querySelectorAll(menuSelector + ".is-open").forEach(function (openedMenu) {
            openedMenu.classList.remove("is-open");
            const openedToggle = openedMenu.querySelector(toggleSelector);
            const openedDropdown = openedMenu.querySelector(dropdownSelector);

            if (openedToggle) {
                openedToggle.setAttribute("aria-expanded", "false");
            }

            if (openedDropdown) {
                openedDropdown.hidden = true;
            }
        });
    }

    function bindMenuToggles(toggles, options) {
        toggles.forEach(function (toggle) {
            if (toggle.dataset.menuToggleBound === "true") {
                return;
            }
            toggle.dataset.menuToggleBound = "true";
            toggle.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();

                const menu = toggle.closest(options.menuSelector);
                const isOpen = menu ? menu.classList.contains("is-open") : false;
                options.closeAll();

                if (!menu || isOpen) {
                    return;
                }

                menu.classList.add("is-open");
                toggle.setAttribute("aria-expanded", "true");

                const dropdown = menu.querySelector(options.dropdownSelector);
                if (dropdown) {
                    dropdown.hidden = false;
                }
            });
        });
    }

    function initQuickWaterActions() {
        const quickWaterButtons = document.querySelectorAll("[data-quick-water-open]");
        const toast = document.querySelector("[data-profile-diary-toast]");

        function setQuickWaterPlantSelection(modalElement) {
            const selectedRadio = modalElement.querySelector("[data-quick-water-selected]");
            const plantsWrap = modalElement.querySelector("[data-quick-water-plants]");
            const plantInputs = plantsWrap ? plantsWrap.querySelectorAll("input[type='checkbox']") : [];
            const shouldSelectPlants = selectedRadio ? selectedRadio.checked : false;

            if (plantsWrap) {
                plantsWrap.hidden = !shouldSelectPlants;
            }

            plantInputs.forEach(function (input) {
                input.disabled = !shouldSelectPlants;
            });
        }

        function closeQuickWaterModal(modalElement) {
            setModalOpen(modalElement, false);
        }

        function openQuickWaterModal(modalElement) {
            if (!modalElement) {
                return;
            }

            setModalOpen(modalElement, true);
            setQuickWaterPlantSelection(modalElement);

            const saveButton = modalElement.querySelector(".profile-confirm-submit");
            if (saveButton) {
                saveButton.focus();
            }
        }

        if (toast) {
            window.setTimeout(function () {
                toast.classList.remove("is-visible");
            }, 3800);
        }

        quickWaterButtons.forEach(function (button) {
            if (button.dataset.quickWaterBound === "true") {
                return;
            }
            button.dataset.quickWaterBound = "true";

            button.addEventListener("click", function () {
                const modalId = button.getAttribute("data-quick-water-open");
                pendingActionFocusSelector = '[data-quick-water-open="' + modalId + '"]';
                openQuickWaterModal(document.getElementById(modalId));
            });
        });

        document.querySelectorAll(".profile-quick-action-backdrop").forEach(function (quickModal) {
            if (quickModal.dataset.quickWaterModalBound === "true") {
                return;
            }
            quickModal.dataset.quickWaterModalBound = "true";

            quickModal.addEventListener("click", function (event) {
                if (event.target === quickModal || event.target.closest("[data-quick-water-cancel]")) {
                    closeQuickWaterModal(quickModal);
                }
            });

            quickModal.querySelectorAll("input[name='apply_to_all']").forEach(function (input) {
                input.addEventListener("change", function () {
                    setQuickWaterPlantSelection(quickModal);
                });
            });
        });

        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") {
                return;
            }

            document.querySelectorAll(".profile-quick-action-backdrop.is-open").forEach(closeQuickWaterModal);
        });
    }

    function initDiaryList() {
        if (!document.querySelector(".profile-diary-wrap")) {
            return;
        }

        const deleteLinks = document.querySelectorAll(".profile-diary-card-archive-btn, .profile-diary-card-state__actions a[href*='/delete/']");
        const modal = document.getElementById("diaryDeleteConfirm");
        const confirmButton = modal ? modal.querySelector("[data-confirm-submit]") : null;
        const cancelButton = modal ? modal.querySelector("[data-confirm-cancel]") : null;
        const menuToggles = document.querySelectorAll("[data-diary-card-menu-toggle]");
        const diaryActionButtons = document.querySelectorAll("[data-diary-card-action-open]");
        const diaryViewTabs = document.querySelectorAll("[data-diary-view-tab]");
        const diaryViewCards = document.querySelectorAll("[data-diary-view-card]");
        const diaryViewEmptyStates = document.querySelectorAll("[data-diary-view-empty]");
        const diaryViewStaticEmptyStates = document.querySelectorAll("[data-diary-view-static-empty]");
        let pendingDelete = null;

        function closeAllCardMenus() {
            closeMenuGroup(".profile-diary-card-menu", "[data-diary-card-menu-toggle]", "[data-diary-card-menu-dropdown]");
        }

        function closeDiaryActionModal(modalElement) {
            setModalOpen(modalElement, false);
        }

        function openDiaryActionModal(modalElement) {
            if (!modalElement) {
                return;
            }

            setModalOpen(modalElement, true);
            focusFirstField(modalElement);
        }

        function closeArchiveModal() {
            setModalOpen(modal, false);
            pendingDelete = null;
        }

        function openArchiveModal(card, targetUrl) {
            if (!modal) {
                return;
            }

            pendingDelete = {card: card, targetUrl: targetUrl};
            setModalOpen(modal, true);

            if (confirmButton) {
                confirmButton.focus();
            }
        }

        function setDiaryView(activeView) {
            let visibleCards = 0;

            diaryViewTabs.forEach(function (tab) {
                const isActive = tab.getAttribute("data-diary-view-tab") === activeView;
                tab.classList.toggle("is-active", isActive);
                tab.setAttribute("aria-selected", String(isActive));
            });

            diaryViewCards.forEach(function (card) {
                const groups = (card.getAttribute("data-diary-view-groups") || "").split(/\s+/);
                const shouldShow = groups.includes(activeView);

                card.hidden = !shouldShow;
                if (shouldShow) {
                    visibleCards += 1;
                }
            });

            diaryViewStaticEmptyStates.forEach(function (emptyState) {
                emptyState.hidden = emptyState.getAttribute("data-diary-view-static-empty") !== activeView;
            });

            diaryViewEmptyStates.forEach(function (emptyState) {
                const isTarget = emptyState.getAttribute("data-diary-view-empty") === activeView;
                emptyState.hidden = !isTarget || visibleCards > 0;
            });

            closeAllCardMenus();
        }

        window.addEventListener("pageshow", closeAllCardMenus);

        diaryViewTabs.forEach(function (tab) {
            tab.addEventListener("click", function () {
                setDiaryView(tab.getAttribute("data-diary-view-tab") || "all");
            });
        });

        setDiaryView("all");

        deleteLinks.forEach(function (link) {
            link.addEventListener("click", function (event) {
                event.preventDefault();

                const card = link.closest(".profile-diary-card");
                const targetUrl = link.getAttribute("href");

                if (!card || !targetUrl || card.classList.contains("is-deleting")) {
                    return;
                }

                openArchiveModal(card, targetUrl);
            });
        });

        bindMenuToggles(menuToggles, {
            menuSelector: ".profile-diary-card-menu",
            dropdownSelector: "[data-diary-card-menu-dropdown]",
            closeAll: closeAllCardMenus,
        });

        document.querySelectorAll(".profile-diary-card-menu__action").forEach(function (action) {
            action.addEventListener("click", closeAllCardMenus);
        });

        document.querySelectorAll(".profile-diary-item-modal__form").forEach(function (formElement) {
            bindDiaryItemForm(formElement, "input[name$='apply_to_all']");
        });

        diaryActionButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                const modalId = button.getAttribute("data-diary-card-action-open");
                const actionPreset = button.getAttribute("data-diary-action-preset");
                pendingActionFocusSelector = actionPreset
                    ? '[data-diary-card-action-open="' + modalId + '"][data-diary-action-preset="' + actionPreset + '"]'
                    : '[data-diary-card-action-open="' + modalId + '"]';
                const actionModal = document.getElementById(modalId);
                openDiaryActionModal(actionModal);
                if (actionPreset && actionModal) {
                    const actionInput = actionModal.querySelector("select[name$='action_type']");
                    if (actionInput) {
                        actionInput.value = actionPreset;
                        actionInput.dispatchEvent(new Event("change", {bubbles: true}));
                    }
                }
            });
        });

        document.querySelectorAll(".profile-diary-item-modal").forEach(function (actionModal) {
            actionModal.addEventListener("click", function (event) {
                if (
                    event.target === actionModal ||
                    event.target.closest("[data-diary-card-action-cancel]") ||
                    event.target.closest("[data-diary-item-modal-cancel]")
                ) {
                    closeDiaryActionModal(actionModal);
                }
            });
        });

        if (cancelButton) {
            cancelButton.addEventListener("click", closeArchiveModal);
        }

        if (modal) {
            modal.addEventListener("click", function (event) {
                if (event.target === modal) {
                    closeArchiveModal();
                }
            });
        }

        if (confirmButton) {
            confirmButton.addEventListener("click", function () {
                if (!pendingDelete || !pendingDelete.card || !pendingDelete.targetUrl) {
                    closeArchiveModal();
                    return;
                }

                const card = pendingDelete.card;
                const targetUrl = pendingDelete.targetUrl;

                card.classList.add("is-deleting");
                closeArchiveModal();

                window.setTimeout(function () {
                    window.location.href = targetUrl;
                }, 320);
            });
        }

        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") {
                return;
            }

            if (modal && modal.classList.contains("is-open")) {
                closeArchiveModal();
            }

            document.querySelectorAll(".profile-diary-item-modal.is-open").forEach(closeDiaryActionModal);
            closeAllCardMenus();
        });

        document.addEventListener("click", function (event) {
            if (event.target.closest(".profile-diary-card-menu")) {
                return;
            }

            closeAllCardMenus();
        });
    }

    function initDiaryDetail() {
        if (!document.querySelector(".profile-diary-detail-wrap")) {
            return;
        }

        const deleteLinks = document.querySelectorAll(".profile-diary-item-delete-btn");
        const modal = document.getElementById("diaryItemDeleteConfirm");
        const confirmButton = modal ? modal.querySelector("[data-item-confirm-submit]") : null;
        const cancelButton = modal ? modal.querySelector("[data-item-confirm-cancel]") : null;
        const recommendationToggle = document.querySelector("[data-recommendation-toggle]");
        const recommendationDetails = document.querySelector("[data-recommendation-details]");
        const plantTabTriggers = document.querySelectorAll("[data-plant-tab-trigger]");
        const plantTabPanels = document.querySelectorAll("[data-plant-tab-panel]");
        const plantMenuToggles = document.querySelectorAll("[data-diary-plant-menu-toggle]");
        const entryMenuToggles = document.querySelectorAll("[data-diary-entry-menu-toggle]");
        const detailMenuToggles = document.querySelectorAll("[data-diary-detail-menu-toggle]");
        const diaryItemModal = document.getElementById("diaryItemAddModal");
        const diaryItemModalOpenButtons = document.querySelectorAll("[data-diary-item-modal-open]");
        const diaryItemModalCancel = diaryItemModal ? diaryItemModal.querySelectorAll("[data-diary-item-modal-cancel]") : [];
        const plantMoveLinks = document.querySelectorAll("[data-plant-move-open]");
        const plantArchiveLinks = document.querySelectorAll("[data-plant-archive-open]");
        let pendingDelete = null;

        function closeAllMenus() {
            closeMenuGroup(".profile-diary-detail-menu", "[data-diary-detail-menu-toggle]", "[data-diary-detail-menu-dropdown]");
            closeMenuGroup(".profile-diary-entry-menu", "[data-diary-entry-menu-toggle]", "[data-diary-entry-menu-dropdown]");
            closeMenuGroup(".profile-diary-plant-menu", "[data-diary-plant-menu-toggle]", "[data-diary-plant-menu-dropdown]");
        }

        function closeDeleteModal() {
            setModalOpen(modal, false);
            pendingDelete = null;
        }

        function openDeleteModal(card, targetUrl) {
            if (!modal) {
                return;
            }

            pendingDelete = {card: card, targetUrl: targetUrl};
            setModalOpen(modal, true);

            if (confirmButton) {
                confirmButton.focus();
            }
        }

        function closeDiaryItemModal() {
            setModalOpen(diaryItemModal, false);
        }

        function openDiaryItemModal() {
            if (!diaryItemModal) {
                return;
            }

            closeAllMenus();
            setModalOpen(diaryItemModal, true);
            focusFirstField(diaryItemModal);
        }

        function closePlantActionModal(modalElement) {
            setModalOpen(modalElement, false);
        }

        function openPlantActionModal(modalElement) {
            if (!modalElement) {
                return;
            }

            closeAllMenus();
            setModalOpen(modalElement, true);
            focusFirstField(modalElement);
        }

        window.addEventListener("pageshow", closeAllMenus);

        deleteLinks.forEach(function (link) {
            link.addEventListener("click", function (event) {
                event.preventDefault();

                const card = link.closest(".profile-diary-card");
                const targetUrl = link.getAttribute("href");

                if (!card || !targetUrl || card.classList.contains("is-deleting")) {
                    return;
                }

                openDeleteModal(card, targetUrl);
            });
        });

        document.querySelectorAll(".profile-diary-item-modal__form").forEach(function (formElement) {
            bindDiaryItemForm(formElement, "input[name='apply_to_all']");
        });

        document.querySelectorAll(".profile-diary-detail-menu__action, .profile-diary-entry-menu__action, .profile-diary-plant-menu__action").forEach(function (action) {
            action.addEventListener("click", closeAllMenus);
        });

        diaryItemModalOpenButtons.forEach(function (button) {
            button.addEventListener("click", function (event) {
                if (!diaryItemModal) {
                    return;
                }

                event.preventDefault();
                const focusKey = button.getAttribute("data-diary-focus-key");
                const actionPreset = button.getAttribute("data-diary-action-preset");
                pendingActionFocusSelector = focusKey
                    ? '[data-diary-focus-key="' + focusKey + '"]'
                    : actionPreset
                        ? '[data-diary-action-preset="' + actionPreset + '"]'
                        : "[data-diary-item-modal-open]";
                openDiaryItemModal();
                if (actionPreset) {
                    const actionInput = diaryItemModal.querySelector("select[name$='action_type']");
                    if (actionInput) {
                        actionInput.value = actionPreset;
                        actionInput.dispatchEvent(new Event("change", {bubbles: true}));
                    }
                }
            });
        });

        diaryItemModalCancel.forEach(function (button) {
            button.addEventListener("click", closeDiaryItemModal);
        });

        if (diaryItemModal) {
            diaryItemModal.addEventListener("click", function (event) {
                if (event.target === diaryItemModal) {
                    closeDiaryItemModal();
                }
            });
        }

        plantMoveLinks.forEach(function (link) {
            link.addEventListener("click", function (event) {
                const modalId = link.getAttribute("data-plant-move-open");
                const actionModal = document.getElementById(modalId);

                if (!actionModal) {
                    return;
                }

                event.preventDefault();
                openPlantActionModal(actionModal);
            });
        });

        plantArchiveLinks.forEach(function (link) {
            link.addEventListener("click", function (event) {
                const modalId = link.getAttribute("data-plant-archive-open");
                const actionModal = document.getElementById(modalId);

                if (!actionModal) {
                    return;
                }

                event.preventDefault();
                openPlantActionModal(actionModal);
            });
        });

        document.querySelectorAll(".profile-plant-move-modal, .profile-plant-archive-modal").forEach(function (actionModal) {
            actionModal.addEventListener("click", function (event) {
                if (event.target === actionModal || event.target.closest("[data-plant-action-cancel]")) {
                    closePlantActionModal(actionModal);
                }
            });
        });

        bindMenuToggles(entryMenuToggles, {
            menuSelector: ".profile-diary-entry-menu",
            dropdownSelector: "[data-diary-entry-menu-dropdown]",
            closeAll: closeAllMenus,
        });
        bindMenuToggles(detailMenuToggles, {
            menuSelector: ".profile-diary-detail-menu",
            dropdownSelector: "[data-diary-detail-menu-dropdown]",
            closeAll: closeAllMenus,
        });
        bindMenuToggles(plantMenuToggles, {
            menuSelector: ".profile-diary-plant-menu",
            dropdownSelector: "[data-diary-plant-menu-dropdown]",
            closeAll: closeAllMenus,
        });

        if (cancelButton) {
            cancelButton.addEventListener("click", closeDeleteModal);
        }

        if (modal) {
            modal.addEventListener("click", function (event) {
                if (event.target === modal) {
                    closeDeleteModal();
                }
            });
        }

        if (confirmButton) {
            confirmButton.addEventListener("click", function () {
                if (!pendingDelete || !pendingDelete.card || !pendingDelete.targetUrl) {
                    closeDeleteModal();
                    return;
                }

                const card = pendingDelete.card;
                const targetUrl = pendingDelete.targetUrl;

                card.classList.add("is-deleting");
                closeDeleteModal();

                window.setTimeout(function () {
                    window.location.href = targetUrl;
                }, 320);
            });
        }

        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") {
                return;
            }

            if (modal && modal.classList.contains("is-open")) {
                closeDeleteModal();
            }

            if (diaryItemModal && diaryItemModal.classList.contains("is-open")) {
                closeDiaryItemModal();
            }

            document.querySelectorAll(".profile-plant-move-modal.is-open, .profile-plant-archive-modal.is-open").forEach(closePlantActionModal);
            closeAllMenus();
        });

        if (recommendationToggle && recommendationDetails) {
            recommendationToggle.addEventListener("click", function () {
                const isExpanded = recommendationToggle.getAttribute("aria-expanded") === "true";

                recommendationToggle.setAttribute("aria-expanded", String(!isExpanded));
                recommendationToggle.textContent = isExpanded ? "Детальніше" : "Згорнути";
                recommendationDetails.hidden = isExpanded;
            });
        }

        if (plantTabTriggers.length && plantTabPanels.length) {
            plantTabTriggers.forEach(function (trigger) {
                trigger.addEventListener("click", function () {
                    const target = trigger.getAttribute("data-target");

                    plantTabTriggers.forEach(function (button) {
                        const isActive = button === trigger;
                        button.classList.toggle("is-active", isActive);
                        button.setAttribute("aria-selected", String(isActive));
                    });

                    plantTabPanels.forEach(function (panel) {
                        panel.hidden = panel.getAttribute("data-plant-tab-panel") !== target;
                    });
                });
            });
        }

        const filtersToggle = document.querySelector("[data-diary-filter-toggle]");
        const filtersPanel = document.querySelector("[data-diary-filters-panel]");

        if (filtersToggle && filtersPanel) {
            filtersToggle.addEventListener("click", function () {
                const isExpanded = filtersToggle.getAttribute("aria-expanded") === "true";
                filtersToggle.setAttribute("aria-expanded", String(!isExpanded));
                filtersPanel.classList.toggle("is-collapsed", isExpanded);
            });
        }

        document.addEventListener("click", function (event) {
            if (
                event.target.closest(".profile-diary-detail-menu") ||
                event.target.closest(".profile-diary-entry-menu") ||
                event.target.closest(".profile-diary-plant-menu")
            ) {
                return;
            }

            closeAllMenus();
        });
    }

    function initDiaryItemFormPage() {
        document.querySelectorAll(".profile-diary-item-form").forEach(function (formElement) {
            bindDiaryItemForm(formElement, "input[name$='apply_to_all']");
        });
    }

    function initPlantFormsets() {
        document.querySelectorAll("[data-plant-formset]").forEach(function (formset) {
            if (formset.dataset.plantFormsetBound === "true") {
                return;
            }
            formset.dataset.plantFormsetBound = "true";

            const addButton = formset.querySelector("[data-plant-form-add]");
            const rows = formset.querySelector("[data-plant-form-rows]");
            const template = formset.querySelector("[data-plant-form-template]");
            const totalForms = formset.querySelector('[name="plants-TOTAL_FORMS"]');

            function initAutocomplete(row) {
                if (!window.django || !window.django.jQuery) {
                    return;
                }

                const $ = window.django.jQuery;
                $(document).trigger("formset:added", [$(row), "plants"]);
                $(row).find("[data-autocomplete-light-function]").each(function () {
                    $(this).trigger("autocompleteLightInitialize");
                });
            }

            function initDatepickers(row) {
                if (typeof window.initProfileDatepickers !== "function") {
                    return;
                }

                window.initProfileDatepickers(row);
            }

            function bindRemove(row) {
                if (!row || row.dataset.plantRemoveBound === "true") {
                    return;
                }
                row.dataset.plantRemoveBound = "true";

                const removeButton = row.querySelector("[data-plant-form-remove]");
                const deleteInput = row.querySelector('[name$="-DELETE"]');

                if (!removeButton || !deleteInput) {
                    return;
                }

                removeButton.addEventListener("click", function () {
                    const removeMode = row.dataset.plantRemoveMode || "row";
                    const removeMessage = row.dataset.plantRemoveMessage || "";

                    if (removeMode === "blocked") {
                        if (removeMessage) {
                            window.alert(removeMessage);
                        }
                        return;
                    }

                    if ((removeMode === "delete" || removeMode === "finish") && removeMessage) {
                        if (!window.confirm(removeMessage)) {
                            return;
                        }
                    }

                    deleteInput.checked = true;
                    row.hidden = true;
                });
            }

            if (!rows) {
                return;
            }

            rows.querySelectorAll("[data-plant-form-row]").forEach(function (row) {
                bindRemove(row);
                initDatepickers(row);
            });

            if (addButton && template && totalForms) {
                addButton.addEventListener("click", function () {
                    const index = Number(totalForms.value);
                    const html = template.innerHTML.replace(/__prefix__/g, String(index));

                    rows.insertAdjacentHTML("beforeend", html);
                    totalForms.value = String(index + 1);

                    const row = rows.lastElementChild;
                    bindRemove(row);
                    initAutocomplete(row);
                    initDatepickers(row);
                });
            }
        });
    }

    function initDiaryInteractions() {
        initHtmxDiaryEvents();
        initAsyncFormFallback(document);
        initLazyRecommendation(document);
        initDateShortcuts(document);
        initDiaryItemFormPage();
        initPlantFormsets();
        initQuickWaterActions();
        initDiaryList();
        initDiaryDetail();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initDiaryInteractions);
    } else {
        initDiaryInteractions();
    }
})();
