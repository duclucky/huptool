import os
import time
import undetected_chromedriver as uc

def main():
    profile_dir = os.path.abspath("chrome_profile")
    import subprocess
    try:
        output = subprocess.check_output('reg query "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon" /v version', shell=True).decode()
        v_main = int(output.strip().split()[-1].split('.')[0])
    except Exception:
        v_main = 149

    print("Opening Chrome for login...")
    driver = uc.Chrome(user_data_dir=profile_dir, version_main=v_main)
    driver.get("https://gemini.google.com/app")
    
    print("PLEASE LOG IN TO GOOGLE. CLOSE THE BROWSER WHEN DONE.")
    
    try:
        while True:
            _ = driver.title
            time.sleep(1)
    except Exception:
        print("Browser closed. Session saved.")

if __name__ == "__main__":
    main()
