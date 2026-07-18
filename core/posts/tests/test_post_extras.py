import json

from django.test import SimpleTestCase

from core.posts.templatetags.post_extras import faq_structured_data


class FaqStructuredDataTests(SimpleTestCase):
    def test_builds_entities_from_paragraph_and_heading_questions(self):
        payload = faq_structured_data("""
            <div class="callout article-faq-item featured">
                <p><strong> Перше питання? </strong></p>
                <p>Перша <em>відповідь</em>.</p>
                <ul><li>Додаткова деталь</li></ul>
            </div>
            <div class="article-faq-item">
                <h3>Друге питання?</h3>
                <p>Друга відповідь.</p>
            </div>
            """)

        data = json.loads(payload)

        self.assertEqual(data["@type"], "FAQPage")
        self.assertEqual(
            data["mainEntity"],
            [
                {
                    "@type": "Question",
                    "name": "Перше питання?",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Перша відповідь. Додаткова деталь",
                    },
                },
                {
                    "@type": "Question",
                    "name": "Друге питання?",
                    "acceptedAnswer": {"@type": "Answer", "text": "Друга відповідь."},
                },
            ],
        )

    def test_ignores_incomplete_and_invalid_blocks(self):
        payload = faq_structured_data("""
            <div class="article-faq-item"><p>Question without answer?</p></div>
            <div class="article-faq-item"><div>Not a question element</div><p>Answer</p></div>
            <div class="article-faq-item"><p></p><p>Answer without question</p></div>
            """)

        self.assertEqual(payload, "")

    def test_ignores_nested_faq_blocks(self):
        payload = faq_structured_data("""
            <div class="article-faq-item">
                <p>Outer question?</p>
                <div class="article-faq-item"><p>Nested question?</p><p>Nested answer.</p></div>
            </div>
            """)

        self.assertEqual(payload, "")

    def test_escapes_script_closing_text_in_json_ld(self):
        payload = faq_structured_data(
            '<div class="article-faq-item"><p>Can text contain &lt;/script&gt;?</p><p>Yes &amp; safely.</p></div>'
        )

        self.assertNotIn("</script", payload.lower())
        data = json.loads(payload)
        self.assertEqual(data["mainEntity"][0]["name"], "Can text contain </script>?")
        self.assertEqual(data["mainEntity"][0]["acceptedAnswer"]["text"], "Yes & safely.")
