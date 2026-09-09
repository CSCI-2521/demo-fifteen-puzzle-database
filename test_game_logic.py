import unittest

from game_logic import is_solvable, move_tile, scrambled_board, solved_board


class GameLogicTests(unittest.TestCase):
    def test_each_supported_puzzle_has_the_expected_solved_board(self):
        self.assertEqual(solved_board(2), [1, 2, 3, 4])
        self.assertEqual(solved_board(3), list(range(1, 10)))
        self.assertEqual(solved_board(4), list(range(1, 17)))

    def test_only_adjacent_tiles_move_into_the_blank(self):
        board = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 15]

        moved = move_tile(board, 15, 4)
        self.assertEqual(moved, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16])

        self.assertIsNone(move_tile(board, 12, 4))
        self.assertEqual(board[-2:], [16, 15])

    def test_solvability_uses_the_board_width(self):
        self.assertTrue(is_solvable(solved_board(3), 3))
        self.assertTrue(is_solvable(solved_board(4), 4))
        self.assertFalse(is_solvable([2, 1, 3, 4, 5, 6, 7, 8, 9], 3))

    def test_scramble_never_returns_the_solved_board(self):
        for size in (2, 3, 4):
            for _ in range(20):
                board = scrambled_board(size)
                self.assertNotEqual(board, solved_board(size))


if __name__ == "__main__":
    unittest.main()
