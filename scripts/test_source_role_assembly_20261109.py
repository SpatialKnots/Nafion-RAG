"""Prior affected scope plus assembly tests, under the existing network audit guard."""

from unittest.mock import patch

from scripts import test_source_paraphrases_20261109 as runner


def main():
    with patch.object(runner, "TEST_FILES", (*runner.TEST_FILES, "test_natural_source_grammar.py", "test_source_role_assembly.py")):
        runner.main()


if __name__ == "__main__":
    main()
