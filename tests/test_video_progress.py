import unittest

from ytdl.video_progress import VideoProgress


def plan(**extra):
    return {"video": {"id": "abc", "title": "Exemplo"}, "formats": [
        {"format_id": "v", "acodec": "none", "vcodec": "h264"},
        {"format_id": "a", "vcodec": "none", "acodec": "aac"}], **extra}


class VideoProgressTests(unittest.TestCase):
    def test_image_finished_does_not_finish_audio_or_merging(self):
        model = VideoProgress.from_plan(plan())
        model.select_file("v")
        model.files[model.current]["status"] = "Concluída"
        self.assertEqual(model.next_label, "Áudio")
        self.assertIn("áudio", model.remaining_text)
        self.assertEqual(model.steps["Juntar imagem e áudio"], "Aguardando")
        model.select_file("a")
        self.assertEqual(model.current, 1)
        model.processing("Merger", "started")
        self.assertEqual(model.steps["Juntar imagem e áudio"], "Em andamento")

    def test_mp3_and_combined_formats_have_different_steps(self):
        model = VideoProgress.from_plan(plan(audio=True, formats=[{"format_id": "a", "vcodec": "none"}]))
        self.assertEqual(len(model.files), 1)
        self.assertIn("Converter para MP3", model.steps)
        self.assertNotIn("Juntar imagem e áudio", model.steps)
        combined = VideoProgress.from_plan(plan(formats=[]))
        self.assertEqual(combined.files[0]["label"], "Vídeo e áudio")
        self.assertNotIn("Juntar imagem e áudio", combined.steps)

    def test_subtitles_only_and_missing_subtitles(self):
        model = VideoProgress.from_plan(plan(subtitles_only=True, subtitles_requested=True))
        self.assertEqual(model.files, [])
        self.assertEqual(model.steps["Legendas"], "Não disponíveis")
        self.assertNotIn("Juntar imagem e áudio", model.steps)

    def test_failure_and_cancel_preserve_completed_stages(self):
        model = VideoProgress.from_plan(plan())
        model.select_file("v")
        model.files[0]["status"] = "Concluída"
        model.select_file("a")
        model.end("Cancelada")
        self.assertEqual(model.files[0]["status"], "Concluída")
        self.assertEqual(model.files[1]["status"], "Cancelada")
        model.processing("Merger", "started")
        model.end("Falhou")
        self.assertEqual(model.steps["Juntar imagem e áudio"], "Falhou")

    def test_fragment_progress_selects_same_file(self):
        model = VideoProgress.from_plan(plan())
        for _ in range(5):
            model.select_file("v")
        self.assertEqual(len(model.files), 2)
        self.assertEqual(model.current, 0)

    def test_video_success_preserves_subtitle_failure(self):
        model = VideoProgress.from_plan(plan(subtitles=[{"ext": "srt"}]))
        model.select_file(subtitle=True)
        model.files[0]["status"] = "Falhou"
        model.end("Concluído")
        self.assertEqual(model.files[0]["status"], "Falhou")
        self.assertEqual(model.steps["Finalizar arquivo"], "Concluída")
