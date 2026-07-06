import os
import argparse
import glob
import json
import random
from video_processor import VideoProcessor
from metadata_manager import MetadataManager
from config import Config

def ensure_dirs(input_dir, output_dir):
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

def process_single_file(input_video, output_dir, mode, account, min_len, max_len):
    filename = os.path.basename(input_video)
    name_no_ext, ext = os.path.splitext(filename)
    print(f"\n--- Đang xử lý: {filename} ---")
    
    processor = VideoProcessor()
    meta_manager = MetadataManager()
    
    if mode == "auto":
        print("[1/3] Đang gửi phân tích AI (Gemini Multimodal)...")
        from ai_analyzer import AIAnalyzer
        analyzer = AIAnalyzer()
        analysis_array = analyzer.analyze(input_video, account, min_len, max_len)
        
        if not analysis_array or not isinstance(analysis_array, list):
            print(f"BỎ QUA: Lỗi phân tích AI cho file {filename}")
            return False
            
        total_parts = len(analysis_array)
        print(f"-> Tuyệt vời! AI tìm được {total_parts} đoạn Highlight đỉnh nhất.")
        
        for idx, analysis_result in enumerate(analysis_array):
            part_num = idx + 1
            raw_title = (
                analysis_result.get('title') or 
                analysis_result.get('Title') or 
                analysis_result.get('TITLE') or 
                f"Phan_{part_num}"
            )
            import re
            safe_title = re.sub(r'[\\/*?:"<>|]', "", raw_title).strip()
            if not safe_title:
                safe_title = f"Phan_{part_num}"
                
            final_output = os.path.join(output_dir, f"{safe_title}.mp4")
            temp_output = os.path.join(output_dir, f"temp_{safe_title}.mp4")
            
            counter = 1
            while os.path.exists(final_output) or os.path.exists(temp_output):
                final_output = os.path.join(output_dir, f"{safe_title}_{counter}.mp4")
                temp_output = os.path.join(output_dir, f"temp_{safe_title}_{counter}.mp4")
                counter += 1
                
            print(f"\n[2/3] Chạy Wash Engine cho Đoạn {part_num}/{total_parts}...")
            print(f"  Highlight: {analysis_result.get('highlight_start')}s -> {analysis_result.get('highlight_end')}s")
            print(f"  Hook: {analysis_result.get('hook_start')}s -> {analysis_result.get('hook_end')}s")
            
            success = processor.process_video(
                input_video, 
                temp_output,
                mode="auto",
                hook_start=analysis_result.get('hook_start'),
                hook_end=analysis_result.get('hook_end'),
                hl_start=analysis_result.get('highlight_start'),
                hl_end=analysis_result.get('highlight_end')
            )
            
            if not success:
                print(f"Lỗi cắt FFmpeg ở đoạn {part_num}.")
                continue
                
            print(f"[3/3] Làm mới Metadata & Hash cho Đoạn {part_num}...")
            meta_manager.clean_and_fake_metadata(temp_output, final_output)
            
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except:
                    pass
            print(f"XONG ĐOẠN {part_num}: -> {os.path.basename(final_output)}")
            
        return True
    else:
        # Chế độ wash-only chỉ nhả 1 file
        final_output = os.path.join(output_dir, f"washed_{filename}")
        temp_output = os.path.join(output_dir, f"temp_{filename}")
        
        if os.path.exists(final_output):
            print(f"BỎ QUA: {filename} đã tồn tại.")
            return True
            
        print("[1/2] Chạy Wash Engine (Làm mới video, không cắt)...")
        success = processor.process_video(input_video, temp_output, mode="wash-only")
        
        if not success:
            print(f"BỎ QUA: Lỗi Wash Engine cho file {filename}")
            return False
            
        print("[2/2] Làm mới Metadata & Hash...")
        meta_manager.clean_and_fake_metadata(temp_output, final_output)
        
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass
        print(f"XONG: -> {os.path.basename(final_output)}")
        return True

