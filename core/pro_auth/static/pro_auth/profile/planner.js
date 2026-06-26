(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const root = document.querySelector("[data-planner-root]");
        if (!root) return;

        const canvas = root.querySelector("[data-planner-canvas]");
        const createForm = root.querySelector("[data-planner-area-form]");
        const inspectorForm = root.querySelector("[data-planner-inspector-form]");
        const inspectorEmpty = root.querySelector("[data-planner-inspector-empty]");
        const inspectorTitle = root.querySelector("[data-planner-inspector-title]");
        const inspectorPosition = root.querySelector("[data-planner-position]");
        const inspectorDiary = root.querySelector("[data-planner-inspector-diary]");
        const inspectorTasks = root.querySelector("[data-planner-inspector-tasks]");
        const inspectorStatus = root.querySelector("[data-planner-inspector-status]");
        const createStatus = root.querySelector("[data-planner-form-status]");
        const emptyState = root.querySelector("[data-planner-empty]");
        const zoneCount = root.querySelector("[data-planner-zone-count]");
        const usedArea = root.querySelector("[data-planner-used-area]");
        const linkedCount = root.querySelector("[data-planner-linked-count]");
        const deleteButton = root.querySelector("[data-planner-area-delete]");
        const rotateButton = root.querySelector("[data-planner-area-rotate]");
        const plantingsSection = root.querySelector("[data-planner-plantings]");
        const plantingList = root.querySelector("[data-planner-planting-list]");
        const plantingCount = root.querySelector("[data-planner-planting-count]");
        const plantingForm = root.querySelector("[data-planner-planting-form]");
        const plantingStatus = root.querySelector("[data-planner-planting-status]");
        const plantingMode = root.querySelector("[data-planner-planting-mode]");
        const plantSelect = root.querySelector("[data-planner-plant-select]");
        const existingPlantField = root.querySelector("[data-planner-existing-plant]");
        const newPlantFields = root.querySelector("[data-planner-new-plant]");
        const plantSourceInputs = root.querySelectorAll("[name='plant_source']");
        const autoLayoutButton = root.querySelector("[data-planner-auto-layout]");
        const copyDetails = root.querySelector(".planner-copy");
        const progressValue = root.querySelector("[data-planner-progress-value]");
        const progressBar = root.querySelector("[data-planner-progress-bar]");
        const progressSteps = root.querySelectorAll("[data-planner-progress-step]");
        const tasksPanel = root.querySelector(".planner-tasks");
        const taskFilterButtons = root.querySelectorAll("[data-task-filter-button]");
        const taskFilterEmpty = root.querySelector("[data-task-filter-empty]");
        const taskTitleInput = root.querySelector("[data-task-title-input]");
        const taskTemplateButtons = root.querySelectorAll("[data-task-template]");
        const taskDateInput = root.querySelector("[data-task-date-input]");
        const taskAreaSelect = root.querySelector("[data-task-area-select]");
        const taskDateShortcutButtons = root.querySelectorAll("[data-task-date-shortcut]");
        const widthM = Number(root.dataset.width);
        const heightM = Number(root.dataset.height);
        const gridStep = Number(root.dataset.gridStep) || 0.5;
        const updateTemplate = root.dataset.areaUpdateTemplate;
        const deleteTemplate = root.dataset.areaDeleteTemplate;
        const plantingAddTemplate = root.dataset.plantingAddTemplate;
        const plantingDeleteTemplate = root.dataset.plantingDeleteTemplate;
        const plantingUpdateTemplate = root.dataset.plantingUpdateTemplate;
        const areasData = document.getElementById("planner-areas-data");
        const areas = areasData ? JSON.parse(areasData.textContent) : [];
        const plantingStatusesData = document.getElementById("planner-planting-statuses");
        const plantingStatuses = plantingStatusesData ? JSON.parse(plantingStatusesData.textContent) : [];
        let selectedArea = null;
        let interaction = null;
        let plantingInteraction = null;

        function formatDateInput(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, "0");
            const day = String(date.getDate()).padStart(2, "0");
            return year + "-" + month + "-" + day;
        }

        if (copyDetails) {
            document.addEventListener("click", function (event) {
                if (copyDetails.open && !copyDetails.contains(event.target)) copyDetails.open = false;
            });
            document.addEventListener("keydown", function (event) {
                if (event.key === "Escape" && copyDetails.open) {
                    copyDetails.open = false;
                    copyDetails.querySelector("summary").focus();
                }
            });
        }

        function applyTaskFilter(filter) {
            if (!tasksPanel) return;
            tasksPanel.dataset.taskFilter = filter;
            taskFilterButtons.forEach(function (button) {
                button.classList.toggle("is-active", button.dataset.taskFilterButton === filter);
            });
            const tasks = Array.from(tasksPanel.querySelectorAll(".planner-task"));
            const matchingTasks = tasks.filter(function (task) {
                if (filter === "all") return true;
                if (filter === "active") return !task.classList.contains("is-complete");
                if (filter === "completed") return task.classList.contains("is-complete");
                return task.dataset.taskBucket === filter;
            });
            tasks.forEach(function (task) {
                task.hidden = matchingTasks.indexOf(task) === -1;
            });
            tasksPanel.querySelectorAll(".planner-task-group").forEach(function (group) {
                const visibleTasks = Array.from(group.querySelectorAll(".planner-task")).filter(function (task) {
                    return !task.hidden;
                });
                group.hidden = visibleTasks.length === 0;
            });
            if (taskFilterEmpty) taskFilterEmpty.hidden = matchingTasks.length > 0;
        }

        taskFilterButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                applyTaskFilter(button.dataset.taskFilterButton);
            });
        });
        if (tasksPanel) applyTaskFilter(tasksPanel.dataset.taskFilter || "active");

        taskTemplateButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (!taskTitleInput) return;
                taskTitleInput.value = button.dataset.taskTemplate || button.textContent.trim();
                taskTitleInput.focus();
            });
        });

        taskDateShortcutButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                if (!taskDateInput) return;
                const shortcut = button.dataset.taskDateShortcut;
                if (shortcut === "clear") {
                    taskDateInput.value = "";
                    taskDateInput.focus();
                    return;
                }
                const date = new Date();
                if (shortcut === "tomorrow") date.setDate(date.getDate() + 1);
                if (shortcut === "week") date.setDate(date.getDate() + 7);
                taskDateInput.value = formatDateInput(date);
                taskDateInput.focus();
            });
        });

        root.querySelectorAll(".planner-task__edit").forEach(function (details) {
            details.addEventListener("toggle", function () {
                if (!details.open) return;
                root.querySelectorAll(".planner-task__edit").forEach(function (other) {
                    if (other !== details) other.open = false;
                });
            });
        });

        if (inspectorTasks) {
            inspectorTasks.addEventListener("click", function (event) {
                const button = event.target.closest("[data-plan-area-task]");
                if (!button || !selectedArea) return;
                if (tasksPanel) {
                    tasksPanel.open = true;
                    applyTaskFilter("active");
                    tasksPanel.scrollIntoView({ block: "start", behavior: "smooth" });
                }
                if (taskAreaSelect) taskAreaSelect.value = String(selectedArea.id);
                if (taskTitleInput) {
                    taskTitleInput.placeholder = "Наприклад, полити " + selectedArea.title;
                    taskTitleInput.focus();
                }
            });
        }

        function endpoint(template, id) {
            return template.replace(/\/0\//, "/" + id + "/");
        }

        function csrfToken() {
            const input = createForm.querySelector("[name='csrfmiddlewaretoken']");
            return input ? input.value : "";
        }

        function snap(value) {
            return Math.round(value / gridStep) * gridStep;
        }

        function clamp(value, minimum, maximum) {
            return Math.min(Math.max(value, minimum), maximum);
        }

        function formatNumber(value) {
            return Number(value).toLocaleString("uk-UA", { maximumFractionDigits: 2 });
        }

        function taskSummary(area) {
            return area.tasks || { openCount: 0, overdueCount: 0, nextTitle: "", nextDate: "", nextBucket: "" };
        }

        function taskCountLabel(count) {
            if (count % 10 === 1 && count % 100 !== 11) return count + " справа";
            if ([2, 3, 4].indexOf(count % 10) !== -1 && [12, 13, 14].indexOf(count % 100) === -1) {
                return count + " справи";
            }
            return count + " справ";
        }

        function escapeHTML(value) {
            return String(value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/\"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function post(url, formData) {
            return fetch(url, {
                method: "POST",
                headers: { "X-CSRFToken": csrfToken() },
                body: formData,
                credentials: "same-origin",
            }).then(function (response) {
                if (!response.ok) throw new Error("Не вдалося зберегти зміни");
                return response.json();
            });
        }

        function areaFormData(area) {
            const data = new FormData();
            data.append("x_m", area.x);
            data.append("y_m", area.y);
            data.append("width_m", area.width);
            data.append("height_m", area.height);
            return data;
        }

        function persistArea(area) {
            return post(endpoint(updateTemplate, area.id), areaFormData(area))
                .then(function (payload) {
                    Object.assign(area, payload.area);
                    selectArea(area);
                    return area;
                });
        }

        function persistPlanting(planting) {
            const data = new FormData();
            data.append("x_pct", planting.x);
            data.append("y_pct", planting.y);
            data.append("width_pct", planting.width);
            data.append("height_pct", planting.height);
            data.append("status", planting.status);
            return post(endpoint(plantingUpdateTemplate, planting.id), data).then(function (payload) {
                Object.assign(planting, payload.planting);
                return planting;
            });
        }

        function applyGeometry(element, area) {
            element.style.left = (area.x / widthM * 100) + "%";
            element.style.top = (area.y / heightM * 100) + "%";
            element.style.width = (area.width / widthM * 100) + "%";
            element.style.height = (area.height / heightM * 100) + "%";
            element.style.setProperty("--zone-color", area.color);
            const meta = element.querySelector("[data-zone-meta]");
            if (meta) meta.textContent = formatNumber(area.width) + " × " + formatNumber(area.height) + " м";
        }

        function applyPlantingGeometry(element, planting) {
            element.style.left = planting.x + "%";
            element.style.top = planting.y + "%";
            element.style.width = planting.width + "%";
            element.style.height = planting.height + "%";
        }

        function plantingElement(planting, area) {
            const element = document.createElement("div");
            element.className = "planner-zone-planting planner-zone-planting--" + planting.mode + " planner-zone-planting--status-" + planting.status;
            element.dataset.plantingId = planting.id;
            element.tabIndex = 0;
            element.setAttribute("aria-label", planting.plantName + ", " + planting.summary);
            let visual = "<span class=\"planner-zone-planting__emoji\">" + escapeHTML(planting.emoji) + "</span>";
            if (planting.mode === "exact" || planting.mode === "approximate") {
                const iconCount = Math.min(Number(planting.quantity) || 1, 12);
                visual = "<span class=\"planner-zone-planting__cluster\">" +
                    Array(iconCount).fill("<i>" + escapeHTML(planting.emoji) + "</i>").join("") +
                    "</span>";
            }
            element.innerHTML =
                visual +
                "<span class=\"planner-zone-planting__label\">" + escapeHTML(planting.summary) + "</span>" +
                "<button type=\"button\" data-planting-resize aria-label=\"Змінити зайняту площу\"></button>";
            element.style.setProperty("--row-count", Math.max(Number(planting.rows) || 3, 1));
            applyPlantingGeometry(element, planting);
            element.addEventListener("pointerdown", function (event) {
                event.stopPropagation();
                const mode = event.target.closest("[data-planting-resize]") ? "resize" : "move";
                plantingInteraction = {
                    planting: planting,
                    area: area,
                    element: element,
                    zone: element.closest(".planner-zone"),
                    mode: mode,
                    startX: event.clientX,
                    startY: event.clientY,
                    initialX: planting.x,
                    initialY: planting.y,
                    initialWidth: planting.width,
                    initialHeight: planting.height,
                };
                if (element.setPointerCapture) element.setPointerCapture(event.pointerId);
                event.preventDefault();
            });
            element.addEventListener("click", function (event) {
                event.stopPropagation();
                selectArea(area);
            });
            return element;
        }

        function zoneElement(area) {
            const element = document.createElement("article");
            element.className = "planner-zone";
            element.tabIndex = 0;
            element.dataset.zoneId = area.id;
            element.setAttribute("aria-label", area.areaTypeLabel + " " + area.title);
            const visualPlants = (area.plantings || []).length ? area.plantings : area.plants;
            const plantIcons = visualPlants.slice(0, 8).map(function (plant) {
                const plantName = plant.plantName || plant.name;
                return "<span title=\"" + escapeHTML(plantName) + "\">" + escapeHTML(plant.emoji) + "</span>";
            }).join("");
            element.innerHTML =
                "<div>" +
                    "<div class=\"planner-zone__type\"><span aria-hidden=\"true\">✥</span> " + escapeHTML(area.areaTypeLabel) + "</div>" +
                    "<h3 class=\"planner-zone__title\">" + escapeHTML(area.title) + "</h3>" +
                    "<div class=\"planner-zone__meta\" data-zone-meta></div>" +
                "</div>" +
                "<div class=\"planner-zone__planting-layer\" data-zone-planting-layer></div>" +
                (!area.plantings.length && plantIcons ? "<div class=\"planner-zone__plants\">" + plantIcons + "</div>" : "") +
                (taskSummary(area).openCount ? "<div class=\"planner-zone__tasks" + (taskSummary(area).overdueCount ? " is-overdue" : "") + "\">" + escapeHTML(taskCountLabel(taskSummary(area).openCount)) + "</div>" : "") +
                "<button class=\"planner-zone__rotate\" type=\"button\" aria-label=\"Повернути грядку на 90 градусів\" data-zone-rotate>↻</button>" +
                "<button class=\"planner-zone__resize\" type=\"button\" aria-label=\"Змінити розмір\" data-zone-resize></button>";
            const plantingLayer = element.querySelector("[data-zone-planting-layer]");
            area.plantings.forEach(function (planting) {
                plantingLayer.appendChild(plantingElement(planting, area));
            });
            applyGeometry(element, area);
            element.addEventListener("click", function () { selectArea(area); });
            element.addEventListener("focus", function () { selectArea(area); });
            element.addEventListener("pointerdown", function (event) { startInteraction(event, area, element); });
            element.addEventListener("keydown", function (event) { moveAreaWithKeyboard(event, area, element); });
            element.querySelector("[data-zone-rotate]").addEventListener("click", function (event) {
                event.stopPropagation();
                rotateArea(area, element);
            });
            return element;
        }

        function renderAll() {
            canvas.querySelectorAll("[data-zone-id]").forEach(function (element) { element.remove(); });
            areas.forEach(function (area) { canvas.appendChild(zoneElement(area)); });
            updateSummary();
        }

        function updateSummary() {
            zoneCount.textContent = areas.length;
            usedArea.textContent = formatNumber(areas.reduce(function (sum, area) { return sum + area.width * area.height; }, 0)) + " м²";
            linkedCount.textContent = areas.filter(function (area) { return Boolean(area.diaryId); }).length;
            emptyState.classList.toggle("is-hidden", areas.length > 0);
            updateProgress();
        }

        function updateProgress() {
            const plantings = areas.reduce(function (items, area) {
                return items.concat(area.plantings || []);
            }, []);
            const completed = [
                true,
                areas.length > 0,
                plantings.length > 0,
                plantings.some(function (planting) { return planting.status !== "planned"; }),
            ];
            const percent = completed.filter(Boolean).length * 25;
            if (progressValue) progressValue.textContent = percent + "%";
            if (progressBar) progressBar.style.width = percent + "%";
            progressSteps.forEach(function (step, index) {
                step.classList.toggle("is-complete", completed[index]);
                const badge = step.querySelector(":scope > span");
                if (badge) badge.textContent = completed[index] ? "✓" : String(index + 1);
            });
        }

        function refreshZone(area) {
            const oldElement = canvas.querySelector("[data-zone-id='" + area.id + "']");
            const newElement = zoneElement(area);
            if (oldElement) oldElement.replaceWith(newElement);
            else canvas.appendChild(newElement);
            updateProgress();
            selectArea(area);
        }

        function renderPlantings(area) {
            const plantings = area.plantings || [];
            plantingCount.textContent = plantings.length;
            if (!plantings.length) {
                plantingList.innerHTML = "<p class=\"planner-plantings__empty\">Рослини ще не розміщені. Можна вказати точну кількість, приблизну, ряди, площу або суцільний посів.</p>";
                return;
            }
            plantingList.innerHTML = "";
            plantings.forEach(function (planting) {
                const card = document.createElement("article");
                card.className = "planner-planting-card";
                const statusOptions = plantingStatuses.map(function (choice) {
                    return "<option value=\"" + escapeHTML(choice[0]) + "\"" + (choice[0] === planting.status ? " selected" : "") + ">" + escapeHTML(choice[1]) + "</option>";
                }).join("");
                const guidanceItems = planting.guidance && planting.guidance.items ? planting.guidance.items : [];
                const guidance = guidanceItems.length
                    ? "<p class=\"planner-planting-card__guidance\"><span>AI-підказка</span> " + escapeHTML(guidanceItems[0]) + "<small>Джерело: " + escapeHTML(planting.guidance.source) + "</small></p>"
                    : "";
                card.innerHTML =
                    "<span class=\"planner-planting-card__emoji\">" + escapeHTML(planting.emoji) + "</span>" +
                    "<div class=\"planner-planting-card__main\"><strong>" + escapeHTML(planting.plantName) + "</strong><small>" + escapeHTML(planting.summary) + "</small>" +
                    "<select data-planting-status aria-label=\"Статус посадки\">" + statusOptions + "</select>" + guidance + "</div>" +
                    "<button type=\"button\" aria-label=\"Прибрати рослину з грядки\" data-planting-delete>×</button>";
                card.querySelector("[data-planting-status]").addEventListener("change", function (event) {
                    planting.status = event.target.value;
                    plantingStatus.textContent = "Оновлюємо статус…";
                    persistPlanting(planting)
                        .then(function () {
                            plantingStatus.textContent = "Статус оновлено.";
                            refreshZone(area);
                        })
                        .catch(function (error) {
                            plantingStatus.textContent = error.message;
                            plantingStatus.classList.add("is-error");
                        });
                });
                card.querySelector("[data-planting-delete]").addEventListener("click", function () {
                    if (!window.confirm("Прибрати цю рослину з плану? Сама рослина та її історія залишаться.")) return;
                    post(endpoint(plantingDeleteTemplate, planting.id), new FormData())
                        .then(function () {
                            const index = plantings.findIndex(function (item) { return item.id === planting.id; });
                            if (index !== -1) plantings.splice(index, 1);
                            const option = document.createElement("option");
                            option.value = planting.plantId;
                            option.textContent = planting.emoji + " " + planting.plantName;
                            plantSelect.appendChild(option);
                            refreshZone(area);
                        })
                        .catch(function (error) {
                            plantingStatus.textContent = error.message;
                            plantingStatus.classList.add("is-error");
                        });
                });
                plantingList.appendChild(card);
            });
        }

        function selectArea(area) {
            selectedArea = area;
            canvas.querySelectorAll(".planner-zone").forEach(function (element) {
                element.classList.toggle("is-selected", Number(element.dataset.zoneId) === area.id);
            });
            inspectorEmpty.hidden = true;
            inspectorForm.hidden = false;
            plantingsSection.hidden = false;
            deleteButton.hidden = false;
            inspectorTitle.textContent = area.title;
            inspectorForm.elements.title.value = area.title;
            inspectorForm.elements.area_type.value = area.areaType;
            inspectorForm.elements.width_m.value = area.width;
            inspectorForm.elements.height_m.value = area.height;
            inspectorPosition.textContent = formatNumber(area.x) + " × " + formatNumber(area.y) + " м від верхнього лівого кута";
            inspectorDiary.innerHTML = area.diaryId
                ? "<p>Підключений щоденник</p><a href=\"" + escapeHTML(area.diaryUrl) + "\">" + escapeHTML(area.diaryTitle) + " →</a>"
                : "<p>Щоденник ще не підключено</p>";
            const tasks = taskSummary(area);
            inspectorTasks.innerHTML = tasks.openCount
                ? "<p>Справи цієї зони</p><strong>" + escapeHTML(taskCountLabel(tasks.openCount)) + (tasks.overdueCount ? " · " + escapeHTML(String(tasks.overdueCount)) + " прострочено" : "") + "</strong>" +
                    (tasks.nextTitle ? "<small>Найближча: " + escapeHTML(tasks.nextTitle) + (tasks.nextDate ? " · " + escapeHTML(tasks.nextDate) : "") + "</small>" : "") +
                    "<button class=\"planner-inspector__task-action\" type=\"button\" data-plan-area-task>+ Запланувати справу</button>"
                : "<p>Справи цієї зони</p><strong>Немає активних справ</strong><small>Додайте першу справу саме для цієї грядки.</small><button class=\"planner-inspector__task-action\" type=\"button\" data-plan-area-task>+ Запланувати справу</button>";
            inspectorStatus.textContent = "";
            renderPlantings(area);
        }

        function startInteraction(event, area, element) {
            if (event.button !== 0) return;
            if (event.target.closest("[data-zone-rotate]")) return;
            if (event.target.closest("[data-planting-id]")) return;
            selectArea(area);
            const mode = event.target.closest("[data-zone-resize]") ? "resize" : "move";
            interaction = {
                area: area,
                element: element,
                mode: mode,
                startX: event.clientX,
                startY: event.clientY,
                initialX: area.x,
                initialY: area.y,
                initialWidth: area.width,
                initialHeight: area.height,
            };
            element.classList.add("is-dragging");
            if (element.setPointerCapture) element.setPointerCapture(event.pointerId);
            event.preventDefault();
        }

        document.addEventListener("pointermove", function (event) {
            if (plantingInteraction) {
                const zoneRect = plantingInteraction.zone.getBoundingClientRect();
                const deltaX = (event.clientX - plantingInteraction.startX) / zoneRect.width * 100;
                const deltaY = (event.clientY - plantingInteraction.startY) / zoneRect.height * 100;
                const planting = plantingInteraction.planting;
                if (plantingInteraction.mode === "move") {
                    planting.x = clamp(plantingInteraction.initialX + deltaX, 0, 100 - planting.width);
                    planting.y = clamp(plantingInteraction.initialY + deltaY, 0, 100 - planting.height);
                } else {
                    planting.width = clamp(plantingInteraction.initialWidth + deltaX, 5, 100 - planting.x);
                    planting.height = clamp(plantingInteraction.initialHeight + deltaY, 5, 100 - planting.y);
                }
                applyPlantingGeometry(plantingInteraction.element, planting);
                event.preventDefault();
                return;
            }
            if (!interaction) return;
            const rect = canvas.getBoundingClientRect();
            const deltaX = (event.clientX - interaction.startX) / rect.width * widthM;
            const deltaY = (event.clientY - interaction.startY) / rect.height * heightM;
            const area = interaction.area;
            if (interaction.mode === "move") {
                area.x = clamp(snap(interaction.initialX + deltaX), 0, widthM - area.width);
                area.y = clamp(snap(interaction.initialY + deltaY), 0, heightM - area.height);
            } else {
                area.width = clamp(snap(interaction.initialWidth + deltaX), 0.5, widthM - area.x);
                area.height = clamp(snap(interaction.initialHeight + deltaY), 0.5, heightM - area.y);
            }
            applyGeometry(interaction.element, area);
            selectArea(area);
            updateSummary();
            event.preventDefault();
        });

        function finishInteraction() {
            if (plantingInteraction) {
                const currentPlanting = plantingInteraction;
                plantingInteraction = null;
                persistPlanting(currentPlanting.planting)
                    .then(function () {
                        applyPlantingGeometry(currentPlanting.element, currentPlanting.planting);
                    })
                    .catch(function (error) {
                        plantingStatus.textContent = error.message;
                        plantingStatus.classList.add("is-error");
                    });
                return;
            }
            if (!interaction) return;
            const current = interaction;
            interaction = null;
            current.element.classList.remove("is-dragging");
            persistArea(current.area)
                .catch(function (error) { inspectorStatus.textContent = error.message; inspectorStatus.classList.add("is-error"); });
        }

        document.addEventListener("pointerup", finishInteraction);
        document.addEventListener("pointercancel", finishInteraction);

        function moveAreaWithKeyboard(event, area, element) {
            const directions = {
                ArrowLeft: [-gridStep, 0],
                ArrowRight: [gridStep, 0],
                ArrowUp: [0, -gridStep],
                ArrowDown: [0, gridStep],
            };
            if (!directions[event.key]) return;
            event.preventDefault();
            area.x = clamp(snap(area.x + directions[event.key][0]), 0, widthM - area.width);
            area.y = clamp(snap(area.y + directions[event.key][1]), 0, heightM - area.height);
            applyGeometry(element, area);
            selectArea(area);
            persistArea(area).catch(function (error) {
                inspectorStatus.textContent = error.message;
                inspectorStatus.classList.add("is-error");
            });
        }

        function rotateArea(area, element) {
            const nextWidth = Math.min(area.height, widthM);
            const nextHeight = Math.min(area.width, heightM);
            area.width = snap(nextWidth);
            area.height = snap(nextHeight);
            area.x = clamp(area.x, 0, widthM - area.width);
            area.y = clamp(area.y, 0, heightM - area.height);
            applyGeometry(element, area);
            selectArea(area);
            inspectorStatus.textContent = "Повертаємо…";
            persistArea(area)
                .then(function () { inspectorStatus.textContent = "Грядку повернуто на 90°."; })
                .catch(function (error) {
                    inspectorStatus.textContent = error.message;
                    inspectorStatus.classList.add("is-error");
                });
        }

        createForm.addEventListener("submit", function (event) {
            event.preventDefault();
            createStatus.textContent = "Зберігаємо…";
            createStatus.classList.remove("is-error");
            const data = new FormData(createForm);
            post(createForm.action, data)
                .then(function (payload) {
                    areas.push(payload.area);
                    canvas.appendChild(zoneElement(payload.area));
                    const diarySelect = createForm.querySelector("[data-planner-diary-select]");
                    if (payload.area.diaryId) {
                        const usedOption = diarySelect.querySelector("option[value='" + payload.area.diaryId + "']");
                        if (usedOption) usedOption.remove();
                    }
                    createStatus.textContent = "Зону додано. Тепер її можна пересувати.";
                    updateSummary();
                    selectArea(payload.area);
                })
                .catch(function (error) {
                    createStatus.textContent = error.message;
                    createStatus.classList.add("is-error");
                });
        });

        inspectorForm.addEventListener("submit", function (event) {
            event.preventDefault();
            if (!selectedArea) return;
            inspectorStatus.textContent = "Зберігаємо…";
            inspectorStatus.classList.remove("is-error");
            const data = new FormData(inspectorForm);
            data.append("x_m", selectedArea.x);
            data.append("y_m", selectedArea.y);
            post(endpoint(updateTemplate, selectedArea.id), data)
                .then(function (payload) {
                    Object.assign(selectedArea, payload.area);
                    refreshZone(selectedArea);
                    inspectorStatus.textContent = "Зміни збережено.";
                    updateSummary();
                })
                .catch(function (error) {
                    inspectorStatus.textContent = error.message;
                    inspectorStatus.classList.add("is-error");
                });
        });

        rotateButton.addEventListener("click", function () {
            if (!selectedArea) return;
            const element = canvas.querySelector("[data-zone-id='" + selectedArea.id + "']");
            if (element) rotateArea(selectedArea, element);
        });

        function updatePlantingFields() {
            const mode = plantingMode.value;
            root.querySelectorAll("[data-planting-field]").forEach(function (field) {
                const fieldType = field.dataset.plantingField;
                field.hidden = !(
                    (fieldType === "quantity" && (mode === "exact" || mode === "approximate")) ||
                    fieldType === mode
                );
            });
        }

        function updatePlantSource() {
            const checked = root.querySelector("[name='plant_source']:checked");
            const createsNewPlant = checked && checked.value === "new";
            existingPlantField.hidden = createsNewPlant;
            newPlantFields.hidden = !createsNewPlant;
            plantSelect.required = !createsNewPlant;
        }

        plantingMode.addEventListener("change", updatePlantingFields);
        plantSourceInputs.forEach(function (input) {
            input.addEventListener("change", updatePlantSource);
        });

        plantingForm.addEventListener("submit", function (event) {
            event.preventDefault();
            if (!selectedArea) return;
            plantingStatus.textContent = "Розміщуємо…";
            plantingStatus.classList.remove("is-error");
            const data = new FormData(plantingForm);
            post(endpoint(plantingAddTemplate, selectedArea.id), data)
                .then(function (payload) {
                    selectedArea.plantings = selectedArea.plantings || [];
                    selectedArea.plantings.push(payload.planting);
                    const usedOption = plantSelect.querySelector("option[value='" + payload.planting.plantId + "']");
                    if (usedOption) usedOption.remove();
                    plantingForm.reset();
                    updatePlantingFields();
                    updatePlantSource();
                    plantingStatus.textContent = "Рослину розміщено на грядці.";
                    refreshZone(selectedArea);
                })
                .catch(function (error) {
                    plantingStatus.textContent = error.message;
                    plantingStatus.classList.add("is-error");
                });
        });

        autoLayoutButton.addEventListener("click", function () {
            if (!selectedArea || !selectedArea.plantings.length) return;
            const plantings = selectedArea.plantings;
            const columns = Math.ceil(Math.sqrt(plantings.length));
            const rows = Math.ceil(plantings.length / columns);
            const gap = 4;
            const itemWidth = (100 - gap * (columns + 1)) / columns;
            const itemHeight = (100 - gap * (rows + 1)) / rows;
            plantingStatus.textContent = "Розкладаємо культури…";
            const requests = plantings.map(function (planting, index) {
                const column = index % columns;
                const row = Math.floor(index / columns);
                planting.x = gap + column * (itemWidth + gap);
                planting.y = gap + row * (itemHeight + gap);
                planting.width = itemWidth;
                planting.height = itemHeight;
                return persistPlanting(planting);
            });
            Promise.all(requests)
                .then(function () {
                    plantingStatus.textContent = "Культури рівномірно розміщено.";
                    refreshZone(selectedArea);
                })
                .catch(function (error) {
                    plantingStatus.textContent = error.message;
                    plantingStatus.classList.add("is-error");
                });
        });

        deleteButton.addEventListener("click", function () {
            if (!selectedArea || !window.confirm("Видалити цю зону з плану? Щоденник і рослини залишаться без змін.")) return;
            post(endpoint(deleteTemplate, selectedArea.id), new FormData())
                .then(function () {
                    const index = areas.findIndex(function (area) { return area.id === selectedArea.id; });
                    if (index !== -1) areas.splice(index, 1);
                    const element = canvas.querySelector("[data-zone-id='" + selectedArea.id + "']");
                    if (element) element.remove();
                    selectedArea = null;
                    inspectorForm.hidden = true;
                    plantingsSection.hidden = true;
                    deleteButton.hidden = true;
                    inspectorEmpty.hidden = false;
                    inspectorTitle.textContent = "Оберіть зону";
                    updateSummary();
                })
                .catch(function (error) {
                    inspectorStatus.textContent = error.message;
                    inspectorStatus.classList.add("is-error");
                });
        });

        updatePlantingFields();
        updatePlantSource();
        applyTaskFilter("active");
        renderAll();
    });
})();
