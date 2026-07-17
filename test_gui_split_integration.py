import pathlib
import unittest


class GuiSplitIntegrationTests(unittest.TestCase):
    def test_split_hook_is_sidebar_mode_not_tab(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")

        self.assertIn('value="split-hook"', gui_source)
        self.assertNotIn('self.tabview.add("Chia Part + Hook")', gui_source)
        self.assertIn('elif mode == "split-hook":', gui_source)

    def test_split_hook_uses_folder_batch_delete_option_and_stop_button(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")
        folder_picker_source = gui_source[
            gui_source.index("def select_pair_input"):
            gui_source.index("def _get_folder_pairs")
        ]

        self.assertIn('self.in_btn.configure(text="Chọn Thư Mục Input")', gui_source)
        self.assertIn("askdirectory", folder_picker_source)
        self.assertNotIn("askopenfilename", folder_picker_source)
        self.assertIn("split_delete_source_var", gui_source)
        self.assertIn('"split_delete_source"', gui_source)
        self.assertIn("stop_split_btn", gui_source)
        self.assertIn("stop_split_processing", gui_source)
        self.assertIn("target=self._run_split_batch", gui_source)
        self.assertIn("collect_split_video_files", gui_source)

    def test_merge_panel_has_merge_once_option(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")

        self.assertIn("merge_once_var", gui_source)
        self.assertIn("Ghép 1 lần", gui_source)
        self.assertIn('"merge_once"', gui_source)
        self.assertIn('"merge_quiet_logs"', gui_source)

    def test_folder_pair_table_and_sequential_runner_exist(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")

        self.assertIn("folder_pairs", gui_source)
        self.assertIn("add_folder_pair_row", gui_source)
        self.assertIn("select_pair_input", gui_source)
        self.assertIn("select_pair_output", gui_source)
        self.assertIn("_get_folder_pairs", gui_source)
        self.assertIn("_run_folder_pairs_batch", gui_source)
        self.assertIn("Input", gui_source)
        self.assertIn("Output", gui_source)
        self.assertIn("process_limit_per_folder", gui_source)

    def test_download_tab_has_cookie_options(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")

        self.assertIn("Dùng cookies từ Chrome", gui_source)
        self.assertIn("Chọn cookies.txt", gui_source)
        self.assertIn("select_dl_cookies_file", gui_source)
        self.assertIn("build_ytdlp_download_command", gui_source)
        self.assertIn("build_ytdlp_prescan_command", gui_source)
        self.assertIn("--cookies-from-browser", gui_source)
        self.assertIn("--cookies", gui_source)

    def test_download_tab_has_app_update_button(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")

        self.assertIn("CẬP NHẬT APP", gui_source)
        self.assertIn("update_app_from_github", gui_source)
        self.assertIn("fetch_update_manifest", gui_source)
        self.assertIn("write_update_script", gui_source)

    def test_sidebar_has_global_karaoke_subtitle_options(self):
        gui_source = pathlib.Path("gui.py").read_text(encoding="utf-8")

        self.assertIn("subtitle_enabled_var", gui_source)
        self.assertIn("Tạo sub", gui_source)
        self.assertIn("subtitle_model_var", gui_source)
        self.assertIn('"subtitle_enabled"', gui_source)
        self.assertIn('"subtitle_model_size"', gui_source)


if __name__ == "__main__":
    unittest.main()
