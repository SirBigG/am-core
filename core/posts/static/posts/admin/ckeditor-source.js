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
        ["article-note", "important-note", "article-faq-item", "article-sources", "article-list"].forEach(function (className) {
            if (element.hasClass(className)) {
                element.removeClass(className);
            }
        });
    }

    function hasArticleBlockStyle(element) {
        return (
            element &&
            (
                element.hasClass("article-note") ||
                element.hasClass("important-note") ||
                element.hasClass("article-faq-item") ||
                element.hasClass("article-sources")
            )
        );
    }

    function getClosestArticleBlock(editor, startElement) {
        var editable = editor.editable();
        var current = startElement;

        while (current && !current.equals(editable)) {
            if (hasArticleBlockStyle(current)) {
                return current;
            }

            current = current.getParent();
        }

        return null;
    }

    function getOutermostArticleBlock(editor, startElement) {
        var block = getClosestArticleBlock(editor, startElement);
        var editable = editor.editable();
        var parent;

        if (!block) {
            return null;
        }

        parent = block.getParent();

        while (parent && !parent.equals(editable)) {
            if (hasArticleBlockStyle(parent)) {
                block = parent;
            }

            parent = parent.getParent();
        }

        return block;
    }

    function unwrapNestedArticleBlocks(container) {
        var blocks = container.find("div");

        for (var index = blocks.count() - 1; index >= 0; index -= 1) {
            var block = blocks.getItem(index);

            if (hasArticleBlockStyle(block)) {
                removeArticleStyleClasses(block);

                if (block.getName() === "div" && !block.$.attributes.length) {
                    unwrapElement(block);
                }
            }
        }
    }

    function removeArticleStyles(editor) {
        var selection = editor.getSelection();
        var startElement = selection && selection.getStartElement();
        var existingBlock;
        var list;

        if (!startElement) {
            return;
        }

        editor.fire("saveSnapshot");
        existingBlock = getOutermostArticleBlock(editor, startElement);

        if (existingBlock) {
            unwrapNestedArticleBlocks(existingBlock);
            removeArticleStyleClasses(existingBlock);

            if (existingBlock.getName() === "div" && !existingBlock.$.attributes.length) {
                unwrapElement(existingBlock);
            }
        }

        list = startElement.getAscendant("ol", true) || startElement.getAscendant("ul", true);

        if (list && list.hasClass("article-list")) {
            list.removeClass("article-list");
        }

        if (editor.editable && editor.editable()) {
            removeEmptyArticleFillerBlocks(editor.editable());
        }

        editor.fire("saveSnapshot");
        editor.fire("change");
    }

    function isFillerHtml(html) {
        return html
            .replace(/&nbsp;/gi, "")
            .replace(/\u00a0/g, "")
            .replace(/<br\s*\/?>/gi, "")
            .replace(/<[^>]+>/g, "")
            .replace(/\s/g, "") === "";
    }

    function isEmptyArticleFillerBlock(element) {
        if (!element || element.type !== CKEDITOR.NODE_ELEMENT) {
            return false;
        }

        if (!/^(p|h1|h2|h3|h4|h5|h6)$/i.test(element.getName())) {
            return false;
        }

        return isFillerHtml(element.getHtml());
    }

    function removeEmptyArticleFillerBlocks(container) {
        var blocks = container.find("p,h1,h2,h3,h4,h5,h6");

        for (var index = blocks.count() - 1; index >= 0; index -= 1) {
            var block = blocks.getItem(index);

            if (isEmptyArticleFillerBlock(block)) {
                block.remove();
            }
        }
    }

    function isWhitespaceTextNode(node) {
        return node && node.type === CKEDITOR.NODE_TEXT && node.getText().replace(/\s|\u00a0/g, "") === "";
    }

    function getAdjacentArticleCleanupNode(element, method) {
        var node = element[method]();

        while (isWhitespaceTextNode(node)) {
            var emptyTextNode = node;
            node = node[method]();
            emptyTextNode.remove();
        }

        return node;
    }

    function removeAdjacentEmptyArticleFillerBlocks(element) {
        var previous = getAdjacentArticleCleanupNode(element, "getPrevious");
        var next = getAdjacentArticleCleanupNode(element, "getNext");

        while (isEmptyArticleFillerBlock(previous)) {
            var previousSibling = previous;
            previous = getAdjacentArticleCleanupNode(previous, "getPrevious");
            previousSibling.remove();
        }

        while (isEmptyArticleFillerBlock(next)) {
            var nextSibling = next;
            next = getAdjacentArticleCleanupNode(next, "getNext");
            nextSibling.remove();
        }
    }

    function wrapSelectionInArticleBlock(editor, className) {
        var selection = editor.getSelection();

        if (!selection) {
            return;
        }

        var ranges = selection.getRanges();
        var existingBlock = getOutermostArticleBlock(editor, selection.getStartElement());

        if (!ranges.length || ranges[0].collapsed) {
            return;
        }

        editor.fire("saveSnapshot");

        if (existingBlock) {
            removeArticleStyleClasses(existingBlock);
            existingBlock.addClass(className);
            unwrapNestedArticleBlocks(existingBlock);
            removeEmptyArticleFillerBlocks(existingBlock);
            selection.selectElement(existingBlock);
            editor.fire("saveSnapshot");
            editor.fire("change");
            return;
        }

        for (var index = 0; index < ranges.length; index += 1) {
            var range = ranges[index];
            var wrapper = new CKEDITOR.dom.element("div", editor.document);
            var fragment = range.extractContents();

            wrapper.addClass(className);
            wrapper.append(fragment);
            unwrapNestedArticleBlocks(wrapper);
            removeEmptyArticleFillerBlocks(wrapper);
            range.insertNode(wrapper);
            removeAdjacentEmptyArticleFillerBlocks(wrapper);
            selection.selectElement(wrapper);
        }

        if (editor.editable && editor.editable()) {
            removeEmptyArticleFillerBlocks(editor.editable());
        }

        editor.fire("saveSnapshot");
        editor.fire("change");
    }

    function wrapSelectionInFaqBlock(editor) {
        wrapSelectionInArticleBlock(editor, "article-faq-item");
    }

    function applyListClass(editor, commandName) {
        var selection;
        var startElement;
        var list;

        editor.execCommand(commandName);
        selection = editor.getSelection();
        startElement = selection && selection.getStartElement();
        list = startElement && startElement.getAscendant(commandName === "numberedlist" ? "ol" : "ul", true);

        if (list) {
            list.addClass("article-list");
        }

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
            ".agro-editor-style-select {",
            "min-height: 26px;",
            "padding: 3px 28px 3px 9px;",
            "border: 1px solid #bfc7c2;",
            "border-radius: 3px;",
            "background: #fff;",
            "color: #223044;",
            "font-size: 13px;",
            "font-weight: 600;",
            "line-height: 1.2;",
            "white-space: nowrap;",
            "cursor: pointer;",
            "}",
            ".agro-editor-style-select:hover,",
            ".agro-editor-style-select:focus {",
            "background: #f0f7f2;",
            "border-color: #2f7d45;",
            "color: #2f7d45;",
            "outline: none;",
            "}",
        ].join("");
        document.head.appendChild(style);
    }

    function makeArticleToolbarSelect(editor) {
        var select = document.createElement("select");
        var actions = {
            note: function () {
                wrapSelectionInArticleBlock(editor, "article-note");
            },
            important: function () {
                wrapSelectionInArticleBlock(editor, "important-note");
            },
            faq: function () {
                wrapSelectionInFaqBlock(editor);
            },
            numberedList: function () {
                applyListClass(editor, "numberedlist");
            },
            bulletedList: function () {
                applyListClass(editor, "bulletedlist");
            },
            plainText: function () {
                removeArticleStyles(editor);
            },
        };
        var options = [
            ["", "Стилі статті"],
            ["note", "Підказка"],
            ["important", "Важливо"],
            ["faq", "FAQ блок"],
            ["numberedList", "1. Список"],
            ["bulletedList", "• Список"],
            ["plainText", "Звичайний текст"],
        ];

        select.className = "agro-editor-style-select";
        select.title = "Застосувати стиль до виділення";

        options.forEach(function (optionConfig) {
            var option = document.createElement("option");
            option.value = optionConfig[0];
            option.textContent = optionConfig[1];
            select.appendChild(option);
        });

        select.addEventListener("mousedown", function (event) {
            event.stopPropagation();
        });
        select.addEventListener("change", function () {
            var action = actions[select.value];

            if (!action) {
                return;
            }

            editor.focus();
            action();
            select.value = "";
        });

        return select;
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

        toolbar.appendChild(makeArticleToolbarSelect(editor));

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
            "h1, h2, h3, h4, h5, h6, .h1, .h2, .h3, .h4, .h5, .h6 {" +
                "color: #2f7d45;" +
                "font-weight: 800;" +
                "line-height: 1.22;" +
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
            ".article-list li::marker {" +
                "color: #2f7d45;" +
                "font-weight: 800;" +
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
