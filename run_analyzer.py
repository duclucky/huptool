import os
import sys
import codecs

# Fix utf-8 printing on windows console
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from ai_analyzer import AIAnalyzer

def main():
    video_path = os.path.abspath(r"input_videos\dummy.mp4")
    if not os.path.exists(video_path):
        print(f"Video khong ton tai: {video_path}")
        return
        
    print(f"Bat dau test analyze voi video: {video_path}")
    analyzer = AIAnalyzer()
    
    try:
        results = analyzer.analyze(video_path, account="free", min_len=5, max_len=10)
        print("======== KET QUA ========")
        print(results)
        print("=========================")
    except Exception as e:
        print(f"Exception during analyze: {e}")

if __name__ == "__main__":
    main()
