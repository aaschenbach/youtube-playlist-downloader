import unittest

from ytdl.playlist_progress import PlaylistProgress


class PlaylistProgressTests(unittest.TestCase):
    def metadata(self):
        return {"entries": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}

    def test_file_bytes_and_conversion_do_not_finish_playlist_item(self):
        progress = PlaylistProgress.from_metadata(self.metadata())
        progress.begin(1, 3)
        progress.record("a", "Baixando")
        self.assertEqual(progress.processed, 0)
        self.assertEqual(progress.remaining, 3)
        self.assertEqual(progress.percent, 0)
        progress.record("a", "Concluído")
        self.assertEqual(progress.processed, 1)
        self.assertEqual(progress.remaining, 2)
        self.assertAlmostEqual(progress.percent, 100 / 3)

    def test_archive_skip_before_position_and_failure_are_separate_outcomes(self):
        progress = PlaylistProgress.from_metadata(self.metadata())
        progress.record("a", "Já baixado")
        progress.begin(2, 3)
        progress.record("b", "Concluído")
        progress.begin(3, 3)
        progress.record("c", "Falhou")
        progress.record("c", "Falhou")
        progress.record("c", "Concluído")
        self.assertEqual(progress.processed, 3)
        self.assertEqual(progress.remaining, 0)
        self.assertEqual(progress.percent, 100)
        self.assertEqual(progress.count("Concluído"), 1)
        self.assertEqual(progress.count("Já baixado"), 1)
        self.assertEqual(progress.count("Falhou"), 1)

    def test_duplicate_video_ids_count_each_playlist_position(self):
        progress = PlaylistProgress.from_metadata({"entries": [{"id": "a"}, {"id": "a"}]})
        progress.begin(1, 2)
        progress.record("a", "Concluído")
        progress.record("a", "Já baixado")
        self.assertEqual(progress.processed, 2)
        self.assertEqual(progress.count("Concluído"), 1)
        self.assertEqual(progress.count("Já baixado"), 1)

    def test_interrupted_playlist_remains_partial(self):
        progress = PlaylistProgress.from_metadata(self.metadata())
        progress.begin(1, 3)
        progress.record("a", "Concluído")
        progress.begin(2, 3)
        progress.record("b", "Baixando")
        self.assertEqual(progress.processed, 1)
        self.assertEqual(progress.remaining, 2)
        self.assertLess(progress.percent, 100)

    def test_unknown_total_has_no_percentage_and_real_total_can_change(self):
        progress = PlaylistProgress()
        progress.begin(1, None)
        progress.record("a", "Concluído")
        self.assertIsNone(progress.percent)
        self.assertIsNone(progress.remaining)
        progress.begin(2, 4)
        self.assertEqual(progress.remaining, 3)
        self.assertEqual(progress.percent, 25)

    def test_finish_does_not_invent_results_for_unidentified_items(self):
        progress = PlaylistProgress.from_metadata(self.metadata())
        progress.record("a", "Já baixado")
        progress.finish()
        self.assertEqual(progress.processed, 1)
        self.assertEqual(progress.count("Concluído"), 0)
        self.assertEqual(progress.remaining, 2)

    def test_empty_playlist_does_not_divide_by_zero(self):
        progress = PlaylistProgress.from_metadata({"entries": []})
        progress.finish()
        self.assertEqual(progress.remaining, 0)
        self.assertIsNone(progress.percent)

    def test_filtered_video_before_position_counts_as_skipped(self):
        progress = PlaylistProgress.from_metadata({"entries": [{"id": "a", "title": "Live"}, {"id": "b", "title": "Live"}]})
        progress.filtered("Live")
        progress.filtered("Live")
        self.assertEqual(progress.count("Pulado"), 2)
        self.assertEqual(progress.remaining, 0)


if __name__ == "__main__":
    unittest.main()
