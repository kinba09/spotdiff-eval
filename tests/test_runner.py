import unittest

from spotdiff_eval.runner import DEFAULT_PROMPT, build_request_payload, extract_prediction_object


class RunnerTests(unittest.TestCase):
    def test_default_prompt_is_loaded_from_spotdiff_prompt_file(self):
        self.assertIn("genuine occlusion", DEFAULT_PROMPT)
        self.assertIn("green_jacket_person_hand", DEFAULT_PROMPT)
        self.assertIn('"differences"', DEFAULT_PROMPT)

    def test_openai_compatible_payload_contains_one_composite_image(self):
        payload = build_request_payload("data:image/png;base64,abc", "find differences", "test-model", "openai_compatible")
        content = payload["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(content[1]["image_url"]["url"], "data:image/png;base64,abc")

    def test_extracts_json_from_openai_style_response(self):
        response = {
            "choices": [
                {
                    "message": {
                        "content": "```json\n{\"differences\": [{\"kind\": \"object_added\", \"subject\": \"cloud\"}]}\n```"
                    }
                }
            ]
        }
        result = extract_prediction_object(response)
        self.assertEqual(result["differences"][0]["subject"], "cloud")

    def test_extracts_direct_prediction_object(self):
        result = extract_prediction_object({"differences": []})
        self.assertEqual(result, {"differences": []})


if __name__ == "__main__":
    unittest.main()
