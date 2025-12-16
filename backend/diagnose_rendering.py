import sys
import os
import importlib.util
from pathlib import Path

def check_package(package_name):
    spec = importlib.util.find_spec(package_name)
    if spec is None:
        print(f"[FAIL] Package '{package_name}' is NOT installed.")
        return False
    print(f"[PASS] Package '{package_name}' is installed.")
    return True

def check_powerpoint():
    if sys.platform != 'win32':
        print("[INFO] Not on Windows, skipping PowerPoint check.")
        return True
    
    try:
        import comtypes.client
        app = comtypes.client.CreateObject("PowerPoint.Application")
        app.Quit()
        print("[PASS] Microsoft PowerPoint is installed and accessible via comtypes.")
        return True
    except Exception as e:
        print(f"[FAIL] Microsoft PowerPoint check failed: {e}")
        print("       PPTX rendering will fail on Windows without PowerPoint.")
        return False

def check_cache_dir():
    cache_path = Path("./data/image_cache")
    try:
        cache_path.mkdir(parents=True, exist_ok=True)
        test_file = cache_path / "test_write.txt"
        test_file.write_text("test")
        test_file.unlink()
        print(f"[PASS] Cache directory '{cache_path}' is writable.")
        return True
    except Exception as e:
        print(f"[FAIL] Cache directory '{cache_path}' check failed: {e}")
        return False

def main():
    print("=== Document Rendering Diagnosis ===")
    
    # 1. Check Python Dependencies
    deps = ["pdfplumber", "pypdfium2", "comtypes", "PIL"]
    all_deps_ok = True
    for dep in deps:
        if not check_package(dep):
            all_deps_ok = False
            
    # 2. Check PowerPoint (Windows only)
    ppt_ok = check_powerpoint()
    
    # 3. Check Cache Directory
    cache_ok = check_cache_dir()
    
    print("\n=== Summary ===")
    if all_deps_ok and ppt_ok and cache_ok:
        print("✅ All checks passed. Rendering should work.")
    else:
        print("❌ Some checks failed. See details above.")

if __name__ == "__main__":
    main()