def run_merge_batch(input_dir, output_dir, extra_args):
    merge_count = extra_args.get("merge_count", 5) if extra_args else 5
    merge_out_max = extra_args.get("merge_out_max", 0) if extra_args else 0
    trim_min = extra_args.get("merge_trim_min", 5) if extra_args else 5
    trim_max = extra_args.get("merge_trim_max", 10) if extra_args else 10
    merge_once = bool(extra_args.get("merge_once", False)) if extra_args else False
    merge_quiet_logs = bool(extra_args.get("merge_quiet_logs", True)) if extra_args else True

    ensure_dirs(input_dir, output_dir)
    input_files = glob.glob(os.path.join(input_dir, "*.mp4"))

    history_file = os.path.join(input_dir, ".ai_merge_history.json")
    history = {
        "forbidden_pairs": [],
        "first_video_pool": [],
        "first_video_used_cycle": [],
        "first_video_all_cycle": [],
        "one_time_used_videos": [],
    }
    if os.path.exists(history_file):
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                history.update(loaded)
        except Exception as e:
            print(f"Lỗi đọc file lịch sử: {e}")

    forbidden_pairs = set(history.get("forbidden_pairs", []))
    first_video_pool = history.get("first_video_pool", [])
    first_video_used_cycle = history.get("first_video_used_cycle", [])
    first_video_all_cycle = history.get("first_video_all_cycle", [])
    one_time_used_videos = set(history.get("one_time_used_videos", []))

    raw_video_count = len(input_files)
    if merge_once:
        input_files = [f for f in input_files if os.path.basename(f) not in one_time_used_videos]

    basenames = [os.path.basename(f) for f in input_files]
    max_text = merge_out_max if merge_out_max > 0 else "không giới hạn"

    print("=" * 50)
    print("Bắt đầu Merge & Wash")
    print(f"Input: {raw_video_count} video | Ghép: {merge_count}/video | Tạo tối đa: {max_text}")
    if merge_once:
        print(f"Ghép 1 lần: ON | Chưa dùng: {len(basenames)} | Đã dùng: {len(one_time_used_videos)}")
    else:
        print("Ghép 1 lần: OFF")
    print("=" * 50)

    if len(basenames) < merge_count:
        if merge_once:
            print(f"Không đủ video chưa dùng. Cần {merge_count}, còn {len(basenames)}.")
        else:
            print(f"LỖI: Không đủ video. Cần {merge_count}, có {len(basenames)}")
        return

    if not first_video_pool and not first_video_used_cycle:
        first_video_pool = list(basenames)
        first_video_used_cycle = []
        first_video_all_cycle = list(basenames)
        random.shuffle(first_video_pool)
    elif set(first_video_all_cycle) != set(basenames):
        first_video_pool = list(basenames)
        first_video_used_cycle = []
        first_video_all_cycle = list(basenames)
        random.shuffle(first_video_pool)

    processor = VideoProcessor()
    meta_manager = MetadataManager()

    created_count = 0
    error_count = 0
    max_limit = merge_out_max if merge_out_max > 0 else 999999
    consecutive_failures = 0

    while created_count < max_limit:
        if merge_once:
            basenames = [v for v in basenames if v not in one_time_used_videos]
            first_video_pool = [v for v in first_video_pool if v not in one_time_used_videos]
            if len(basenames) < merge_count:
                print(f"Không đủ video chưa dùng để ghép tiếp. Cần {merge_count}, còn {len(basenames)}.")
                break

        if len(first_video_pool) == 0:
            first_video_pool = list(basenames)
            first_video_used_cycle = []
            first_video_all_cycle = list(basenames)
            random.shuffle(first_video_pool)

        first_video = first_video_pool.pop(0)
        remaining_candidates = [v for v in basenames if v != first_video]
        if len(remaining_candidates) < merge_count - 1:
            print("Không đủ video để ghép tiếp.")
            break

        found_safe = False
        safe_sequence = []
        best_sequence = None
        best_duplicate_count = 999999

        for _ in range(1000):
            selected_others = random.sample(remaining_candidates, merge_count - 1)
            random.shuffle(selected_others)
            sequence = [first_video] + selected_others

            duplicate_count = 0
            for i in range(len(sequence) - 1):
                pair = f"{sequence[i]}->{sequence[i+1]}"
                if pair in forbidden_pairs:
                    duplicate_count += 1

            if duplicate_count == 0:
                found_safe = True
                safe_sequence = sequence
                break

            if duplicate_count < best_duplicate_count:
                best_duplicate_count = duplicate_count
                best_sequence = sequence

        if not found_safe:
            safe_sequence = best_sequence

        print(f"[{created_count + 1}] Đang ghép: {' + '.join(safe_sequence)}")

        full_paths = [os.path.join(input_dir, v) for v in safe_sequence]
        safe_title = f"Merged_{created_count + 1}_{int(random.random() * 10000)}"
        temp_output = os.path.join(output_dir, f"temp_{safe_title}.mp4")
        final_output = os.path.join(output_dir, f"{safe_title}.mp4")

        success = processor.merge_and_wash(
            full_paths,
            temp_output,
            trim_min,
            trim_max,
            verbose=not merge_quiet_logs,
        )

        if success:
            meta_manager.clean_and_fake_metadata(temp_output, final_output)

            for i in range(len(safe_sequence) - 1):
                pair = f"{safe_sequence[i]}->{safe_sequence[i+1]}"
                forbidden_pairs.add(pair)

            if first_video not in first_video_used_cycle:
                first_video_used_cycle.append(first_video)

            if merge_once:
                one_time_used_videos.update(safe_sequence)

            history["forbidden_pairs"] = list(forbidden_pairs)
            history["first_video_pool"] = first_video_pool
            history["first_video_used_cycle"] = first_video_used_cycle
            history["first_video_all_cycle"] = first_video_all_cycle
            history["one_time_used_videos"] = sorted(one_time_used_videos)

            try:
                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=4)
            except:
                pass

            created_count += 1
            consecutive_failures = 0
            print(f"[{created_count}] OK -> {os.path.basename(final_output)}")
        else:
            consecutive_failures += 1
            error_count += 1
            print(f"[{created_count + 1}] Lỗi ghép, đang thử lượt khác.")
            first_video_pool.insert(0, first_video)

            if consecutive_failures >= 3:
                print("Lỗi ghép liên tiếp 3 lần. Đang dừng thuật toán để tránh lặp vô hạn.")
                break

        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except:
                pass

    print("=" * 50)
    print(f"Hoàn tất Merge & Wash: tạo {created_count} video | lỗi {error_count}")



