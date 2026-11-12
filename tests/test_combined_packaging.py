import unittest
from pathlib import Path
import release_packaging as rp
from apply_service_patch import owned

class PackagingTests(unittest.TestCase):
    def test_one_full_generator(self):
        self.assertTrue(hasattr(rp, 'generate_production'))
        self.assertFalse(hasattr(rp, 'generate_market'))
    def test_service_overlay_scope(self):
        for svc in ('scorer','travel','sports'):
            self.assertTrue(owned(svc, f'app/{svc}/router.py'))
            self.assertTrue(owned(svc, f'static/{svc}.html'))
            self.assertFalse(owned(svc, 'app/main.py'))
            self.assertFalse(owned(svc, 'scorer_data/scorer.db'))
    def test_combined_requirements(self):
        self.assertIn("'app/scorer/router.py'", Path(rp.__file__).read_text())
        self.assertIn("'app/travel/router.py'", Path(rp.__file__).read_text())
        self.assertIn("'app/sports/router.py'", Path(rp.__file__).read_text())
if __name__ == '__main__': unittest.main()
