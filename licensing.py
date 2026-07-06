import os
import json
import hashlib
import subprocess
import base64
from config import get_app_dir

# Khóa Public Key được nhúng trực tiếp (An toàn để public)
RSA_N = 113917724117332164527952129075203421580298094973262510052242910701631785097454293247983504819990823582086551696670381727228960703877813307854631896178078482823519371658215772186709799632535199308947182552444627539976982831559198978942587458081141115981257101324558848105746602226606243088209366756838672181617
RSA_E = 65537

def get_hwid():
    try:
        CREATE_NO_WINDOW = 0x08000000
        output = subprocess.check_output('wmic csproduct get uuid', creationflags=CREATE_NO_WINDOW, text=True, shell=True)
        lines = output.strip().split('\n')
        if len(lines) >= 2:
            uuid_str = lines[1].strip()
            if uuid_str and uuid_str != "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF":
                return hashlib.md5(uuid_str.encode()).hexdigest()[:16].upper()
    except:
        pass
    import uuid
    return hashlib.md5(str(uuid.getnode()).encode()).hexdigest()[:16].upper()

def get_license_path():
    app_dir = get_app_dir()
    return os.path.join(app_dir, "license.dat")

def verify_key(activation_key):
    try:
        # Key format: BASE64(PAYLOAD_JSON).BASE64(SIGNATURE_INT)
        parts = activation_key.strip().split('.')
        if len(parts) != 2:
            return False, "Định dạng Key không hợp lệ."
            
        payload_b64, sig_b64 = parts
        
        payload_json = base64.b64decode(payload_b64).decode('utf-8')
        sig_int = int.from_bytes(base64.b64decode(sig_b64), byteorder='big')
        
        # Verify signature
        payload_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
        hash_int = int(payload_hash, 16)
        
        decrypted_hash = pow(sig_int, RSA_E, RSA_N)
        if decrypted_hash != hash_int:
            return False, "Key giả mạo hoặc bị hỏng."
            
        data = json.loads(payload_json)
        
        # Kiểm tra nội dung
        if data.get("product") != "HupTool":
            return False, "Key này không dành cho Húp Tool."
            
        current_hwid = get_hwid()
        if data.get("hwid") and data.get("hwid") != current_hwid:
            return False, f"Key không đúng máy (Sai HWID). HWID của bạn: {current_hwid}"
            
        # Kiểm tra expire_date nếu cần (tuỳ chọn thêm)
        
        return True, data
    except Exception as e:
        return False, f"Lỗi xác thực: {e}"

def load_and_verify_license():
    license_path = get_license_path()
    if not os.path.exists(license_path):
        return False, "Chưa có bản quyền", None
        
    try:
        with open(license_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
            
        ok, result = verify_key(key)
        if ok:
            return True, "Hợp lệ", result
        else:
            return False, result, None
    except:
        return False, "Lỗi đọc file license", None

def save_license(activation_key):
    license_path = get_license_path()
    with open(license_path, "w", encoding="utf-8") as f:
        f.write(activation_key)