def run_batch(input_dir, output_dir, mode, account, min_len, max_len, extra_args=None):
    if mode == "merge-wash":
        run_merge_batch(input_dir, output_dir, extra_args)
        return
        
    ensure_dirs(input_dir, output_dir)
    input_files = glob.glob(os.path.join(input_dir, "*.mp4"))
    process_limit = int(extra_args.get("process_limit_per_folder", 0)) if extra_args else 0
    if process_limit > 0:
        input_files = input_files[:process_limit]
    
    if not input_files:
        print(f"Thư mục trống: {input_dir}")
        print("Vui lòng copy các video vào thư mục này rồi chạy lại tool.")
        return
        
    print("="*50)
    print(f"TÌM THẤY {len(input_files)} VIDEO GỐC ĐỂ XỬ LÝ")
    print(f"CHẾ ĐỘ: {mode.upper()}")
    print("="*50)
    
    success_count = 0
    for input_file in input_files:
        if process_single_file(input_file, output_dir, mode, account, min_len, max_len):
            success_count += 1
            try:
                os.remove(input_file)
                print(f"[DỌN DẸP] Đã xóa file gốc thành công: {os.path.basename(input_file)}")
            except Exception as e:
                print(f"[LỖI] Không thể xóa file gốc {input_file}: {e}")
            
    print("="*50)
    print(f"HOÀN THÀNH BATCH! Đã xử lý xong {success_count}/{len(input_files)} video gốc.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Video Processor V7")
    parser.add_argument("--mode", choices=["auto", "wash-only", "merge-wash"], default="wash-only")
    parser.add_argument("--min", type=int, default=30)
    parser.add_argument("--max", type=int, default=60)
    parser.add_argument("--account", choices=["free", "pro"], default="free")
    parser.add_argument("--mcount", type=int, default=5)
    parser.add_argument("--mmax", type=int, default=0)
    parser.add_argument("--mtmin", type=float, default=5)
    parser.add_argument("--mtmax", type=float, default=10)
    args = parser.parse_args()
    
    extra_args = {
        "merge_count": args.mcount,
        "merge_out_max": args.mmax,
        "merge_trim_min": args.mtmin,
        "merge_trim_max": args.mtmax
    }
    
    run_batch(Config.INPUT_DIR, Config.OUTPUT_DIR, args.mode, args.account, args.min, args.max, extra_args)
