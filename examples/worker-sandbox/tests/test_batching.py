import unittest

from batching import batch_items


class BatchItemsTests(unittest.TestCase):
    def test_partial_final_batch_preserves_all_items_in_order(self):
        self.assertEqual(
            batch_items(list(range(10)), 4),
            [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]],
        )

    def test_exact_capacity_has_no_extra_empty_batch(self):
        self.assertEqual(batch_items(["a", "b", "c", "d"], 2),
                         [["a", "b"], ["c", "d"]])

    def test_empty_input_produces_no_jobs(self):
        self.assertEqual(batch_items([], 4), [])

    def test_invalid_capacities_are_rejected(self):
        for capacity in (0, -1, 1.5, True):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    batch_items(["a"], capacity)


if __name__ == "__main__":
    unittest.main()
