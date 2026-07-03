(function () {
    var pollCount = 0;
    var maxPollCount = 80;

    function styleSourceAreas(root) {
        var sourceAreas = (root || document).querySelectorAll(
            ".cke_source, textarea.cke_source, .cke_contents textarea"
        );
        sourceAreas.forEach(function (sourceArea) {
            sourceArea.style.setProperty("background", "#fff", "important");
            sourceArea.style.setProperty("color", "#111", "important");
            sourceArea.style.setProperty("caret-color", "#111", "important");
            sourceArea.style.setProperty("-webkit-text-fill-color", "#111", "important");
            sourceArea.style.setProperty("text-shadow", "none", "important");
        });
    }

    function styleSourceTextarea(editor) {
        if (!editor || !editor.container || !editor.container.$) {
            return;
        }

        styleSourceAreas(editor.container.$);

        if (editor.editable && editor.editable()) {
            var editableElement = editor.editable().$;
            if (editableElement) {
                editableElement.style.setProperty("background", "#fff", "important");
                editableElement.style.setProperty("color", "#111", "important");
                editableElement.style.setProperty("caret-color", "#111", "important");
                editableElement.style.setProperty("-webkit-text-fill-color", "#111", "important");
                editableElement.style.setProperty("text-shadow", "none", "important");
            }
        }
    }

    function bindEditor(editor) {
        if (editor._agromegaSourceStylesBound) {
            return;
        }
        editor._agromegaSourceStylesBound = true;

        styleSourceTextarea(editor);
        bindArticleToolbar(editor);
        editor.on("mode", function () {
            window.setTimeout(function () {
                styleSourceTextarea(editor);
                bindArticleToolbar(editor);
            }, 0);
            window.setTimeout(function () {
                styleSourceTextarea(editor);
                bindArticleToolbar(editor);
            }, 100);
        });
    }

    function unwrapElement(element) {
        var parent = element.getParent();

        while (element.getFirst()) {
            element.getFirst().insertBefore(element);
        }

        element.remove();
        return parent;
    }

    function removeArticleStyleClasses(element) {
        ["article-note", "important-note", "article-faq-item", "article-sources"].forEach(function (className) {
            if (element.hasClass(className)) {
                element.removeClass(className);
            }
        });
    }

    function removeArticleStyles(editor) {
        var selection = editor.getSelection();
        var startElement = selection && selection.getStartElement();

        if (!startElement) {
            return;
        }

        var editable = editor.editable();
        var current = startElement;

        while (current && !current.equals(editable)) {
            if (
                current.hasClass("article-note") ||
                current.hasClass("important-note") ||
                current.hasClass("article-faq-item") ||
                current.hasClass("article-sources")
            ) {
                removeArticleStyleClasses(current);

                if (current.getName() === "div" && !current.$.attributes.length) {
                    unwrapElement(current);
                }
                editor.fire("change");
                return;
            }

            current = current.getParent();
        }
    }

    function wrapSelectionInFaqBlock(editor) {
        var selection = editor.getSelection();

        if (!selection) {
            return;
        }

        var ranges = selection.getRanges();

        if (!ranges.length || ranges[0].collapsed) {
            return;
        }

        editor.fire("saveSnapshot");

        for (var index = 0; index < ranges.length; index += 1) {
            var range = ranges[index];
            var wrapper = new CKEDITOR.dom.element("div", editor.document);
            var fragment = range.extractContents();

            wrapper.addClass("article-faq-item");
            wrapper.append(fragment);
            range.insertNode(wrapper);
            selection.selectElement(wrapper);
        }

        editor.fire("saveSnapshot");
        editor.fire("change");
    }

    function ensureArticleToolbarStyles() {
        if (document.getElementById("agro-editor-style-toolbar-css")) {
            return;
        }

        var style = document.createElement("style");
        style.id = "agro-editor-style-toolbar-css";
        style.textContent = [
            ".agro-editor-style-toolbar {",
            "display: inline-flex;",
            "gap: 6px;",
            "align-items: center;",
            "padding: 0 6px;",
            "}",
            ".agro-editor-style-button {",
            "display: inline-flex;",
            "align-items: center;",
            "min-height: 26px;",
            "padding: 3px 9px;",
            "border: 1px solid #bfc7c2;",
            "border-radius: 3px;",
            "background: #fff;",
            "color: #223044;",
            "font-size: 13px;",
            "font-weight: 600;",
            "line-height: 1.2;",
            "white-space: nowrap;",
            "cursor: pointer;",
            "user-select: none;",
            "}",
            ".agro-editor-style-button:hover,",
            ".agro-editor-style-button:focus {",
            "background: #f0f7f2;",
            "border-color: #2f7d45;",
            "color: #2f7d45;",
            "outline: none;",
            "}",
        ].join("");
        document.head.appendChild(style);
    }

    function makeArticleToolbarButton(label, title, onClick) {
        var button = document.createElement("span");
        button.setAttribute("role", "button");
        button.setAttribute("tabindex", "0");
        button.className = "agro-editor-style-button";
        button.textContent = label;
        button.title = title;
        button.addEventListener("mousedown", function (event) {
            event.preventDefault();
            event.stopPropagation();
            onClick();
        });
        button.addEventListener("keydown", function (event) {
            if (event.key !== "Enter" && event.key !== " ") {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            onClick();
        });
        return button;
    }

    function bindArticleToolbar(editor) {
        if (!editor.container || !editor.container.$ || editor._agromegaArticleToolbarBound) {
            return;
        }

        var toolbox = editor.container.$.querySelector(".cke_top .cke_toolbox");

        if (!toolbox) {
            return;
        }

        editor._agromegaArticleToolbarBound = true;
        ensureArticleToolbarStyles();

        var toolbar = document.createElement("span");
        toolbar.className = "cke_toolbar agro-editor-style-toolbar";
        toolbar.setAttribute("role", "toolbar");

        toolbar.appendChild(
            makeArticleToolbarButton("FAQ блок", "Обгорнути виділення в один FAQ блок", function () {
                editor.focus();
                wrapSelectionInFaqBlock(editor);
            })
        );
        toolbar.appendChild(
            makeArticleToolbarButton("Звичайний текст", "Прибрати кастомний стиль блоку", function () {
                editor.focus();
                removeArticleStyles(editor);
            })
        );

        toolbox.appendChild(toolbar);
    }

    function bindExistingEditors() {
        styleSourceAreas(document);

        if (!window.CKEDITOR) {
            if (pollCount < maxPollCount) {
                pollCount += 1;
                window.setTimeout(bindExistingEditors, 100);
            }
            return;
        }

        window.CKEDITOR.addCss(
            ".cke_source, .cke_contents textarea {" +
                "background: #fff !important;" +
                "color: #111 !important;" +
                "caret-color: #111 !important;" +
                "-webkit-text-fill-color: #111 !important;" +
                "text-shadow: none !important;" +
            "}" +
            ".article-note, .important-note {" +
                "margin: 0 0 1.35rem;" +
                "padding: 0.95rem 1rem;" +
                "background: #f0f7f2;" +
                "border-left: 4px solid #2f7d45;" +
                "color: #203829;" +
            "}" +
            ".important-note {" +
                "background: #f8e2d4;" +
                "border-color: rgba(178, 34, 34, 0.18);" +
                "border-left-color: #b22222;" +
            "}" +
            ".article-faq-item {" +
                "margin: 0 0 1rem;" +
                "padding: 1rem 1.125rem;" +
                "background: #f7fbf8;" +
                "border: 1px solid #d8e8dc;" +
                "color: #223044;" +
            "}" +
            ".article-faq-item h1, .article-faq-item h2, .article-faq-item h3, .article-faq-item h4, .article-faq-item h5, .article-faq-item h6 {" +
                "margin: 0 0 0.5rem;" +
                "color: #2f7d45;" +
                "font-size: 1.2rem;" +
            "}" +
            ".article-faq-item > p:first-child {" +
                "margin: 0 0 0.5rem;" +
                "color: #2f7d45;" +
                "font-size: 1.2rem;" +
                "font-weight: 800;" +
                "line-height: 1.22;" +
            "}" +
            ".article-faq-item p:last-child {" +
                "margin-bottom: 0;" +
            "}" +
            ".article-sources a {" +
                "color: inherit !important;" +
                "text-decoration: none !important;" +
                "pointer-events: none;" +
                "cursor: text;" +
            "}" +
            "table {" +
                "width: 100% !important;" +
                "min-width: 100%;" +
                "max-width: 100%;" +
                "table-layout: fixed !important;" +
                "margin: 1.35rem 0;" +
                "border: 1px solid rgba(47, 125, 69, 0.18);" +
                "border-collapse: collapse;" +
                "color: #223044;" +
                "font-size: 0.86em;" +
                "line-height: 1.55;" +
            "}" +
            "thead th, table th {" +
                "background: #dcefd7;" +
                "color: #223044;" +
                "font-weight: 800;" +
            "}" +
            "th, td {" +
                "width: auto !important;" +
                "padding: 0.75rem 0.875rem;" +
                "border: 1px solid rgba(47, 125, 69, 0.16);" +
                "text-align: left;" +
                "vertical-align: top;" +
            "}" +
            "col {" +
                "width: auto !important;" +
            "}" +
            "tbody tr:nth-child(even) td {" +
                "background: #fbfdfb;" +
            "}"
        );

        Object.keys(window.CKEDITOR.instances).forEach(function (name) {
            bindEditor(window.CKEDITOR.instances[name]);
        });

        window.CKEDITOR.on("instanceReady", function (event) {
            bindEditor(event.editor);
        });
    }

    function observeDynamicSourceAreas() {
        if (!window.MutationObserver) {
            return;
        }

        var observer = new MutationObserver(function () {
            styleSourceAreas(document);
        });
        observer.observe(document.documentElement, {
            childList: true,
            subtree: true,
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            observeDynamicSourceAreas();
            bindExistingEditors();
        });
    } else {
        observeDynamicSourceAreas();
        bindExistingEditors();
    }
}());
